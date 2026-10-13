"""
Test Suite for Database Models, Seeding, and Health Check Endpoint.
Verifies that database tables are initialized, master data contains 24 indicators,
and health endpoint functions properly.
"""

import sys
import os
import pytest
from sqlalchemy import inspect
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db.database import engine, SessionLocal, init_db
from app.db.models import DataSource, Indicator, IndicatorValue, DailyReport, IngestionLog
from app.main import app
from scripts.seed_data import seed_database


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Ensure database schema is created and seeded before running tests."""
    init_db()
    seed_database()


def test_database_tables_exist():
    """Verify that all 5 required tables exist in database metadata."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    required_tables = [
        "data_sources",
        "indicators",
        "indicator_values",
        "daily_reports",
        "ingestion_logs",
    ]

    for table in required_tables:
        assert table in tables, f"Table '{table}' not found in database!"


def test_data_sources_seeded():
    """Verify that 3 core data sources (FRED, YAHOO, STOOQ) are seeded."""
    session = SessionLocal()
    try:
        sources = session.query(DataSource).all()
        source_ids = {src.id for src in sources}
        assert "FRED" in source_ids
        assert "YAHOO" in source_ids
        assert "STOOQ" in source_ids
        assert len(sources) >= 3
    finally:
        session.close()


def test_24_indicators_seeded():
    """Verify that exactly 24 indicators are seeded across all 6 categories."""
    session = SessionLocal()
    try:
        indicators = session.query(Indicator).all()
        assert len(indicators) == 24, f"Expected 24 indicators, found {len(indicators)}"

        # Verify all 6 categories are represented
        categories = {ind.category for ind in indicators}
        expected_categories = {"MACRO", "RATES", "FX", "COMMODITY", "EQUITY", "SENTIMENT"}
        assert categories == expected_categories, f"Categories mismatch: {categories} != {expected_categories}"

        # Category counts verification
        cat_counts = {}
        for ind in indicators:
            cat_counts[ind.category] = cat_counts.get(ind.category, 0) + 1

        assert cat_counts["MACRO"] == 6
        assert cat_counts["RATES"] == 5
        assert cat_counts["FX"] == 4
        assert cat_counts["COMMODITY"] == 4
        assert cat_counts["EQUITY"] == 4
        assert cat_counts["SENTIMENT"] == 1
    finally:
        session.close()


def test_health_check_endpoint():
    """Verify the /api/v1/system/health API endpoint."""
    client = TestClient(app)
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["version"] == "1.0.0"
    assert "timestamp" in data


def test_indicators_api_endpoint():
    """Verify GET /api/v1/indicators returns 24 indicators."""
    client = TestClient(app)
    response = client.get("/api/v1/indicators")
    assert response.status_code == 200
    res_body = response.json()
    assert res_body["status"] == "success"
    assert len(res_body["data"]) == 24
