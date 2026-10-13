"""
Quantitative Analytics and Trend Calculation Engine.
Calculates percentage changes (1D, 1W, 1M, YoY), basis points (bps) for rates,
Moving Averages (MA20, MA50), and trend state classifications according to docs/SRS.md Section 4.
"""

from datetime import date
import logging
from typing import List, Optional
import numpy as np
from sqlalchemy.orm import Session

from app.db.models import Indicator, IndicatorValue

logger = logging.getLogger(__name__)


def compute_relative_change(current_val: float, past_val: Optional[float]) -> Optional[float]:
    """
    Compute percentage change: ((P_t - P_past) / P_past) * 100.
    Returns None if past_val is None or non-positive.
    """
    if past_val is None or past_val == 0:
        return None
    return round(((current_val - past_val) / past_val) * 100.0, 2)


def compute_basis_points_change(current_val: float, past_val: Optional[float]) -> Optional[float]:
    """
    Compute basis points change for interest rates and yields: (P_t - P_past) * 100.
    """
    if past_val is None:
        return None
    return round((current_val - past_val) * 100.0, 1)


def compute_moving_average(values: List[float], window: int) -> Optional[float]:
    """
    Compute Simple Moving Average over the trailing `window` data points.
    Returns None if fewer than `window` points are available.
    """
    if len(values) < window:
        return None
    trailing_slice = values[-window:]
    return round(float(np.mean(trailing_slice)), 2)


def classify_trend_state(
    change_value: Optional[float],
    is_rates: bool = False,
) -> str:
    """
    Classify asset or rate trend state according to docs/SRS.md Section 4.2 table:

    Asset threshold (% change):
    - Strong Bullish: >= +2.0%
    - Bullish:        +0.5% <= delta < +2.0%
    - Neutral:        -0.5% < delta < +0.5%
    - Bearish:        -2.0% < delta <= -0.5%
    - Strong Bearish: <= -2.0%

    Rates threshold (bps change):
    - Strong Bullish: >= +15 bps
    - Bullish:        +5 <= delta < +15 bps
    - Neutral:        -5 < delta < +5 bps
    - Bearish:        -15 < delta <= -5 bps
    - Strong Bearish: <= -15 bps
    """
    if change_value is None:
        return "NEUTRAL"

    if is_rates:
        if change_value >= 15.0:
            return "STRONG_BULLISH"
        elif change_value >= 5.0:
            return "BULLISH"
        elif change_value > -5.0:
            return "NEUTRAL"
        elif change_value > -15.0:
            return "BEARISH"
        else:
            return "STRONG_BEARISH"
    else:
        if change_value >= 2.0:
            return "STRONG_BULLISH"
        elif change_value >= 0.5:
            return "BULLISH"
        elif change_value > -0.5:
            return "NEUTRAL"
        elif change_value > -2.0:
            return "BEARISH"
        else:
            return "STRONG_BEARISH"


def calculate_indicator_metrics(
    records: List[IndicatorValue],
    category: str = "",
) -> Optional[IndicatorValue]:
    """
    Calculate 1D, 1W, 1M, YoY, MA20, MA50, and trend_state for the latest record.
    The input list is sorted chronologically by record_date.
    """
    if not records:
        return None

    # Sort ascending by record date
    records.sort(key=lambda r: r.record_date)
    latest = records[-1]
    curr_val = latest.value
    n = len(records)
    is_rates = category.upper() == "RATES"

    # Extract clean list of numeric values
    all_values = [r.value for r in records]

    # 1-Day Change (t - 1)
    if n >= 2:
        prev_val = records[-2].value
        latest.change_1d = (
            compute_basis_points_change(curr_val, prev_val)
            if is_rates
            else compute_relative_change(curr_val, prev_val)
        )
    else:
        latest.change_1d = 0.0

    # 1-Week Change (~5 trading sessions)
    idx_1w = max(0, n - 6)
    if n >= 6:
        val_1w = records[idx_1w].value
        latest.change_1w = (
            compute_basis_points_change(curr_val, val_1w)
            if is_rates
            else compute_relative_change(curr_val, val_1w)
        )

    # 1-Month Change (~21 trading sessions)
    idx_1m = max(0, n - 22)
    if n >= 22:
        val_1m = records[idx_1m].value
        latest.change_1m = (
            compute_basis_points_change(curr_val, val_1m)
            if is_rates
            else compute_relative_change(curr_val, val_1m)
        )

    # Year-over-Year Change (~252 sessions or closest ~365 days)
    if n >= 253:
        val_yoy = records[max(0, n - 253)].value
        latest.change_yoy = compute_relative_change(curr_val, val_yoy)
    else:
        # Fallback date-based search if sparse series (e.g. monthly macro)
        target_yoy_date = latest.record_date.replace(year=latest.record_date.year - 1)
        closest_rec = None
        min_diff = 45  # within 45 days window
        for r in records[:-1]:
            diff = abs((r.record_date - target_yoy_date).days)
            if diff < min_diff:
                min_diff = diff
                closest_rec = r
        if closest_rec:
            latest.change_yoy = compute_relative_change(curr_val, closest_rec.value)

    # Moving Averages
    latest.ma_20 = compute_moving_average(all_values, window=20)
    latest.ma_50 = compute_moving_average(all_values, window=50)

    # Trend State
    latest.trend_state = classify_trend_state(latest.change_1d, is_rates=is_rates)

    return latest


def update_indicator_metrics_in_db(indicator_id: str, db: Session) -> Optional[IndicatorValue]:
    """
    Fetch all historical records for an indicator from DB, compute quantitative metrics,
    and persist the updated latest record to the database.
    """
    indicator = db.query(Indicator).filter(Indicator.id == indicator_id).first()
    if not indicator:
        logger.warning("Indicator '%s' not found in database.", indicator_id)
        return None

    records = (
        db.query(IndicatorValue)
        .filter(IndicatorValue.indicator_id == indicator_id)
        .order_by(IndicatorValue.record_date.asc())
        .all()
    )
    if not records:
        return None

    updated_latest = calculate_indicator_metrics(records, category=indicator.category)
    db.commit()
    db.refresh(updated_latest)
    return updated_latest
