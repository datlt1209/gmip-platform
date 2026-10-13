"""
Indicators API Router.
Provides endpoints for retrieving indicator catalogs with latest values & sparklines,
as well as historical time-series queries (1W, 1M, 3M, 1Y, ALL) according to docs/SRS.md Section 9.1.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Indicator, IndicatorValue
from app.db.schemas import ApiResponse

router = APIRouter(prefix="/indicators", tags=["Indicators"])


@router.get("", response_model=ApiResponse[List[Dict[str, Any]]], summary="Get indicator catalog with latest metrics")
def get_indicators(
    category: Optional[str] = Query(None, description="Optional category filter (MACRO, RATES, FX, COMMODITY, EQUITY, SENTIMENT)"),
    db: Session = Depends(get_db),
):
    """
    Retrieve list of indicators with latest values, changes, and mini-sparklines.
    """
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

        # Fetch recent 10 values for sparkline
        recent_values = (
            db.query(IndicatorValue.value)
            .filter(IndicatorValue.indicator_id == ind.id)
            .order_by(IndicatorValue.record_date.desc())
            .limit(10)
            .all()
        )
        sparkline = [float(v[0]) for v in reversed(recent_values)]

        results.append({
            "id": ind.id,
            "symbol": ind.symbol,
            "name_vi": ind.name_vi,
            "name_en": ind.name_en,
            "category": ind.category,
            "unit": ind.unit,
            "frequency": ind.frequency,
            "priority": ind.priority,
            "latest_value": latest_val.value if latest_val else None,
            "change_1d": latest_val.change_1d if latest_val else None,
            "change_1w": latest_val.change_1w if latest_val else None,
            "change_1m": latest_val.change_1m if latest_val else None,
            "trend_state": latest_val.trend_state if latest_val else "NEUTRAL",
            "record_date": latest_val.record_date.isoformat() if latest_val else None,
            "sparkline": sparkline,
        })

    return ApiResponse(status="success", data=results)


@router.get("/{indicator_id}/history", response_model=ApiResponse[Dict[str, Any]], summary="Get indicator historical series")
def get_indicator_history(
    indicator_id: str,
    range: str = Query("1M", description="Time range filter: 1W, 1M, 3M, 1Y, ALL"),
    db: Session = Depends(get_db),
):
    """
    Retrieve historical time series data (date, value, ma_20, ma_50) for interactive charting.
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

    range_upper = range.upper()
    if range_upper == "1W":
        query = query.filter(IndicatorValue.record_date >= anchor_date - timedelta(days=7))
    elif range_upper == "1M":
        query = query.filter(IndicatorValue.record_date >= anchor_date - timedelta(days=30))
    elif range_upper == "3M":
        query = query.filter(IndicatorValue.record_date >= anchor_date - timedelta(days=90))
    elif range_upper == "1Y":
        query = query.filter(IndicatorValue.record_date >= anchor_date - timedelta(days=365))
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
