"""
Daily Reports API Router.
Provides endpoints for retrieving latest published daily report (with snapshot),
paginated archive reports list, and specific report details according to docs/SRS.md Section 9.1.
"""

from datetime import date
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import DailyReport, IndicatorValue
from app.db.schemas import ApiResponse

router = APIRouter(prefix="/reports", tags=["Daily Reports"])


@router.get("/latest", response_model=ApiResponse[Dict[str, Any]], summary="Get latest published daily report")
def get_latest_report(db: Session = Depends(get_db)):
    """
    Retrieve the most recent published daily report with executive snapshot metrics.
    """
    report = (
        db.query(DailyReport)
        .filter(DailyReport.status == "PUBLISHED")
        .order_by(DailyReport.report_date.desc())
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No published daily report found",
        )

    # Build snapshot array of key market indicators
    key_symbols = ["SP500", "NASDAQ100", "DXY", "US_10Y_YIELD", "BRENT_OIL", "GOLD", "VIX"]
    snapshot_items: List[Dict[str, Any]] = []

    for sym in key_symbols:
        val_rec = (
            db.query(IndicatorValue)
            .filter(
                IndicatorValue.indicator_id == sym,
                IndicatorValue.record_date <= report.report_date,
            )
            .order_by(IndicatorValue.record_date.desc())
            .first()
        )
        if val_rec:
            snapshot_items.append({
                "symbol": sym,
                "value": val_rec.value,
                "change_1d": val_rec.change_1d,
                "trend_state": val_rec.trend_state,
            })

    return ApiResponse(
        status="success",
        data={
            "id": report.id,
            "report_date": report.report_date.isoformat(),
            "title": report.title,
            "summary": report.summary,
            "risk_level": report.risk_level,
            "status": report.status,
            "published_at": report.published_at.isoformat() if report.published_at else None,
            "content_markdown": report.content_markdown,
            "snapshot": snapshot_items,
        },
    )



@router.get("", response_model=ApiResponse[Dict[str, Any]], summary="List archive reports with pagination")
def list_reports(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    from_date: Optional[date] = Query(None, description="Start date filter"),
    to_date: Optional[date] = Query(None, description="End date filter"),
    db: Session = Depends(get_db),
):
    """
    List historical reports for archive navigation and calendar search.
    """
    query = db.query(DailyReport).filter(DailyReport.status == "PUBLISHED")
    if from_date:
        query = query.filter(DailyReport.report_date >= from_date)
    if to_date:
        query = query.filter(DailyReport.report_date <= to_date)

    total = query.count()
    reports = (
        query.order_by(DailyReport.report_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": r.id,
            "report_date": r.report_date.isoformat(),
            "title": r.title,
            "summary": r.summary,
            "risk_level": r.risk_level,
            "status": r.status,
            "published_at": r.published_at.isoformat() if r.published_at else None,
        }
        for r in reports
    ]

    return ApiResponse(
        status="success",
        data={
            "total": total,
            "page": page,
            "limit": limit,
            "items": items,
        },
    )


@router.get("/{report_id}", response_model=ApiResponse[Dict[str, Any]], summary="Get specific report by ID or date")
def get_report_by_id(report_id: str, db: Session = Depends(get_db)):
    """
    Retrieve full report content by ID (e.g. REPORT-20261013) or date string (2026-10-13).
    """
    query = db.query(DailyReport)
    if report_id.startswith("REPORT-"):
        query = query.filter(DailyReport.id == report_id)
    else:
        try:
            target_date = date.fromisoformat(report_id)
            query = query.filter(DailyReport.report_date == target_date)
        except ValueError:
            query = query.filter(DailyReport.id == report_id)

    report = query.first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found",
        )

    # Build snapshot array of key market indicators up to report date
    key_symbols = ["SP500", "NASDAQ100", "DXY", "US_10Y_YIELD", "BRENT_OIL", "GOLD", "VIX"]
    snapshot_items: List[Dict[str, Any]] = []

    for sym in key_symbols:
        val_rec = (
            db.query(IndicatorValue)
            .filter(
                IndicatorValue.indicator_id == sym,
                IndicatorValue.record_date <= report.report_date,
            )
            .order_by(IndicatorValue.record_date.desc())
            .first()
        )
        if val_rec:
            snapshot_items.append({
                "symbol": sym,
                "value": val_rec.value,
                "change_1d": val_rec.change_1d,
                "trend_state": val_rec.trend_state,
            })

    return ApiResponse(
        status="success",
        data={
            "id": report.id,
            "report_date": report.report_date.isoformat(),
            "title": report.title,
            "summary": report.summary,
            "risk_level": report.risk_level,
            "status": report.status,
            "content_markdown": report.content_markdown,
            "published_at": report.published_at.isoformat() if report.published_at else None,
            "snapshot": snapshot_items,
        },
    )
