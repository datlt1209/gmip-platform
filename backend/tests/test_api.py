"""
Integration Tests for REST API Endpoints (Indicators, Reports, Admin).
Tests API response structures, error handling, filters, and admin authentication.
"""

from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings
from app.db.database import SessionLocal, init_db
from app.db.models import Indicator, IndicatorValue, DailyReport
from scripts.seed_data import seed_database

settings = get_settings()


@pytest.fixture(scope="module", autouse=True)
def setup_api_data():
    """Ensure database has seed data and test reports populated."""
    init_db()
    seed_database()

    session = SessionLocal()
    today = date.today()

    # Insert test indicator value
    sp500_val = session.query(IndicatorValue).filter_by(indicator_id="SP500", record_date=today).first()
    if not sp500_val:
        sp500_val = IndicatorValue(
            indicator_id="SP500",
            record_date=today,
            value=5850.0,
            change_1d=0.75,
            change_1w=1.80,
            ma_20=5790.0,
            trend_state="BULLISH",
            source_used="YAHOO",
        )
        session.add(sp500_val)

    # Insert test daily report
    test_report = session.query(DailyReport).filter_by(report_date=today).first()
    if not test_report:
        test_report = DailyReport(
            id=f"REPORT-{today.strftime('%Y%m%d')}",
            report_date=today,
            title=f"Báo cáo thử nghiệm ngày {today.strftime('%d/%m/%Y')}",
            summary="Bản tóm tắt thị trường kiểm thử.",
            risk_level="MEDIUM",
            content_markdown="# BÁO CÁO NHỊP ĐẬP KINH TẾ...",
            status="PUBLISHED",
        )
        session.add(test_report)

    session.commit()
    session.close()


def test_get_indicators_catalog_with_sparkline():
    client = TestClient(app)
    response = client.get("/api/v1/indicators?category=EQUITY")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    items = res_data["data"]
    assert len(items) == 4  # SP500, NASDAQ100, DOW_JONES, NIKKEI225

    sp500_item = next(item for item in items if item["id"] == "SP500")
    assert sp500_item["latest_value"] is not None
    assert "sparkline" in sp500_item
    assert isinstance(sp500_item["sparkline"], list)


def test_get_indicator_history_endpoint():
    client = TestClient(app)
    # Test valid indicator
    response = client.get("/api/v1/indicators/SP500/history?range=1M")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["indicator_id"] == "SP500"
    assert data["range"] == "1M"
    assert isinstance(data["data"], list)

    # Test 404 for invalid indicator
    resp_404 = client.get("/api/v1/indicators/INVALID_ID/history")
    assert resp_404.status_code == 404


def test_get_latest_report_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/reports/latest")
    assert response.status_code == 200
    report_data = response.json()["data"]
    assert report_data["id"] is not None
    assert report_data["status"] == "PUBLISHED"
    assert "content_markdown" in report_data
    assert "snapshot" in report_data
    assert isinstance(report_data["snapshot"], list)



def test_get_reports_archive_pagination():
    client = TestClient(app)
    response = client.get("/api/v1/reports?page=1&limit=5")
    assert response.status_code == 200
    page_data = response.json()["data"]
    assert "total" in page_data
    assert page_data["page"] == 1
    assert page_data["limit"] == 5
    assert isinstance(page_data["items"], list)


def test_admin_trigger_report_auth():
    client = TestClient(app)

    # 1. Unauthorized when secret key missing or incorrect
    resp_unauth = client.post("/api/v1/admin/trigger/report", headers={"X-Admin-Key": "wrong-key"})
    assert resp_unauth.status_code == 401

    # 2. Authorized with valid secret key
    resp_auth = client.post(
        "/api/v1/admin/trigger/report",
        headers={"X-Admin-Key": settings.ADMIN_SECRET_KEY},
    )
    assert resp_auth.status_code == 200
    assert resp_auth.json()["status"] == "success"
