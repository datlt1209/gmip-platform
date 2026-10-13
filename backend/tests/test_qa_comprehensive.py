"""
Comprehensive QA & Test Automation Suite for GMIP (Sprint 2, Sprint 3, Sprint 5).
Covers:
- [TASK-09] Unit Tests for Fetchers (FRED, Yahoo, Stooq), Data Sanitizer, and Failover Coordinator.
- [TASK-10 & 11] Quantitative Analytics & Risk Signal Detectors with hand-calculated ground-truth data.
- [TASK-13] Strict Data Lineage Verification (100% parity between DB `indicator_values` and generated Markdown report).
- [TASK-20] End-to-End Integration Pipeline (Mock Ingest -> Analytics -> Report Generation -> REST APIs & X-Admin-Api-Key Security).
- [TASK-22] NFR Performance & Latency Benchmark (< 300ms response time across all core API endpoints).
- [TASK-23] 3-Day Consecutive Dry Run Simulation (Day 1, Day 2, Day 3 automated pipeline stability & archive integrity).
"""

from datetime import date, timedelta
import math
import time
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.config import get_settings
from app.db.database import Base, get_db
from app.db.models import DataSource, Indicator, IndicatorValue, DailyReport, IngestionLog
from app.core.ingestion.base import DataPoint, validate_indicator_value
from app.core.ingestion.fred import FredFetcher, FredFetcherError
from app.core.ingestion.yahoo import YahooFetcher, YahooFetcherError
from app.core.ingestion.stooq import StooqFetcher, StooqFetcherError
from app.core.ingestion.fallback import FailoverCoordinator
from app.core.analytics.calculator import (
    compute_relative_change,
    compute_basis_points_change,
    compute_moving_average,
    classify_trend_state,
    calculate_indicator_metrics,
    update_indicator_metrics_in_db,
)
from app.core.analytics.signals import (
    check_inverted_yield_curve,
    check_vix_extreme_fear,
    check_energy_price_shock,
    evaluate_macro_signals,
)
from app.core.reporting.generator import DailyReportGenerator
from app.core.reporting.templates import format_value_str, format_change_str, format_trend_label
from scripts.seed_data import DATA_SOURCES, INDICATORS

settings = get_settings()


@pytest.fixture
def qa_db_session():
    """Isolated in-memory SQLite database seeded with all 3 data sources and 24 indicators."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    for src in DATA_SOURCES:
        session.add(DataSource(**src))
    for ind in INDICATORS:
        session.add(Indicator(**ind))
    session.commit()

    yield session
    session.close()


# ==============================================================================
# 1. [TASK-09] FETCHERS, DATA SANITIZER & FAILOVER COORDINATOR UNIT TESTS
# ==============================================================================
class TestTask09FetchersSanitizerAndFailover:
    """[TASK-09] Independent verification of Fetchers, Sanitizer rules, and Failover mechanism."""

    def test_data_sanitizer_blocks_nan_inf_none(self):
        """Sanitizer must reject None, NaN, +Inf, and -Inf."""
        assert validate_indicator_value("SP500", None, category="EQUITY")[0] is False
        assert validate_indicator_value("SP500", float("nan"), category="EQUITY")[0] is False
        assert validate_indicator_value("SP500", float("inf"), category="EQUITY")[0] is False
        assert validate_indicator_value("SP500", float("-inf"), category="EQUITY")[0] is False

    def test_data_sanitizer_blocks_negative_for_equities_commodities_fx_sentiment(self):
        """Sanitizer must reject <= 0 values for EQUITY, COMMODITY, FX, SENTIMENT, but allow negative RATES/MACRO."""
        for cat, ind_id in [
            ("EQUITY", "SP500"),
            ("COMMODITY", "BRENT_OIL"),
            ("FX", "EUR_USD"),
            ("SENTIMENT", "VIX"),
        ]:
            valid_neg, reason_neg = validate_indicator_value(ind_id, -10.5, category=cat)
            assert valid_neg is False
            assert "Non-positive value" in reason_neg

            valid_zero, _ = validate_indicator_value(ind_id, 0.0, category=cat)
            assert valid_zero is False

        # Negative values are valid for RATES (e.g., inverted yield spread) and MACRO (e.g., GDP contraction)
        assert validate_indicator_value("US_10Y_02Y_SPREAD", -0.35, category="RATES")[0] is True
        assert validate_indicator_value("US_GDP_QOQ", -1.2, category="MACRO")[0] is True

    def test_data_sanitizer_blocks_daily_jump_exceeding_50_percent(self):
        """Sanitizer must block daily spikes/drops > 50% for non-rate/non-macro assets."""
        # +50.0% exact boundary is allowed
        assert validate_indicator_value("BRENT_OIL", 120.0, prev_value=80.0, category="COMMODITY")[0] is True
        # +50.1% is blocked
        valid_up, reason_up = validate_indicator_value("BRENT_OIL", 120.08, prev_value=80.0, category="COMMODITY")
        assert valid_up is False
        assert "Extreme change detected" in reason_up

        # -55% drop is blocked
        valid_down, reason_down = validate_indicator_value("SP500", 2250.0, prev_value=5000.0, category="EQUITY")
        assert valid_down is False
        assert "Extreme change detected" in reason_down

    @patch("requests.get")
    def test_fred_yahoo_stooq_fetchers_isolated(self, mock_get):
        """Verify FRED, Yahoo REST, and Stooq CSV fetchers parse mocked payloads accurately."""
        # 1. FRED Fetcher
        fred_resp = MagicMock(status_code=200)
        fred_resp.json.return_value = {
            "observations": [
                {"date": "2026-10-10", "value": "2.40"},
                {"date": "2026-10-11", "value": "."},  # Missing marker
                {"date": "2026-10-12", "value": "2.45"},
            ]
        }
        mock_get.return_value = fred_resp
        fred = FredFetcher(api_key="qa_mock_key")
        fred_pts = fred.fetch_series("CPIAUCSL")
        assert len(fred_pts) == 2
        assert fred_pts[-1] == DataPoint(record_date=date(2026, 10, 12), value=2.45)

        # 2. Yahoo Fetcher
        yahoo_resp = MagicMock(status_code=200)
        yahoo_resp.json.return_value = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1791676800, 1791763200],
                        "indicators": {"quote": [{"close": [83.50, 84.20]}]},
                    }
                ]
            }
        }
        mock_get.return_value = yahoo_resp
        yahoo = YahooFetcher(throttle_seconds=0.0, backoff_delays=[0.0, 0.0, 0.0])
        yahoo_pts = yahoo._fetch_via_rest("BZ=F")
        assert len(yahoo_pts) == 2
        assert yahoo_pts[0].value == 83.50
        assert yahoo_pts[1].value == 84.20

        # 3. Stooq Fetcher
        stooq_resp = MagicMock(status_code=200)
        stooq_resp.text = (
            "Date,Open,High,Low,Close,Volume\n"
            "2026-10-11,2640.0,2655.0,2635.0,2648.5,5000\n"
            "2026-10-12,2648.5,2660.0,2645.0,2655.4,5200\n"
        )
        mock_get.return_value = stooq_resp
        stooq = StooqFetcher()
        stooq_pts = stooq.fetch_series("XAUUSD")
        assert len(stooq_pts) == 2
        assert stooq_pts[-1] == DataPoint(record_date=date(2026, 10, 12), value=2655.4)

    def test_failover_coordinator_yahoo_timeout_falls_back_to_stooq_and_logs(self, qa_db_session):
        """AC-06: When Yahoo Finance times out/errors, Coordinator automatically switches to Stooq and logs FALLBACK_SUCCESS."""
        mock_yahoo = MagicMock()
        mock_yahoo.fetch_series.side_effect = TimeoutError("Yahoo Finance request timed out after 10s")

        mock_stooq = MagicMock()
        mock_stooq.fetch_series.return_value = [
            DataPoint(record_date=date(2026, 10, 12), value=5815.20)
        ]

        coordinator = FailoverCoordinator(yahoo_fetcher=mock_yahoo, stooq_fetcher=mock_stooq)
        sp500_ind = qa_db_session.query(Indicator).filter_by(id="SP500").first()

        success, saved_rec, source_used = coordinator.ingest_indicator(sp500_ind, db=qa_db_session)

        assert success is True
        assert source_used == "STOOQ"
        assert saved_rec is not None
        assert saved_rec.value == 5815.20
        assert saved_rec.source_used == "STOOQ"

        logs = (
            qa_db_session.query(IngestionLog)
            .filter_by(indicator_id="SP500")
            .order_by(IngestionLog.id.asc())
            .all()
        )
        assert len(logs) == 2
        assert logs[0].source_id == "YAHOO"
        assert logs[0].status == "FAILED"
        assert "timed out" in logs[0].error_message.lower()
        assert logs[1].source_id == "STOOQ"
        assert logs[1].status == "FALLBACK_SUCCESS"


# ==============================================================================
# 2. [TASK-10 & 11] QUANTITATIVE CALCULATOR & RISK SIGNALS (HAND-CALCULATED)
# ==============================================================================
class TestTask10And11QuantitativeAndSignals:
    """[TASK-10 & 11] Hand-calculated verification of Δ1D, Δ1W, Δ1M, ΔYoY, bps, MA20, MA50, 5 trends & 3 risk signals."""

    def test_hand_calculated_metrics_full_260_day_series(self):
        """
        Hand-calculated series over 260 trading sessions:
        Let value at index i (0 <= i < 260) be: P_i = 1000.0 + 2.0 * i
        - Latest index t = 259 -> P_t = 1000.0 + 2 * 259 = 1518.0
        - 1D ago (t-1 = 258)   -> P_{t-1} = 1516.0 -> Δ1D = (1518 - 1516)/1516 * 100 = +0.1319% -> 0.13%
        - 1W ago (t-5 = 254)   -> P_{t-5} = 1508.0 -> Δ1W = (1518 - 1508)/1508 * 100 = +0.6631% -> 0.66%
        - 1M ago (t-21 = 238)  -> P_{t-21} = 1476.0 -> Δ1M = (1518 - 1476)/1476 * 100 = +2.8455% -> 2.85%
        - YoY ago (t-252 = 7)  -> P_{t-252} = 1014.0 -> ΔYoY = (1518 - 1014)/1014 * 100 = +49.7041% -> 49.70%
        - MA20 (indices 240..259): arithmetic mean of (1480.0 .. 1518.0) = (1480 + 1518) / 2 = 1499.00
        - MA50 (indices 210..259): arithmetic mean of (1420.0 .. 1518.0) = (1420 + 1518) / 2 = 1469.00
        """
        base_date = date(2026, 1, 1)
        records = [
            IndicatorValue(
                indicator_id="SP500",
                record_date=base_date + timedelta(days=i),
                value=1000.0 + 2.0 * i,
                source_used="YAHOO",
            )
            for i in range(260)
        ]

        latest = calculate_indicator_metrics(records, category="EQUITY")
        assert latest.value == 1518.0
        assert latest.change_1d == 0.13
        assert latest.change_1w == 0.66
        assert latest.change_1m == 2.85
        assert latest.change_yoy == 49.70
        assert latest.ma_20 == 1499.00
        assert latest.ma_50 == 1469.00
        assert latest.trend_state == "NEUTRAL"  # +0.13% is within (-0.5%, +0.5%)

    def test_hand_calculated_rates_bps_and_5_trend_levels(self):
        """Verify basis points (bps) calculation for RATES and all 5 trend classification boundaries."""
        # 4.12% -> 4.27% = +15.0 bps (STRONG_BULLISH)
        assert compute_basis_points_change(4.27, 4.12) == 15.0
        assert classify_trend_state(15.0, is_rates=True) == "STRONG_BULLISH"
        assert classify_trend_state(5.0, is_rates=True) == "BULLISH"
        assert classify_trend_state(4.9, is_rates=True) == "NEUTRAL"
        assert classify_trend_state(-4.9, is_rates=True) == "NEUTRAL"
        assert classify_trend_state(-5.0, is_rates=True) == "BEARISH"
        assert classify_trend_state(-14.9, is_rates=True) == "BEARISH"
        assert classify_trend_state(-15.0, is_rates=True) == "STRONG_BEARISH"

        # Asset percentage 5-level boundaries
        assert classify_trend_state(2.0, is_rates=False) == "STRONG_BULLISH"
        assert classify_trend_state(0.5, is_rates=False) == "BULLISH"
        assert classify_trend_state(0.49, is_rates=False) == "NEUTRAL"
        assert classify_trend_state(-0.49, is_rates=False) == "NEUTRAL"
        assert classify_trend_state(-0.5, is_rates=False) == "BEARISH"
        assert classify_trend_state(-1.99, is_rates=False) == "BEARISH"
        assert classify_trend_state(-2.0, is_rates=False) == "STRONG_BEARISH"

    def test_three_special_risk_signals_exact_thresholds(self, qa_db_session):
        """
        Verify SRS Section 4.3 risk triggers:
        1. Yield Curve Inversion: 10Y - 2Y < 0
        2. Extreme Market Volatility: VIX >= 30.0
        3. Energy Price Shock: Brent or WTI Δ1D >= +4.0%
        """
        # Boundary unit tests
        assert check_inverted_yield_curve(spread_val=-0.01) is not None
        assert check_inverted_yield_curve(spread_val=0.0) is None
        assert check_inverted_yield_curve(yield_10y=3.95, yield_02y=4.00) is not None

        assert check_vix_extreme_fear(30.0) is not None
        assert check_vix_extreme_fear(29.99) is None

        assert check_energy_price_shock(brent_change_1d=4.0, wti_change_1d=1.2) is not None
        assert check_energy_price_shock(brent_change_1d=1.0, wti_change_1d=4.0) is not None
        assert check_energy_price_shock(brent_change_1d=3.99, wti_change_1d=3.99) is None

        # Full DB signal evaluation with all 3 warnings triggered simultaneously
        target_dt = date(2026, 10, 13)
        qa_db_session.add_all([
            IndicatorValue(indicator_id="US_10Y_02Y_SPREAD", record_date=target_dt, value=-15.0, source_used="FRED"),
            IndicatorValue(indicator_id="VIX", record_date=target_dt, value=31.5, change_1d=18.0, source_used="YAHOO"),
            IndicatorValue(indicator_id="BRENT_OIL", record_date=target_dt, value=90.0, change_1d=4.25, source_used="YAHOO"),
        ])
        qa_db_session.commit()

        assessment = evaluate_macro_signals(qa_db_session, target_date=target_dt)
        assert assessment.risk_level == "HIGH"
        assert len(assessment.active_warnings) == 3


# ==============================================================================
# 3. [TASK-13] STRICT DATA LINEAGE VERIFICATION
# ==============================================================================
class TestTask13DataLineageIntegrity:
    """[TASK-13] Verify 100% of figures in generated report match `indicator_values` records in DB."""

    def test_report_markdown_and_snapshot_match_database_100_percent(self, qa_db_session):
        report_dt = date(2026, 10, 13)
        ground_truth = {
            "SP500": (5815.20, 0.61, 1.25, "BULLISH"),
            "NASDAQ100": (20240.10, 0.85, 1.80, "BULLISH"),
            "DOW_JONES": (42850.50, 0.42, 0.95, "NEUTRAL"),
            "NIKKEI225": (39120.00, 1.12, 2.30, "BULLISH"),
            "DXY": (102.85, 0.22, 0.55, "NEUTRAL"),
            "EUR_USD": (1.0925, -0.18, -0.40, "NEUTRAL"),
            "USD_JPY": (149.20, 0.31, 0.85, "NEUTRAL"),
            "USD_VND": (25340.00, 0.12, 0.25, "NEUTRAL"),
            "BRENT_OIL": (84.20, -0.45, 2.10, "NEUTRAL"),
            "WTI_OIL": (80.15, -0.52, 1.95, "BEARISH"),
            "GOLD": (2655.40, 0.35, 0.90, "NEUTRAL"),
            "COPPER": (4.4200, 0.68, 1.40, "BULLISH"),
            "FED_FUNDS_RATE": (4.83, 0.0, 0.0, "NEUTRAL"),
            "US_10Y_YIELD": (4.15, 3.20, 8.50, "NEUTRAL"),
            "US_02Y_YIELD": (3.98, 2.10, 5.00, "NEUTRAL"),
            "US_10Y_02Y_SPREAD": (17.0, 1.10, 3.50, "NEUTRAL"),
            "US_CPI_YOY": (2.40, 0.0, 0.0, "NEUTRAL"),
            "US_CORE_CPI_YOY": (3.20, 0.0, 0.0, "NEUTRAL"),
            "US_UNEMP_RATE": (4.10, 0.0, 0.0, "NEUTRAL"),
            "VIX": (15.40, -3.20, -6.50, "STRONG_BEARISH"),
        }

        for ind_id, (val, chg_1d, chg_1w, trend) in ground_truth.items():
            qa_db_session.add(
                IndicatorValue(
                    indicator_id=ind_id,
                    record_date=report_dt,
                    value=val,
                    change_1d=chg_1d,
                    change_1w=chg_1w,
                    trend_state=trend,
                    source_used="YAHOO",
                )
            )
        qa_db_session.commit()

        generator = DailyReportGenerator(db=qa_db_session)
        report = generator.generate_daily_report(report_date=report_dt)
        md = report.content_markdown

        # Verify Quick Snapshot Table rows match DB exactly
        snapshot_checks = [
            ("SP500", format_value_str(5815.20), format_change_str(0.61), format_change_str(1.25)),
            ("NASDAQ100", format_value_str(20240.10), format_change_str(0.85), format_change_str(1.80)),
            ("DXY", format_value_str(102.85), format_change_str(0.22), format_change_str(0.55)),
            ("US_10Y_YIELD", format_value_str(4.15, "%"), format_change_str(3.20, " bps"), format_change_str(8.50, " bps")),
            ("BRENT_OIL", format_value_str(84.20, "USD/thùng"), format_change_str(-0.45), format_change_str(2.10)),
            ("GOLD", format_value_str(2655.40, "USD/Ounce"), format_change_str(0.35), format_change_str(0.90)),
            ("VIX", format_value_str(15.40), format_change_str(-3.20), format_change_str(-6.50)),
        ]
        for ind_id, expected_val_str, expected_1d_str, expected_1w_str in snapshot_checks:
            db_rec = qa_db_session.query(IndicatorValue).filter_by(indicator_id=ind_id, record_date=report_dt).one()
            assert expected_val_str in md, f"Lineage mismatch for {ind_id} value: {expected_val_str} not in report"
            assert expected_1d_str in md, f"Lineage mismatch for {ind_id} 1D change: {expected_1d_str} not in report"
            assert expected_1w_str in md, f"Lineage mismatch for {ind_id} 1W change: {expected_1w_str} not in report"
            assert db_rec.value == ground_truth[ind_id][0]

        # Verify narrative body figures match DB 100%
        assert format_value_str(3.98, "%") in md  # US_02Y_YIELD
        assert format_value_str(17.0, "bps") in md  # US_10Y_02Y_SPREAD
        assert format_value_str(4.83, "%") in md  # FED_FUNDS_RATE
        assert format_value_str(2.40, "%") in md  # US_CPI_YOY
        assert format_value_str(3.20, "%") in md  # US_CORE_CPI_YOY
        assert format_value_str(4.10, "%") in md  # US_UNEMP_RATE
        assert format_value_str(1.0925) in md  # EUR_USD
        assert format_value_str(149.20) in md  # USD_JPY
        assert format_value_str(25340.00) in md  # USD_VND
        assert format_value_str(80.15, "USD/thùng") in md  # WTI_OIL
        assert format_value_str(4.4200) in md  # COPPER


# ==============================================================================
# 4. [TASK-20] END-TO-END INTEGRATION & ADMIN API SECURITY TESTS
# ==============================================================================
class TestTask20EndToEndPipelineAndApiSecurity:
    """[TASK-20] End-to-End flow: Mock Ingest -> Analytics -> Report -> REST APIs & X-Admin-Api-Key auth."""

    def test_end_to_end_pipeline_and_rest_endpoints(self, qa_db_session):
        # Override FastAPI get_db dependency to use isolated qa_db_session
        def override_get_db():
            yield qa_db_session

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        try:
            target_dt = date.today()
            prev_dt = target_dt - timedelta(days=1)

            # 1. Mock Fetchers returning 2 days of data for all indicators
            mock_fred = MagicMock()
            mock_fred.fetch_series.return_value = [
                DataPoint(record_date=prev_dt, value=3.00),
                DataPoint(record_date=target_dt, value=3.10),
            ]
            mock_yahoo = MagicMock()
            mock_yahoo.fetch_series.return_value = [
                DataPoint(record_date=prev_dt, value=100.0),
                DataPoint(record_date=target_dt, value=101.5),
            ]
            mock_stooq = MagicMock()

            coordinator = FailoverCoordinator(
                fred_fetcher=mock_fred,
                yahoo_fetcher=mock_yahoo,
                stooq_fetcher=mock_stooq,
            )

            # Ingest previous day then target day
            coordinator.ingest_all(db=qa_db_session, target_date=prev_dt)
            summary = coordinator.ingest_all(db=qa_db_session, target_date=target_dt)
            assert summary["total"] == 24
            assert summary["failed"] == 0

            # 2. Run Analytics Engine for all 24 indicators
            for ind in qa_db_session.query(Indicator).all():
                updated = update_indicator_metrics_in_db(ind.id, qa_db_session)
                assert updated is not None
                assert updated.change_1d is not None

            # 3. Generate Daily Report
            generator = DailyReportGenerator(db=qa_db_session)
            report = generator.generate_daily_report(report_date=target_dt)
            assert report.status == "PUBLISHED"

            # 4. Verify REST API Endpoints
            # 4a. GET /api/v1/indicators
            r_ind = client.get("/api/v1/indicators")
            assert r_ind.status_code == 200
            ind_list = r_ind.json()["data"]
            assert len(ind_list) == 24
            sp500_entry = next(x for x in ind_list if x["id"] == "SP500")
            assert sp500_entry["latest_value"] == 101.5
            assert sp500_entry["change_1d"] == 1.5
            assert sp500_entry["trend_state"] == "BULLISH"

            # 4b. GET /api/v1/indicators/{id}/history
            r_hist = client.get("/api/v1/indicators/SP500/history?range=1M")
            assert r_hist.status_code == 200
            hist_data = r_hist.json()["data"]
            assert hist_data["indicator_id"] == "SP500"
            assert len(hist_data["data"]) == 2

            # 4c. GET /api/v1/reports/latest
            r_latest = client.get("/api/v1/reports/latest")
            assert r_latest.status_code == 200
            latest_data = r_latest.json()["data"]
            assert latest_data["id"] == f"REPORT-{target_dt.strftime('%Y%m%d')}"
            assert len(latest_data["snapshot"]) == 7

            # 4d. GET /api/v1/reports/{date}
            r_by_date = client.get(f"/api/v1/reports/{target_dt.isoformat()}")
            assert r_by_date.status_code == 200
            assert r_by_date.json()["data"]["report_date"] == target_dt.isoformat()

            # 4e. GET /api/v1/reports (Archive)
            r_archive = client.get("/api/v1/reports?page=1&limit=10")
            assert r_archive.status_code == 200
            assert r_archive.json()["data"]["total"] == 1

            # 5. Verify X-Admin-Api-Key security on /api/v1/admin/*
            # Missing header -> 401
            assert client.post("/api/v1/admin/generate-report").status_code == 401
            assert client.post("/api/v1/admin/ingest").status_code == 401

            # Wrong X-Admin-Api-Key -> 401
            assert (
                client.post(
                    "/api/v1/admin/generate-report",
                    headers={"X-Admin-Api-Key": "invalid-hacker-key"},
                ).status_code
                == 401
            )

            # Valid X-Admin-Api-Key -> 200 OK
            r_admin_ok = client.post(
                f"/api/v1/admin/generate-report?report_date={target_dt.isoformat()}",
                headers={"X-Admin-Api-Key": settings.ADMIN_SECRET_KEY},
            )
            assert r_admin_ok.status_code == 200
            assert r_admin_ok.json()["status"] == "success"
        finally:
            app.dependency_overrides.clear()


# ==============================================================================
# 5. [TASK-22] PERFORMANCE & LATENCY BENCHMARK (< 300ms NFR)
# ==============================================================================
class TestTask22PerformanceAndLatencyBenchmark:
    """[TASK-22] Measure response latency across all primary GET API endpoints (< 300ms per SRS Section 10.1)."""

    def test_api_endpoints_latency_under_300ms(self, qa_db_session):
        def override_get_db():
            yield qa_db_session

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        try:
            today = date.today()
            # Seed 60 days of historical data across all 24 indicators
            for ind in qa_db_session.query(Indicator).all():
                for d in range(60):
                    rec_date = today - timedelta(days=59 - d)
                    qa_db_session.add(
                        IndicatorValue(
                            indicator_id=ind.id,
                            record_date=rec_date,
                            value=100.0 + d * 0.5,
                            change_1d=0.5,
                            change_1w=2.5,
                            ma_20=95.0 + d * 0.5,
                            ma_50=90.0 + d * 0.5,
                            trend_state="BULLISH",
                            source_used=ind.primary_source_id,
                        )
                    )
            qa_db_session.commit()

            generator = DailyReportGenerator(db=qa_db_session)
            generator.generate_daily_report(report_date=today)

            endpoints_to_benchmark = [
                "/api/v1/system/health",
                "/api/v1/indicators",
                "/api/v1/indicators?category=MACRO",
                "/api/v1/indicators/SP500/history?range=1Y",
                "/api/v1/reports/latest",
                f"/api/v1/reports/{today.isoformat()}",
                "/api/v1/reports?page=1&limit=10",
            ]

            for ep in endpoints_to_benchmark:
                t0 = time.perf_counter()
                resp = client.get(ep)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                assert resp.status_code == 200, f"Endpoint {ep} failed with {resp.status_code}"
                assert elapsed_ms < 300.0, f"NFR Violation: {ep} took {elapsed_ms:.2f}ms (> 300ms limit)"
        finally:
            app.dependency_overrides.clear()


# ==============================================================================
# 6. [TASK-23] 3-DAY CONSECUTIVE DRY RUN SIMULATION
# ==============================================================================
class TestTask23ThreeDayConsecutiveDryRun:
    """[TASK-23] Simulate 3 consecutive days (Day 1, Day 2, Day 3) of automated ingestion, analytics & report publishing."""

    def test_three_consecutive_days_dry_run_stability(self, qa_db_session):
        days = [
            date(2026, 10, 11),  # Day 1
            date(2026, 10, 12),  # Day 2
            date(2026, 10, 13),  # Day 3
        ]

        # Base prices consistent across sources so failover passes +/-50% variation check
        for day_idx, sim_date in enumerate(days):
            daily_val = 100.0 + day_idx * 1.5  # Day 1: 100.0, Day 2: 101.5, Day 3: 103.0

            mock_fred = MagicMock()
            mock_fred.fetch_series.return_value = [
                DataPoint(record_date=sim_date, value=daily_val)
            ]

            mock_yahoo = MagicMock()
            # Simulate Yahoo failure on Day 2 for resilience check during 3-day dry run, working on Day 1 & Day 3
            if day_idx == 1:
                mock_yahoo.fetch_series.side_effect = ConnectionError("Simulated Day 2 Yahoo glitch")
            else:
                mock_yahoo.fetch_series.return_value = [
                    DataPoint(record_date=sim_date, value=daily_val)
                ]

            mock_stooq = MagicMock()
            mock_stooq.fetch_series.return_value = [
                DataPoint(record_date=sim_date, value=daily_val)
            ]

            coordinator = FailoverCoordinator(
                fred_fetcher=mock_fred,
                yahoo_fetcher=mock_yahoo,
                stooq_fetcher=mock_stooq,
            )

            # Step 1: Run daily ingestion
            ingest_summary = coordinator.ingest_all(db=qa_db_session, target_date=sim_date)
            assert ingest_summary["total"] == 24
            assert ingest_summary["failed"] == 0

            # Step 2: Update quantitative analytics for all 24 indicators
            for ind in qa_db_session.query(Indicator).filter_by(is_active=True).all():
                rec = update_indicator_metrics_in_db(ind.id, qa_db_session)
                assert rec is not None
                assert rec.record_date == sim_date

            # Step 3: Generate & publish daily report
            generator = DailyReportGenerator(db=qa_db_session)
            report = generator.generate_daily_report(report_date=sim_date)
            assert report.status == "PUBLISHED"
            assert report.id == f"REPORT-{sim_date.strftime('%Y%m%d')}"
            assert report.report_date == sim_date

        # Final Verification across all 3 consecutive days
        published_reports = (
            qa_db_session.query(DailyReport)
            .filter(DailyReport.status == "PUBLISHED")
            .order_by(DailyReport.report_date.asc())
            .all()
        )
        assert len(published_reports) == 3
        assert [r.report_date for r in published_reports] == days

        # Verify each of the 24 indicators has 3 distinct daily records (24 * 3 = 72 records)
        total_indicator_values = qa_db_session.query(IndicatorValue).count()
        assert total_indicator_values == 24 * 3
