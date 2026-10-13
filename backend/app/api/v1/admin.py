"""
Admin Management API Router.
Provides administrative actions: manual ingestion triggers and on-demand report generation.
Protected by X-Admin-Key authorization header.
"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db
from app.db.models import Indicator
from app.db.schemas import ApiResponse
from app.core.ingestion.fallback import FailoverCoordinator
from app.core.analytics.calculator import update_indicator_metrics_in_db
from app.core.reporting.generator import DailyReportGenerator

router = APIRouter(prefix="/admin", tags=["Admin"])
settings = get_settings()


def verify_admin_key(
    x_admin_api_key: Optional[str] = Header(None, description="Admin API authorization secret key (SRS)"),
    x_admin_key: Optional[str] = Header(None, description="Admin authorization secret key alias"),
):
    """Verify admin secret key header (supports both X-Admin-Api-Key and X-Admin-Key)."""
    provided_key = x_admin_api_key or x_admin_key
    if not provided_key or provided_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrative secret key",
        )


@router.post("/trigger/crawl", response_model=ApiResponse[dict], summary="Trigger manual data ingestion")
@router.post("/ingest", response_model=ApiResponse[dict], summary="Trigger manual data ingestion alias")
def trigger_crawl(
    x_admin_api_key: Optional[str] = Header(None, description="Admin API authorization secret key"),
    x_admin_key: Optional[str] = Header(None, description="Admin authorization secret key alias"),
    db: Session = Depends(get_db),
):
    """Trigger an on-demand data fetch pipeline across all active indicators."""
    verify_admin_key(x_admin_api_key=x_admin_api_key, x_admin_key=x_admin_key)

    coordinator = FailoverCoordinator()
    summary = coordinator.ingest_all(db=db, delay_between_requests=0.1)

    # Recalculate metrics
    indicators = db.query(Indicator).filter(Indicator.is_active == True).all()
    for ind in indicators:
        update_indicator_metrics_in_db(ind.id, db)

    return ApiResponse(
        status="success",
        data={
            "message": "Ingestion job completed successfully",
            "summary": summary,
        },
    )


@router.post("/trigger/report", response_model=ApiResponse[dict], summary="Trigger manual report generation")
@router.post("/generate-report", response_model=ApiResponse[dict], summary="Trigger manual report generation alias")
def trigger_report(
    report_date: Optional[date] = Query(None, description="Optional target report date (YYYY-MM-DD)"),
    x_admin_api_key: Optional[str] = Header(None, description="Admin API authorization secret key"),
    x_admin_key: Optional[str] = Header(None, description="Admin authorization secret key alias"),
    db: Session = Depends(get_db),
):
    """Trigger an on-demand report compilation job."""
    verify_admin_key(x_admin_api_key=x_admin_api_key, x_admin_key=x_admin_key)

    generator = DailyReportGenerator(db=db)
    report = generator.generate_daily_report(report_date=report_date)

    return ApiResponse(
        status="success",
        data={
            "message": "Report generated successfully",
            "report_id": report.id,
            "report_date": report.report_date.isoformat(),
            "risk_level": report.risk_level,
        },
    )
