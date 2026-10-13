"""
Indicators API Router.
Provides endpoints for retrieving indicator catalogs with timeframe filters (1D, 1W, 1M, 1Q, 1Y, 2Y, 3Y, ALL),
latest values & downsampled sparklines, as well as historical time-series queries.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Indicator, IndicatorValue
from app.db.schemas import ApiResponse
from app.core.analytics.calculator import compute_relative_change

router = APIRouter(prefix="/indicators", tags=["Indicators"])

# Timeframe days mapping
RANGE_DAYS: Dict[str, int] = {
    "1D": 1,
    "1W": 7,
    "1M": 30,
    "1Q": 90,
    "3M": 90,
    "1Y": 365,
    "2Y": 730,
    "3Y": 1095,
}


@router.get("", response_model=ApiResponse[List[Dict[str, Any]]], summary="Get indicator catalog with latest metrics")
def get_indicators(
    category: Optional[str] = Query(None, description="Optional category filter (MACRO, RATES, FX, COMMODITY, EQUITY, SENTIMENT)"),
    timeframe: str = Query("1D", alias="range", description="Timeframe filter: 1D, 1W, 1M, 1Q, 3M, 1Y, 2Y, 3Y, ALL"),
    db: Session = Depends(get_db),
):
    """
    Retrieve list of indicators with values, timeframe changes (period_change), and mini-sparklines.
    """
    range_upper = timeframe.upper() if timeframe else "1D"


    query = db.query(Indicator).filter(Indicator.is_active == True)
    if category:
        query = query.filter(Indicator.category == category.upper())
    indicators = query.order_by(Indicator.priority.asc(), Indicator.id.asc()).all()

    results: List[Dict[str, Any]] = []
    for ind in indicators:
        # Fetch latest record
        latest_val = (
            db.query(IndicatorValue)
            .filter(IndicatorValue.indicator_id == ind.id)
            .order_by(IndicatorValue.record_date.desc())
            .first()
        )

        if not latest_val:
            results.append({
                "id": ind.id,
                "symbol": ind.symbol,
                "name_vi": ind.name_vi,
                "name_en": ind.name_en,
                "category": ind.category,
                "unit": ind.unit,
                "frequency": ind.frequency,
                "priority": ind.priority,
                "latest_value": None,
                "change_1d": None,
                "change_1w": None,
                "change_1m": None,
                "period_change": None,
                "range": range_upper,
                "trend_state": "NEUTRAL",
                "record_date": None,
                "sparkline": [],
            })
            continue

        anchor_date = latest_val.record_date

        # Calculate period_change based on chosen timeframe
        if range_upper == "1D":
            period_change = latest_val.change_1d
        elif range_upper == "1W":
            period_change = latest_val.change_1w
        elif range_upper == "1M":
            period_change = latest_val.change_1m
        else:
            # For 1Q, 3M, 1Y, 2Y, 3Y, ALL: query benchmark historical point
            if range_upper == "ALL":
                past_rec = (
                    db.query(IndicatorValue)
                    .filter(IndicatorValue.indicator_id == ind.id)
                    .order_by(IndicatorValue.record_date.asc())
                    .first()
                )
            else:
                days = RANGE_DAYS.get(range_upper, 90)
                cutoff_date = anchor_date - timedelta(days=days)
                past_rec = (
                    db.query(IndicatorValue)
                    .filter(
                        IndicatorValue.indicator_id == ind.id,
                        IndicatorValue.record_date <= cutoff_date,
                    )
                    .order_by(IndicatorValue.record_date.desc())
                    .first()
                )
                if not past_rec:
                    past_rec = (
                        db.query(IndicatorValue)
                        .filter(IndicatorValue.indicator_id == ind.id)
                        .order_by(IndicatorValue.record_date.asc())
                        .first()
                    )

            if past_rec and past_rec.value is not None:
                period_change = compute_relative_change(latest_val.value, past_rec.value)
            else:
                period_change = 0.0

        # Construct Sparkline data tailored to chosen timeframe
        if range_upper in ("1D", "1W"):
            recent_values = (
                db.query(IndicatorValue.value)
                .filter(IndicatorValue.indicator_id == ind.id)
                .order_by(IndicatorValue.record_date.desc())
                .limit(14)
                .all()
            )
            sparkline = [float(v[0]) for v in reversed(recent_values)]
        else:
            spark_query = db.query(IndicatorValue.value, IndicatorValue.record_date).filter(
                IndicatorValue.indicator_id == ind.id
            )
            if range_upper in RANGE_DAYS:
                days = RANGE_DAYS[range_upper]
                spark_query = spark_query.filter(
                    IndicatorValue.record_date >= anchor_date - timedelta(days=days)
                )

            pts = spark_query.order_by(IndicatorValue.record_date.asc()).all()
            raw_vals = [float(p[0]) for p in pts]

            if len(raw_vals) <= 25:
                sparkline = raw_vals
            else:
                # Downsample uniformly to 25 representative points
                n_pts = len(raw_vals)
                indices = [int(round(k * (n_pts - 1) / 24)) for k in range(25)]
                sparkline = [raw_vals[idx] for idx in indices]

        results.append({
            "id": ind.id,
            "symbol": ind.symbol,
            "name_vi": ind.name_vi,
            "name_en": ind.name_en,
            "category": ind.category,
            "unit": ind.unit,
            "frequency": ind.frequency,
            "priority": ind.priority,
            "latest_value": latest_val.value,
            "change_1d": latest_val.change_1d,
            "change_1w": latest_val.change_1w,
            "change_1m": latest_val.change_1m,
            "period_change": period_change,
            "range": range_upper,
            "trend_state": latest_val.trend_state if latest_val.trend_state else "NEUTRAL",
            "record_date": latest_val.record_date.isoformat(),
            "sparkline": sparkline,
        })

    return ApiResponse(status="success", data=results)


@router.get("/{indicator_id}/history", response_model=ApiResponse[Dict[str, Any]], summary="Get indicator historical series")
def get_indicator_history(
    indicator_id: str,
    timeframe: str = Query("1M", alias="range", description="Time range filter: 1W, 1M, 1Q, 3M, 1Y, 2Y, 3Y, ALL"),
    db: Session = Depends(get_db),
):
    """
    Retrieve historical time series data (date, value, ma_20, ma_50) for interactive charting.
    Supports: 1W, 1M, 1Q, 3M, 1Y, 2Y, 3Y, ALL.
    """
    indicator = db.query(Indicator).filter(Indicator.id == indicator_id.upper()).first()
    if not indicator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator '{indicator_id}' not found",
        )

    query = db.query(IndicatorValue).filter(IndicatorValue.indicator_id == indicator.id)

    # Determine anchor date (latest observation date or fallback to today)
    latest_rec = (
        db.query(IndicatorValue.record_date)
        .filter(IndicatorValue.indicator_id == indicator.id)
        .order_by(IndicatorValue.record_date.desc())
        .first()
    )
    anchor_date = latest_rec[0] if latest_rec else date.today()

    range_upper = timeframe.upper()

    if range_upper in RANGE_DAYS:
        days = RANGE_DAYS[range_upper]
        query = query.filter(IndicatorValue.record_date >= anchor_date - timedelta(days=days))
    # "ALL" applies no cutoff

    history_records = query.order_by(IndicatorValue.record_date.asc()).all()

    series_data = [
        {
            "date": rec.record_date.isoformat(),
            "value": rec.value,
            "ma_20": rec.ma_20,
            "ma_50": rec.ma_50,
            "change_1d": rec.change_1d,
        }
        for rec in history_records
    ]

    return ApiResponse(
        status="success",
        data={
            "indicator_id": indicator.id,
            "name_vi": indicator.name_vi,
            "unit": indicator.unit,
            "range": range_upper,
            "data": series_data,
        },
    )
