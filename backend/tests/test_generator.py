"""
Unit Tests for Daily Report Generator Engine (generator.py).
Tests 5-section Vietnamese Markdown report compilation, data lineage preservation,
and database persistence.
"""

from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.reporting.generator import DailyReportGenerator
from app.db.database import Base
from app.db.models import DailyReport, Indicator, IndicatorValue, DataSource
from scripts.seed_data import seed_database


@pytest.fixture
def reporting_test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed master indicators
    # Add data sources first
    session.add(DataSource(id="FRED", name="FRED", base_url="https://fred", is_active=True))
    session.add(DataSource(id="YAHOO", name="Yahoo", base_url="https://yahoo", is_active=True))
    session.add(DataSource(id="STOOQ", name="Stooq", base_url="https://stooq", is_active=True))

    # Add core indicators
    test_indicators = [
        Indicator(id="SP500", symbol="^GSPC", name_vi="S&P 500", name_en="S&P 500", category="EQUITY", unit="Điểm", primary_source_id="YAHOO"),
        Indicator(id="NASDAQ100", symbol="^NDX", name_vi="Nasdaq 100", name_en="Nasdaq 100", category="EQUITY", unit="Điểm", primary_source_id="YAHOO"),
        Indicator(id="DOW_JONES", symbol="^DJI", name_vi="Dow Jones", name_en="Dow Jones", category="EQUITY", unit="Điểm", primary_source_id="YAHOO"),
        Indicator(id="NIKKEI225", symbol="^N225", name_vi="Nikkei 225", name_en="Nikkei 225", category="EQUITY", unit="Điểm", primary_source_id="YAHOO"),
        Indicator(id="DXY", symbol="DX-Y", name_vi="DXY", name_en="DXY", category="FX", unit="Điểm", primary_source_id="YAHOO"),
        Indicator(id="EUR_USD", symbol="EURUSD", name_vi="EUR/USD", name_en="EUR/USD", category="FX", unit="USD/EUR", primary_source_id="YAHOO"),
        Indicator(id="USD_JPY", symbol="USDJPY", name_vi="USD/JPY", name_en="USD/JPY", category="FX", unit="JPY/USD", primary_source_id="YAHOO"),
        Indicator(id="USD_VND", symbol="USDVND", name_vi="USD/VND", name_en="USD/VND", category="FX", unit="VND/USD", primary_source_id="YAHOO"),
        Indicator(id="BRENT_OIL", symbol="BZ=F", name_vi="Dầu Brent", name_en="Brent", category="COMMODITY", unit="USD/thùng", primary_source_id="YAHOO"),
        Indicator(id="WTI_OIL", symbol="CL=F", name_vi="Dầu WTI", name_en="WTI", category="COMMODITY", unit="USD/thùng", primary_source_id="YAHOO"),
        Indicator(id="GOLD", symbol="GC=F", name_vi="Vàng", name_en="Gold", category="COMMODITY", unit="USD/Ounce", primary_source_id="YAHOO"),
        Indicator(id="COPPER", symbol="HG=F", name_vi="Đồng", name_en="Copper", category="COMMODITY", unit="USD/Lbs", primary_source_id="YAHOO"),
        Indicator(id="FED_FUNDS_RATE", symbol="FEDFUNDS", name_vi="Fed Funds", name_en="Fed Funds", category="RATES", unit="%", primary_source_id="FRED"),
        Indicator(id="US_10Y_YIELD", symbol="^TNX", name_vi="10Y", name_en="10Y", category="RATES", unit="%", primary_source_id="YAHOO"),
        Indicator(id="US_02Y_YIELD", symbol="^IRX", name_vi="2Y", name_en="2Y", category="RATES", unit="%", primary_source_id="YAHOO"),
        Indicator(id="US_10Y_02Y_SPREAD", symbol="T10Y2Y", name_vi="Spread", name_en="Spread", category="RATES", unit="bps", primary_source_id="FRED"),
        Indicator(id="US_CPI_YOY", symbol="CPI", name_vi="CPI", name_en="CPI", category="MACRO", unit="%", primary_source_id="FRED"),
        Indicator(id="US_CORE_CPI_YOY", symbol="CORECPI", name_vi="Core CPI", name_en="Core CPI", category="MACRO", unit="%", primary_source_id="FRED"),
        Indicator(id="US_UNEMP_RATE", symbol="UNRATE", name_vi="Unemployment", name_en="Unemployment", category="MACRO", unit="%", primary_source_id="FRED"),
        Indicator(id="VIX", symbol="^VIX", name_vi="VIX", name_en="VIX", category="SENTIMENT", unit="Điểm", primary_source_id="YAHOO"),
    ]
    session.add_all(test_indicators)
    session.commit()

    yield session
    session.close()


def test_daily_report_generation(reporting_test_db):
    report_date = date(2026, 10, 13)

    # Populate known mock values
    reporting_test_db.add(IndicatorValue(indicator_id="SP500", record_date=report_date, value=5815.20, change_1d=0.61, change_1w=1.25, trend_state="BULLISH", source_used="YAHOO"))
    reporting_test_db.add(IndicatorValue(indicator_id="DXY", record_date=report_date, value=102.85, change_1d=0.22, change_1w=0.55, trend_state="BULLISH", source_used="YAHOO"))
    reporting_test_db.add(IndicatorValue(indicator_id="US_10Y_YIELD", record_date=report_date, value=4.15, change_1d=3.2, change_1w=8.5, trend_state="NEUTRAL", source_used="YAHOO"))
    reporting_test_db.add(IndicatorValue(indicator_id="BRENT_OIL", record_date=report_date, value=84.20, change_1d=-0.45, change_1w=2.10, trend_state="NEUTRAL", source_used="YAHOO"))
    reporting_test_db.add(IndicatorValue(indicator_id="GOLD", record_date=report_date, value=2655.40, change_1d=0.35, change_1w=0.90, trend_state="NEUTRAL", source_used="YAHOO"))
    reporting_test_db.add(IndicatorValue(indicator_id="VIX", record_date=report_date, value=15.40, change_1d=-3.20, change_1w=-6.50, trend_state="NEUTRAL", source_used="YAHOO"))
    reporting_test_db.commit()

    generator = DailyReportGenerator(db=reporting_test_db)
    report = generator.generate_daily_report(report_date=report_date)

    # 1. Verification of Report Metadata
    assert report is not None
    assert report.id == "REPORT-20261013"
    assert report.report_date == report_date
    assert report.status == "PUBLISHED"
    assert "13/10/2026" in report.title

    # 2. Verification of 5 Standard Sections
    content = report.content_markdown
    assert "### PHẦN I: TỔNG QUAN THỊ TRƯỜNG & ĐIỂM TIN NỔI BẬT" in content
    assert "### PHẦN II: VĨ MÔ TOÀN CẦU & CHÍNH SÁCH TIỀN TỆ" in content
    assert "### PHẦN III: DIỄN BIẾN THỊ TRƯỜNG TÀI SẢN" in content
    assert "### PHẦN IV: ĐIỂM CẦN CHÚ Ý & SỰ KIỆN KINH TẾ TRONG NGÀY" in content
    assert "### PHẦN V: LA BÀN RỦI RO & NHẬN ĐỊNH TỔNG QUAN" in content

    # 3. Data Lineage Verification: exact numbers must exist in markdown
    assert "5,815.20" in content
    assert "+0.61%" in content
    assert "102.85" in content
    assert "4.15%" in content
    assert "$84.20/thùng" in content
    assert "$2,655.40/oz" in content

    # 4. Check Database Persistence
    saved_report = reporting_test_db.query(DailyReport).filter_by(id="REPORT-20261013").first()
    assert saved_report is not None
    assert saved_report.summary is not None
    assert len(saved_report.summary) > 20
