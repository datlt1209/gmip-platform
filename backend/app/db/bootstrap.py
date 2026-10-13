"""
Database Bootstrap and Initial Seeding Helper for GMIP.
Automatically seeds master indicators, generates 1,100-day (~3 years) historical time-series,
precomputes moving averages & trend metrics with high-performance bulk insertion,
and generates 7 daily reports on fresh database startup.
Essential for Render Cloud container cold-starts and 1Q/1Y/2Y/3Y multi-period filtering.
"""

from datetime import date, timedelta
import logging
import math
from typing import Dict, List
from sqlalchemy.orm import Session

from app.db.models import Indicator, IndicatorValue, DataSource
from app.core.analytics.calculator import classify_trend_state
from app.core.reporting.generator import DailyReportGenerator
from scripts.seed_data import DATA_SOURCES, INDICATORS

logger = logging.getLogger(__name__)

# Base market figures for realistic synthetic 1,100-day series
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


def bootstrap_database_if_empty(db: Session, force: bool = False) -> bool:
    """
    Check if the indicators catalog is empty or force re-seed.
    If empty (or force=True), seed 3 data sources, 24 indicators, 1,100 days (~3 years)
    of historical observations with precomputed MA20, MA50, changes, and generate 7 reports.

    Returns:
        True if bootstrapping was executed, False if database already contained data.
    """
    count = db.query(Indicator).count()
    if count > 0 and not force:
        val_count = db.query(IndicatorValue).count()
        # If indicators exist and have at least 1,000 points, consider it ready
        if val_count >= 1000:
            logger.info("Database already initialized with %d indicators and %d values. Skipping bootstrap.", count, val_count)
            return False

    logger.info("Fresh/re-seed database detected. Commencing 1,100-day bulk bootstrap for cloud deployment...")

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

    # Clean existing values if re-seeding
    if force:
        db.query(IndicatorValue).delete()
        db.commit()

    # 3. Generate 1,100 days (~3 years) of realistic historical observations
    today = date.today()
    indicators = db.query(Indicator).all()
    all_objects: List[IndicatorValue] = []

    DAYS_COUNT = 1100

    for ind in indicators:
        base_val = BASE_VALUES.get(ind.id, 100.0)
        is_rates = ind.category == "RATES"
        is_fx = ind.category == "FX"
        is_macro = ind.category == "MACRO"

        # Generate continuous series of 1,100 price points
        dates = []
        vals = []
        for i in range(DAYS_COUNT):
            rec_date = today - timedelta(days=(DAYS_COUNT - 1 - i))
            dates.append(rec_date)

            drift = (i / float(DAYS_COUNT)) * 0.15  # 15% 3-year drift
            if is_rates:
                fluc = math.sin(i / 30.0) * 0.35 + math.sin(i / 7.0) * 0.08
                val = round(max(0.01, base_val + fluc - (drift * 0.4)), 2)
                if ind.id == "US_10Y_02Y_SPREAD":
                    val = round(base_val + math.sin(i / 40.0) * 8.0 + math.sin(i / 9.0) * 2.0, 1)
            elif is_fx and ind.id in ("EUR_USD", "USD_JPY"):
                fluc = math.sin(i / 50.0) * 0.035 + math.sin(i / 8.0) * 0.01
                val = round(max(0.5, base_val + fluc + (drift * 0.02)), 4)
            elif is_fx and ind.id == "USD_VND":
                val = round(base_val + (i * 0.75), 1)
            elif is_macro:
                fluc = math.sin(i / 60.0) * 0.25 + math.sin(i / 15.0) * 0.05
                val = round(max(0.0, base_val + fluc), 2)
            else:
                pct = math.sin(i / 45.0) * 0.07 + math.sin(i / 10.0) * 0.02 + drift
                val = round(base_val * (1.0 + pct), 2)

            vals.append(val)

        # Precompute prefix sum array for O(1) Moving Average queries
        prefix_sum = [0.0] * (DAYS_COUNT + 1)
        for idx, v in enumerate(vals):
            prefix_sum[idx + 1] = prefix_sum[idx] + v

        # Construct all IndicatorValue records with precomputed metrics
        for i in range(DAYS_COUNT):
            curr_v = vals[i]

            # 1D change
            chg_1d = None
            if i >= 1:
                prev_v = vals[i - 1]
                if is_rates:
                    chg_1d = round((curr_v - prev_v) * 100.0, 1)
                elif prev_v > 0:
                    chg_1d = round(((curr_v - prev_v) / prev_v) * 100.0, 2)

            # 1W change (~5 sessions)
            chg_1w = None
            if i >= 5:
                prev_5 = vals[i - 5]
                if is_rates:
                    chg_1w = round((curr_v - prev_5) * 100.0, 1)
                elif prev_5 > 0:
                    chg_1w = round(((curr_v - prev_5) / prev_5) * 100.0, 2)

            # 1M change (~21 sessions)
            chg_1m = None
            if i >= 21:
                prev_21 = vals[i - 21]
                if is_rates:
                    chg_1m = round((curr_v - prev_21) * 100.0, 1)
                elif prev_21 > 0:
                    chg_1m = round(((curr_v - prev_21) / prev_21) * 100.0, 2)

            # YoY change (~252 sessions)
            chg_yoy = None
            if i >= 252:
                prev_252 = vals[i - 252]
                if prev_252 > 0:
                    chg_yoy = round(((curr_v - prev_252) / prev_252) * 100.0, 2)

            # Moving Averages
            ma_20 = None
            if i >= 19:
                sum_20 = prefix_sum[i + 1] - prefix_sum[i - 19]
                ma_20 = round(sum_20 / 20.0, 2)

            ma_50 = None
            if i >= 49:
                sum_50 = prefix_sum[i + 1] - prefix_sum[i - 49]
                ma_50 = round(sum_50 / 50.0, 2)

            # Trend state classification
            trend = classify_trend_state(chg_1d, is_rates=is_rates)

            all_objects.append(
                IndicatorValue(
                    indicator_id=ind.id,
                    record_date=dates[i],
                    value=curr_v,
                    change_1d=chg_1d,
                    change_1w=chg_1w,
                    change_1m=chg_1m,
                    change_yoy=chg_yoy,
                    ma_20=ma_20,
                    ma_50=ma_50,
                    trend_state=trend,
                    source_used=ind.primary_source_id,
                )
            )

    # Bulk insert all 26,400 observations in 1 rapid transaction
    db.bulk_save_objects(all_objects)
    db.commit()
    logger.info("Successfully bulk inserted %d historical data points across 1,100 days (~3 years).", len(all_objects))

    # 4. Generate 7 daily reports for the past week
    generator = DailyReportGenerator(db=db)
    reports_created = 0
    for j in range(7):
        rep_date = today - timedelta(days=(6 - j))
        generator.generate_daily_report(report_date=rep_date)
        reports_created += 1

    logger.info("Bootstrap complete: Generated %d daily reports ready for instant serving.", reports_created)
    return True
