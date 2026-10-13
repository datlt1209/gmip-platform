"""
Unit Tests for Macroeconomic Signals and Risk Engine (signals.py).
Tests Inverted Yield Curve, VIX panic threshold, Energy price shock, and risk aggregation.
"""

from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.analytics.signals import (
    check_inverted_yield_curve,
    check_vix_extreme_fear,
    check_energy_price_shock,
    evaluate_macro_signals,
)
from app.db.database import Base
from app.db.models import Indicator, IndicatorValue, DataSource


@pytest.fixture
def signal_test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed data sources
    session.add(DataSource(id="YAHOO", name="Yahoo", base_url="https://yahoo", is_active=True))
    session.add(DataSource(id="FRED", name="FRED", base_url="https://fred", is_active=True))

    # Seed indicators needed for signals
    indicators = [
        Indicator(id="US_10Y_02Y_SPREAD", symbol="T10Y2Y", name_vi="Spread", name_en="Spread", category="RATES", unit="bps", primary_source_id="FRED"),
        Indicator(id="US_10Y_YIELD", symbol="^TNX", name_vi="10Y", name_en="10Y", category="RATES", unit="%", primary_source_id="YAHOO"),
        Indicator(id="US_02Y_YIELD", symbol="^IRX", name_vi="2Y", name_en="2Y", category="RATES", unit="%", primary_source_id="YAHOO"),
        Indicator(id="VIX", symbol="^VIX", name_vi="VIX", name_en="VIX", category="SENTIMENT", unit="Points", primary_source_id="YAHOO"),
        Indicator(id="BRENT_OIL", symbol="BZ=F", name_vi="Brent", name_en="Brent", category="COMMODITY", unit="USD", primary_source_id="YAHOO"),
        Indicator(id="WTI_OIL", symbol="CL=F", name_vi="WTI", name_en="WTI", category="COMMODITY", unit="USD", primary_source_id="YAHOO"),
    ]
    session.add_all(indicators)
    session.commit()

    yield session
    session.close()


def test_individual_signal_detectors():
    # 1. Inverted yield curve
    assert check_inverted_yield_curve(spread_val=-0.15) is not None
    assert "Đường cong lợi suất đảo ngược" in check_inverted_yield_curve(spread_val=-0.15)
    assert check_inverted_yield_curve(spread_val=0.20) is None
    # 10Y < 2Y direct difference
    assert check_inverted_yield_curve(yield_10y=3.80, yield_02y=4.10) is not None

    # 2. VIX Extreme Fear
    assert check_vix_extreme_fear(32.5) is not None
    assert "vượt ngưỡng 30 điểm" in check_vix_extreme_fear(32.5)
    assert check_vix_extreme_fear(18.0) is None

    # 3. Energy Price Shock
    assert check_energy_price_shock(brent_change_1d=4.5) is not None
    assert "Giá dầu biến động đột biến" in check_energy_price_shock(brent_change_1d=4.5)
    assert check_energy_price_shock(brent_change_1d=2.1, wti_change_1d=1.5) is None


def test_evaluate_macro_signals_high_risk(signal_test_db):
    test_date = date(2026, 10, 13)

    # Insert high risk scenario: Inverted spread (-12 bps) and VIX = 32.0
    signal_test_db.add(IndicatorValue(indicator_id="US_10Y_02Y_SPREAD", record_date=test_date, value=-12.0, source_used="FRED"))
    signal_test_db.add(IndicatorValue(indicator_id="VIX", record_date=test_date, value=32.0, change_1d=12.5, source_used="YAHOO"))
    signal_test_db.commit()

    assessment = evaluate_macro_signals(signal_test_db, target_date=test_date)
    assert assessment.risk_level == "HIGH"
    assert len(assessment.active_warnings) >= 2


def test_evaluate_macro_signals_low_risk(signal_test_db):
    test_date = date(2026, 10, 13)

    # Insert low risk scenario: Positive spread (+25 bps), calm VIX (14.5), stable oil (+0.5%)
    signal_test_db.add(IndicatorValue(indicator_id="US_10Y_02Y_SPREAD", record_date=test_date, value=25.0, source_used="FRED"))
    signal_test_db.add(IndicatorValue(indicator_id="VIX", record_date=test_date, value=14.5, change_1d=-1.5, source_used="YAHOO"))
    signal_test_db.add(IndicatorValue(indicator_id="BRENT_OIL", record_date=test_date, value=82.0, change_1d=0.5, source_used="YAHOO"))
    signal_test_db.commit()

    assessment = evaluate_macro_signals(signal_test_db, target_date=test_date)
    assert assessment.risk_level == "LOW"
    assert len(assessment.active_warnings) == 0
