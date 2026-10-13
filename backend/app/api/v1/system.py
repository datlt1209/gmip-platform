"""
System Status and Health Check API Router.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db
from app.db.schemas import HealthResponse

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health", response_model=HealthResponse, summary="Perform system health check")
def health_check(db: Session = Depends(get_db)):
    """
    Check API status, DB connectivity and system readiness.
    """
    db_status = "connected"
    try:
        # Perform lightweight connection check
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    return HealthResponse(
        status="healthy" if "unhealthy" not in db_status else "degraded",
        version="1.0.0",
        database=db_status,
        timestamp=datetime.now(timezone.utc),
    )
