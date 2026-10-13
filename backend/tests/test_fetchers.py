"""
Unit Tests for Data Ingestion Fetchers and Failover Coordinator.
All network requests are mocked to ensure 100% offline, deterministic testing.
"""

from datetime import date
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.ingestion.base import DataPoint, validate_indicator_value
from app.core.ingestion.fred import FredFetcher, FredFetcherError
from app.core.ingestion.yahoo import YahooFetcher, YahooFetcherError
from app.core.ingestion.stooq import StooqFetcher, StooqFetcherError
from app.core.ingestion.fallback import FailoverCoordinator
from app.db.database import Base
from app.db.models import Indicator, IndicatorValue, IngestionLog, DataSource


@pytest.fixture
def mock_db():
    """In-memory SQLite database session for unit testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed required data sources
    session.add(DataSource(id="FRED", name="FRED", base_url="https://fred", is_active=True))
    session.add(DataSource(id="YAHOO", name="Yahoo", base_url="https://yahoo", is_active=True))
    session.add(DataSource(id="STOOQ", name="Stooq", base_url="https://stooq", is_active=True))
    session.commit()

    yield session
    session.close()


# -----------------------------------------------------------------------------
# 1. Base Validator Tests
# -----------------------------------------------------------------------------
def test_validate_indicator_value_sanity():
    # None and NaN checks
    valid, _ = validate_indicator_value("SP500", None)
    assert not valid
    valid, _ = validate_indicator_value("SP500", float("nan"))
    assert not valid
    valid, _ = validate_indicator_value("SP500", float("inf"))
    assert not valid

    # Negative check for Equity
    valid, _ = validate_indicator_value("SP500", -100.0, category="EQUITY")
    assert not valid

    # Negative check for Rates (Allowed)
    valid, _ = validate_indicator_value("US_10Y_02Y_SPREAD", -0.25, category="RATES")
    assert valid

    # Extreme variation check (> 50%)
    valid_drop, _ = validate_indicator_value("SP500", 2000.0, prev_value=5000.0, category="EQUITY")
    assert not valid_drop  # dropped by 60% (> 50%) is rejected
    valid_surge, reason = validate_indicator_value("SP500", 11000.0, prev_value=5000.0, category="EQUITY")
    assert not valid_surge
    assert "Extreme change detected" in reason

    # Normal variation
    valid, _ = validate_indicator_value("SP500", 5050.0, prev_value=5000.0, category="EQUITY")
    assert valid



# -----------------------------------------------------------------------------
# 2. FredFetcher Tests
# -----------------------------------------------------------------------------
@patch("requests.get")
def test_fred_fetcher_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "observations": [
            {"date": "2026-10-01", "value": "3.1"},
            {"date": "2026-10-02", "value": "."},  # Should be skipped
            {"date": "2026-10-03", "value": "3.25"},
        ]
    }
    mock_get.return_value = mock_resp

    fetcher = FredFetcher(api_key="test_key")
    points = fetcher.fetch_series("CPIAUCSL")

    assert len(points) == 2
    assert points[0] == DataPoint(record_date=date(2026, 10, 1), value=3.1)
    assert points[1] == DataPoint(record_date=date(2026, 10, 3), value=3.25)


def test_fred_fetcher_missing_key():
    fetcher = FredFetcher(api_key="")
    with pytest.raises(FredFetcherError):
        fetcher.fetch_series("CPIAUCSL")


# -----------------------------------------------------------------------------
# 3. YahooFetcher Tests
# -----------------------------------------------------------------------------
@patch("requests.get")
def test_yahoo_fetcher_rest_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # Unix timestamps for 2026-10-01 and 2026-10-02
    mock_resp.json.return_value = {
        "chart": {
            "result": [
                {
                    "timestamp": [1790812800, 1790899200],
                    "indicators": {"quote": [{"close": [5800.5, 5825.2]}]},
                }
            ]
        }
    }
    mock_get.return_value = mock_resp

    fetcher = YahooFetcher(throttle_seconds=0.0, backoff_delays=[0.0, 0.0, 0.0])
    points = fetcher._fetch_via_rest("^GSPC")

    assert len(points) == 2
    assert points[0].value == 5800.5
    assert points[1].value == 5825.2


@patch("requests.get")
def test_yahoo_fetcher_retry_exhaustion(mock_get):
    mock_get.side_effect = Exception("Connection timed out")
    fetcher = YahooFetcher(throttle_seconds=0.0, max_retries=3, backoff_delays=[0.0, 0.0, 0.0])

    with pytest.raises(YahooFetcherError):
        fetcher.fetch_series("^GSPC")

    # Should have retried 3 times
    assert mock_get.call_count == 3


# -----------------------------------------------------------------------------
# 4. StooqFetcher Tests
# -----------------------------------------------------------------------------
@patch("requests.get")
def test_stooq_fetcher_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = """Date,Open,High,Low,Close,Volume
2026-10-01,5790.0,5810.0,5780.0,5805.2,1000
2026-10-02,5805.0,5830.0,5800.0,5820.0,1200
"""
    mock_get.return_value = mock_resp

    fetcher = StooqFetcher()
    points = fetcher.fetch_series("^SPX")

    assert len(points) == 2
    assert points[0] == DataPoint(record_date=date(2026, 10, 1), value=5805.2)
    assert points[1] == DataPoint(record_date=date(2026, 10, 2), value=5820.0)


@patch("requests.get")
def test_stooq_fetcher_no_data(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "No data"
    mock_get.return_value = mock_resp

    fetcher = StooqFetcher()
    with pytest.raises(StooqFetcherError):
        fetcher.fetch_series("UNKNOWN_SYMBOL")


# -----------------------------------------------------------------------------
# 5. FailoverCoordinator Tests
# -----------------------------------------------------------------------------
def test_failover_coordinator_primary_success(mock_db):
    mock_yahoo = MagicMock()
    mock_yahoo.fetch_series.return_value = [
        DataPoint(record_date=date(2026, 10, 12), value=5815.2)
    ]
    mock_stooq = MagicMock()

    coordinator = FailoverCoordinator(yahoo_fetcher=mock_yahoo, stooq_fetcher=mock_stooq)

    indicator = Indicator(
        id="SP500",
        symbol="^GSPC",
        name_vi="S&P 500",
        name_en="S&P 500",
        category="EQUITY",
        unit="Points",
        primary_source_id="YAHOO",
        fallback_source_id="STOOQ",
        is_active=True,
    )
    mock_db.add(indicator)
    mock_db.commit()

    success, record, source_used = coordinator.ingest_indicator(indicator, db=mock_db)

    assert success is True
    assert record.value == 5815.2
    assert source_used == "YAHOO"
    assert mock_yahoo.fetch_series.called
    assert not mock_stooq.fetch_series.called

    # Check ingestion log
    log = mock_db.query(IngestionLog).filter_by(indicator_id="SP500").first()
    assert log is not None
    assert log.status == "SUCCESS"
    assert log.source_id == "YAHOO"


def test_failover_coordinator_fallback_triggered(mock_db):
    # Primary Yahoo fails
    mock_yahoo = MagicMock()
    mock_yahoo.fetch_series.side_effect = Exception("Yahoo 429 Rate Limit Exceeded")

    # Fallback Stooq succeeds
    mock_stooq = MagicMock()
    mock_stooq.fetch_series.return_value = [
        DataPoint(record_date=date(2026, 10, 12), value=5812.0)
    ]

    coordinator = FailoverCoordinator(yahoo_fetcher=mock_yahoo, stooq_fetcher=mock_stooq)

    indicator = Indicator(
        id="SP500",
        symbol="^GSPC",
        name_vi="S&P 500",
        name_en="S&P 500",
        category="EQUITY",
        unit="Points",
        primary_source_id="YAHOO",
        fallback_source_id="STOOQ",
        is_active=True,
    )
    mock_db.add(indicator)
    mock_db.commit()

    success, record, source_used = coordinator.ingest_indicator(indicator, db=mock_db)

    assert success is True
    assert record.value == 5812.0
    assert source_used == "STOOQ"
    assert mock_stooq.fetch_series.called

    # Verify both logs: FAILED for primary, FALLBACK_SUCCESS for fallback
    logs = (
        mock_db.query(IngestionLog)
        .filter_by(indicator_id="SP500")
        .order_by(IngestionLog.id.asc())
        .all()
    )
    assert len(logs) == 2
    assert logs[0].status == "FAILED"
    assert logs[0].source_id == "YAHOO"
    assert logs[1].status == "FALLBACK_SUCCESS"
    assert logs[1].source_id == "STOOQ"
