"""
Database Bootstrap and Initial Seeding Helper for GMIP.
Automatically seeds master indicators, generates 60-day historical time-series,
calculates moving averages & trend metrics, and generates 7 daily reports on fresh database startup.
Essential for Render Cloud container cold-starts.
"""

from datetime import date, timedelta
import logging
import math
from typing import Dict
from sqlalchemy.orm import Session

from app.db.models import Indicator, IndicatorValue, DataSource
from app.core.analytics.calculator import update_indicator_metrics_in_db
from app.core.reporting.generator import DailyReportGenerator
from scripts.seed_data import DATA_SOURCES, INDICATORS

logger = logging.getLogger(__name__)

# Base market figures for realistic synthetic 60-day series
BASE_VALUES: Dict[str, float] = {
    "SP500": 5800.0,
    "NASDAQ100": 20200.0,
    "DOW_JONES": 42500.0,
    "NIKKEI225": 39500.0,
    "DXY": 102.5,
    "EUR_USD": 1.085,
    "USD_JPY": 149.5,
    "USD_VND": 25300.0,
    "BRENT_OIL": 82.5,
    "WTI_OIL": 78.0,
    "GOLD": 2650.0,
    "COPPER": 4.40,
    "FED_FUNDS_RATE": 4.83,
    "US_10Y_YIELD": 4.12,
    "US_02Y_YIELD": 3.95,
    "US_10Y_02Y_SPREAD": 17.0,
    "ECB_DEPOSIT_RATE": 3.50,
    "US_CPI_YOY": 2.4,
    "US_CORE_CPI_YOY": 3.3,
    "US_GDP_QOQ": 2.8,
    "US_UNEMP_RATE": 4.1,
    "US_NONFARM_PAYROLL": 254.0,
    "US_MANUF_PMI": 47.2,
    "VIX": 16.2,
}


def bootstrap_database_if_empty(db: Session) -> bool:
    """
    Check if the indicators catalog is empty.
    If empty, seed 3 data sources, 24 indicators, 60 days of historical data,
    compute quantitative metrics, and generate 7 daily reports.

    Returns:
        True if bootstrapping was executed, False if database already contained data.
    """
    count = db.query(Indicator).count()
    if count > 0:
        logger.info("Database already initialized with %d indicators. Skipping bootstrap.", count)
        return False

    logger.info("Fresh database detected. Commencing automatic bootstrap seeding for cloud deployment...")

    # 1. Seed Data Sources
    for src in DATA_SOURCES:
        existing = db.query(DataSource).filter_by(id=src["id"]).first()
        if not existing:
            db.add(DataSource(**src))
    db.commit()

    # 2. Seed 24 Indicators
    for ind in INDICATORS:
        existing = db.query(Indicator).filter_by(id=ind["id"]).first()
        if not existing:
            db.add(Indicator(**ind))
    db.commit()
    logger.info("Seeded 3 data sources and 24 indicators master catalog.")

    # 3. Generate 60 days of realistic historical observations
    today = date.today()
    indicators = db.query(Indicator).all()
    total_points = 0

    for ind in indicators:
        base_val = BASE_VALUES.get(ind.id, 100.0)
        is_rates = ind.category == "RATES"
        is_fx = ind.category == "FX"
        is_macro = ind.category == "MACRO"

        for i in range(60):
            record_date = today - timedelta(days=(59 - i))

            # Generate natural gentle fluctuation
            if is_rates:
                fluc = math.sin(i / 4.0) * 0.12 + ((i % 5) - 2) * 0.02
                val = round(max(0.01, base_val + fluc), 2)
                if ind.id == "US_10Y_02Y_SPREAD":
                    val = round(base_val + math.sin(i / 5.0) * 3.5, 1)
            elif is_fx and ind.id in ("EUR_USD", "USD_JPY"):
                fluc = math.sin(i / 6.0) * 0.015
                val = round(max(0.5, base_val + fluc), 4)
            elif is_fx and ind.id == "USD_VND":
                val = round(base_val + i * 3.0, 1)
            elif is_macro:
                fluc = math.sin(i / 8.0) * 0.15
                val = round(base_val + fluc, 2)
            else:
                pct = math.sin(i / 5.0) * 0.025 + ((i % 7) - 3) * 0.003
                val = round(base_val * (1.0 + pct), 2)

            val_rec = IndicatorValue(
                indicator_id=ind.id,
                record_date=record_date,
                value=val,
                source_used=ind.primary_source_id,
            )
            db.add(val_rec)
            total_points += 1

    db.commit()
    logger.info("Successfully generated %d historical data points across 60 days.", total_points)

    # 4. Compute quantitative analytics (MA20, MA50, 1D/1W/1M, trend_state)
    for ind in indicators:
        update_indicator_metrics_in_db(ind.id, db)
    logger.info("Calculated quantitative metrics and moving averages for all 24 indicators.")

    # 5. Generate 7 daily reports for the past week
    generator = DailyReportGenerator(db=db)
    reports_created = 0
    for j in range(7):
        rep_date = today - timedelta(days=(6 - j))
        generator.generate_daily_report(report_date=rep_date)
        reports_created += 1

    logger.info("Bootstrap complete: Generated %d daily reports ready for instant serving.", reports_created)
    return True
