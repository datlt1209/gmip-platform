"""
Scheduler and Cron Jobs Module for GMIP.
Executes daily data ingestion at 06:00 AM and reporting generation at 06:30 AM (Asia/Ho_Chi_Minh).
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.db.database import SessionLocal
from app.db.models import Indicator
from app.core.ingestion.fallback import FailoverCoordinator
from app.core.analytics.calculator import update_indicator_metrics_in_db
from app.core.reporting.generator import DailyReportGenerator

logger = logging.getLogger(__name__)
settings = get_settings()

scheduler = BackgroundScheduler(timezone=settings.TIMEZONE)


def scheduled_ingestion_job():
    """Daily data ingestion job scheduled for 06:00 AM Asia/Ho_Chi_Minh."""
    logger.info("Executing scheduled daily macro data ingestion at 06:00 AM...")
    db = SessionLocal()
    try:
        coordinator = FailoverCoordinator()
        summary = coordinator.ingest_all(db=db, delay_between_requests=settings.INGESTION_RATE_LIMIT_DELAY)
        logger.info("Ingestion completed: %s", summary)

        # Update quantitative metrics and moving averages for each indicator
        indicators = db.query(Indicator).filter(Indicator.is_active == True).all()
        for ind in indicators:
            update_indicator_metrics_in_db(ind.id, db)
        logger.info("Updated analytical metrics (1D, 1W, 1M, MA20/50) for %d indicators.", len(indicators))
    except Exception as exc:
        logger.error("Error during scheduled ingestion job: %s", exc, exc_info=True)
    finally:
        db.close()


def scheduled_reporting_job():
    """Daily report generation job scheduled for 06:30 AM Asia/Ho_Chi_Minh."""
    logger.info("Executing scheduled daily report compilation at 06:30 AM...")
    db = SessionLocal()
    try:
        generator = DailyReportGenerator(db=db)
        report = generator.generate_daily_report()
        logger.info("Daily report '%s' generated successfully (Status: %s).", report.id, report.status)
    except Exception as exc:
        logger.error("Error during scheduled daily reporting job: %s", exc, exc_info=True)
    finally:
        db.close()


def start_scheduler():
    """Configure and start the background scheduler."""
    if scheduler.running:
        return

    # Ingestion job: Daily at 06:00 AM Asia/Ho_Chi_Minh
    scheduler.add_job(
        scheduled_ingestion_job,
        trigger=CronTrigger(hour=6, minute=0, timezone=settings.TIMEZONE),
        id="daily_macro_ingestion",
        name="Daily Macro Data Ingestion",
        replace_existing=True,
    )

    # Reporting job: Daily at 06:30 AM Asia/Ho_Chi_Minh
    scheduler.add_job(
        scheduled_reporting_job,
        trigger=CronTrigger(hour=6, minute=30, timezone=settings.TIMEZONE),
        id="daily_macro_reporting",
        name="Daily Macro Report Generator",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("GMIP Background Scheduler started (Ingestion: 06:00 AM, Reporting: 06:30 AM).")


def stop_scheduler():
    """Stop the background scheduler cleanly."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("GMIP Background Scheduler shut down.")
