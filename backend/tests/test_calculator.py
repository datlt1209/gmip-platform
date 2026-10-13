"""
Unit Tests for Quantitative Analytics Engine (calculator.py).
Tests relative change, bps change, moving averages, trend classification,
and metrics computation across historical series.
"""

from datetime import date, timedelta
import pytest

from app.core.analytics.calculator import (
    compute_relative_change,
    compute_basis_points_change,
    compute_moving_average,
    classify_trend_state,
    calculate_indicator_metrics,
)
from app.db.models import IndicatorValue


def test_compute_relative_change():
    assert compute_relative_change(105.0, 100.0) == 5.0
    assert compute_relative_change(95.0, 100.0) == -5.0
    assert compute_relative_change(100.0, 100.0) == 0.0
    assert compute_relative_change(100.0, 0.0) is None
    assert compute_relative_change(100.0, None) is None


def test_compute_basis_points_change():
    # 4.20% to 4.25% is +5.0 bps
    assert compute_basis_points_change(4.25, 4.20) == 5.0
    # 4.25% to 4.10% is -15.0 bps
    assert compute_basis_points_change(4.10, 4.25) == -15.0
    assert compute_basis_points_change(4.25, None) is None


def test_compute_moving_average():
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert compute_moving_average(values, 3) == 40.0  # (30+40+50)/3
    assert compute_moving_average(values, 5) == 30.0
    assert compute_moving_average(values, 10) is None  # Insufficient data points


def test_classify_trend_state_assets():
    # Non-rate asset thresholds (% change)
    assert classify_trend_state(2.5, is_rates=False) == "STRONG_BULLISH"
    assert classify_trend_state(2.0, is_rates=False) == "STRONG_BULLISH"
    assert classify_trend_state(1.2, is_rates=False) == "BULLISH"
    assert classify_trend_state(0.5, is_rates=False) == "BULLISH"
    assert classify_trend_state(0.2, is_rates=False) == "NEUTRAL"
    assert classify_trend_state(-0.2, is_rates=False) == "NEUTRAL"
    assert classify_trend_state(-0.5, is_rates=False) == "BEARISH"
    assert classify_trend_state(-1.5, is_rates=False) == "BEARISH"
    assert classify_trend_state(-2.0, is_rates=False) == "STRONG_BEARISH"
    assert classify_trend_state(-3.5, is_rates=False) == "STRONG_BEARISH"


def test_classify_trend_state_rates():
    # Rates thresholds (bps change)
    assert classify_trend_state(16.0, is_rates=True) == "STRONG_BULLISH"
    assert classify_trend_state(15.0, is_rates=True) == "STRONG_BULLISH"
    assert classify_trend_state(8.5, is_rates=True) == "BULLISH"
    assert classify_trend_state(5.0, is_rates=True) == "BULLISH"
    assert classify_trend_state(2.0, is_rates=True) == "NEUTRAL"
    assert classify_trend_state(-4.0, is_rates=True) == "NEUTRAL"
    assert classify_trend_state(-5.0, is_rates=True) == "BEARISH"
    assert classify_trend_state(-10.0, is_rates=True) == "BEARISH"
    assert classify_trend_state(-15.0, is_rates=True) == "STRONG_BEARISH"
    assert classify_trend_state(-20.0, is_rates=True) == "STRONG_BEARISH"


def test_calculate_indicator_metrics_series():
    # Create synthetic series of 25 observations
    base_date = date(2026, 9, 1)
    records = []
    for i in range(25):
        rec_date = base_date + timedelta(days=i)
        val = 5000.0 + (i * 10.0)  # increasing series: 5000 to 5240
        records.append(
            IndicatorValue(
                indicator_id="SP500",
                record_date=rec_date,
                value=val,
                source_used="YAHOO",
            )
        )

    latest = calculate_indicator_metrics(records, category="EQUITY")
    assert latest is not None
    assert latest.value == 5240.0

    # 1D change: (5240 - 5230) / 5230 * 100 = 10 / 5230 ~ +0.19% (NEUTRAL)
    assert latest.change_1d == 0.19
    assert latest.trend_state == "NEUTRAL"

    # MA20 should be computed
    assert latest.ma_20 is not None
    # 20 points from index 5 (5050) to 24 (5240): mean is 5145.0
    assert latest.ma_20 == 5145.0

    # MA50 should be None since we only have 25 points
    assert latest.ma_50 is None
