"""
Seed Data Script for GMIP.
Initializes data sources and the 24 core macroeconomic indicators defined in docs/SRS.md.
Execution is idempotent: safe to run multiple times without duplicate errors.
"""

import sys
import os
import logging

# Ensure backend root is on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db.database import SessionLocal, init_db
from app.db.models import DataSource, Indicator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ==============================================================================
# Master Data Sources (docs/TECH_ARCHITECTURE.md & docs/SRS.md Section 3)
# ==============================================================================
DATA_SOURCES = [
    {
        "id": "FRED",
        "name": "Federal Reserve Economic Data (St. Louis Fed)",
        "base_url": "https://api.stlouisfed.org/fred",
        "auth_type": "API_KEY",
        "rate_limit_per_minute": 120,
        "is_active": True,
    },
    {
        "id": "YAHOO",
        "name": "Yahoo Finance",
        "base_url": "https://query1.finance.yahoo.com",
        "auth_type": "NONE",
        "rate_limit_per_minute": 60,
        "is_active": True,
    },
    {
        "id": "STOOQ",
        "name": "Stooq Financial Data (CSV Mirror)",
        "base_url": "https://stooq.com",
        "auth_type": "NONE",
        "rate_limit_per_minute": 60,
        "is_active": True,
    },
]

# ==============================================================================
# 24 Core Indicators Catalog (docs/SRS.md Section 2)
# ==============================================================================
INDICATORS = [
    # --------------------------------------------------------------------------
    # 1. Macro (Vĩ mô) - 6 indicators
    # --------------------------------------------------------------------------
    {
        "id": "US_CPI_YOY",
        "symbol": "CPIAUCSL",
        "name_vi": "Lạm phát Mỹ (Consumer Price Index YoY)",
        "name_en": "Consumer Price Index YoY",
        "category": "MACRO",
        "unit": "%",
        "frequency": "MONTHLY",
        "primary_source_id": "FRED",
        "fallback_source_id": None,
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "US_CORE_CPI_YOY",
        "symbol": "CPILFESL",
        "name_vi": "Lạm phát lõi Mỹ (Core CPI YoY)",
        "name_en": "Core CPI YoY",
        "category": "MACRO",
        "unit": "%",
        "frequency": "MONTHLY",
        "primary_source_id": "FRED",
        "fallback_source_id": None,
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "US_GDP_QOQ",
        "symbol": "A191RL1Q225SBEA",
        "name_vi": "Tăng trưởng GDP Mỹ (Real GDP QoQ Ann.)",
        "name_en": "Real GDP QoQ Ann.",
        "category": "MACRO",
        "unit": "%",
        "frequency": "QUARTERLY",
        "primary_source_id": "FRED",
        "fallback_source_id": None,
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "US_UNEMP_RATE",
        "symbol": "UNRATE",
        "name_vi": "Tỷ lệ thất nghiệp Mỹ (Unemployment Rate)",
        "name_en": "Unemployment Rate",
        "category": "MACRO",
        "unit": "%",
        "frequency": "MONTHLY",
        "primary_source_id": "FRED",
        "fallback_source_id": None,
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "US_NONFARM_PAYROLL",
        "symbol": "PAYEMS",
        "name_vi": "Bảng lương phi nông nghiệp (Nonfarm Payrolls)",
        "name_en": "Nonfarm Payrolls",
        "category": "MACRO",
        "unit": "Nghìn việc làm",
        "frequency": "MONTHLY",
        "primary_source_id": "FRED",
        "fallback_source_id": None,
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "US_MANUF_PMI",
        "symbol": "^PMI",
        "name_vi": "Chỉ số sản xuất PMI (ISM Manufacturing PMI)",
        "name_en": "ISM Manufacturing PMI",
        "category": "MACRO",
        "unit": "Điểm số",
        "frequency": "MONTHLY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 2,
        "is_active": True,
    },

    # --------------------------------------------------------------------------
    # 2. Rates (Lãi suất) - 5 indicators
    # --------------------------------------------------------------------------
    {
        "id": "FED_FUNDS_RATE",
        "symbol": "FEDFUNDS",
        "name_vi": "Lãi suất điều hành Fed (Fed Funds Rate)",
        "name_en": "Fed Funds Rate",
        "category": "RATES",
        "unit": "%",
        "frequency": "DAILY",
        "primary_source_id": "FRED",
        "fallback_source_id": "YAHOO",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "US_10Y_YIELD",
        "symbol": "^TNX",
        "name_vi": "Lợi suất TPCP Mỹ 10 năm (US 10-Year Treasury)",
        "name_en": "US 10-Year Treasury",
        "category": "RATES",
        "unit": "%",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "FRED",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "US_02Y_YIELD",
        "symbol": "^IRX",
        "name_vi": "Lợi suất TPCP Mỹ 2 năm (US 2-Year Treasury)",
        "name_en": "US 2-Year Treasury",
        "category": "RATES",
        "unit": "%",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "FRED",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "US_10Y_02Y_SPREAD",
        "symbol": "T10Y2Y",
        "name_vi": "Chênh lệch lợi suất 10Y-2Y (Yield Curve Spread)",
        "name_en": "Yield Curve Spread",
        "category": "RATES",
        "unit": "bps",
        "frequency": "DAILY",
        "primary_source_id": "FRED",
        "fallback_source_id": "YAHOO",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "ECB_DEPOSIT_RATE",
        "symbol": "ECBDFR",
        "name_vi": "Lãi suất tiền gửi ECB (ECB Deposit Facility)",
        "name_en": "ECB Deposit Facility",
        "category": "RATES",
        "unit": "%",
        "frequency": "MONTHLY",
        "primary_source_id": "FRED",
        "fallback_source_id": "YAHOO",
        "priority": 2,
        "is_active": True,
    },

    # --------------------------------------------------------------------------
    # 3. FX (Ngoại hối) - 4 indicators
    # --------------------------------------------------------------------------
    {
        "id": "DXY",
        "symbol": "DX-Y.NYB",
        "name_vi": "Chỉ số sức mạnh đồng USD (US Dollar Index)",
        "name_en": "US Dollar Index",
        "category": "FX",
        "unit": "Điểm số",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "EUR_USD",
        "symbol": "EURUSD=X",
        "name_vi": "Tỷ giá Euro / Đô la Mỹ (EUR/USD)",
        "name_en": "EUR/USD",
        "category": "FX",
        "unit": "USD/EUR",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "USD_JPY",
        "symbol": "JPY=X",
        "name_vi": "Tỷ giá Đô la Mỹ / Yên Nhật (USD/JPY)",
        "name_en": "USD/JPY",
        "category": "FX",
        "unit": "JPY/USD",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "USD_VND",
        "symbol": "VND=X",
        "name_vi": "Tỷ giá Đô la Mỹ / Đồng Việt Nam (USD/VND)",
        "name_en": "USD/VND",
        "category": "FX",
        "unit": "VND/USD",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 2,
        "is_active": True,
    },

    # --------------------------------------------------------------------------
    # 4. Commodity (Hàng hóa) - 4 indicators
    # --------------------------------------------------------------------------
    {
        "id": "BRENT_OIL",
        "symbol": "BZ=F",
        "name_vi": "Giá dầu thô Brent (Brent Crude Oil)",
        "name_en": "Brent Crude Oil",
        "category": "COMMODITY",
        "unit": "USD/thùng",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "FRED",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "WTI_OIL",
        "symbol": "CL=F",
        "name_vi": "Giá dầu thô WTI (WTI Crude Oil)",
        "name_en": "WTI Crude Oil",
        "category": "COMMODITY",
        "unit": "USD/thùng",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "FRED",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "GOLD",
        "symbol": "GC=F",
        "name_vi": "Giá vàng thế giới (Gold Spot / Futures)",
        "name_en": "Gold Spot / Futures",
        "category": "COMMODITY",
        "unit": "USD/Ounce",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "COPPER",
        "symbol": "HG=F",
        "name_vi": "Giá đồng thế giới (Copper - Dr. Copper)",
        "name_en": "Copper - Dr. Copper",
        "category": "COMMODITY",
        "unit": "USD/Lbs",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 2,
        "is_active": True,
    },

    # --------------------------------------------------------------------------
    # 5. Equity (Chứng khoán) - 4 indicators
    # --------------------------------------------------------------------------
    {
        "id": "SP500",
        "symbol": "^GSPC",
        "name_vi": "Chỉ số chứng khoán S&P 500",
        "name_en": "S&P 500 Index",
        "category": "EQUITY",
        "unit": "Điểm số",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "NASDAQ100",
        "symbol": "^NDX",
        "name_vi": "Chỉ số chứng khoán công nghệ Nasdaq 100",
        "name_en": "Nasdaq 100 Index",
        "category": "EQUITY",
        "unit": "Điểm số",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "DOW_JONES",
        "symbol": "^DJI",
        "name_vi": "Chỉ số công nghiệp Dow Jones",
        "name_en": "Dow Jones Industrial Average",
        "category": "EQUITY",
        "unit": "Điểm số",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "NIKKEI225",
        "symbol": "^N225",
        "name_vi": "Chỉ số chứng khoán Nhật Bản Nikkei 225",
        "name_en": "Nikkei 225 Index",
        "category": "EQUITY",
        "unit": "Điểm số",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 2,
        "is_active": True,
    },

    # --------------------------------------------------------------------------
    # 6. Sentiment (Tâm lý thị trường) - 1 indicator
    # --------------------------------------------------------------------------
    {
        "id": "VIX",
        "symbol": "^VIX",
        "name_vi": "Chỉ số đo lường sự biến động và sợ hãi (CBOE VIX)",
        "name_en": "CBOE Volatility Index (VIX)",
        "category": "SENTIMENT",
        "unit": "Điểm số",
        "frequency": "DAILY",
        "primary_source_id": "YAHOO",
        "fallback_source_id": "STOOQ",
        "priority": 1,
        "is_active": True,
    },
]


def seed_database():
    """Seed data sources and indicators into the database idempotently."""
    logger.info("Initializing database tables if not already present...")
    init_db()

    session = SessionLocal()
    try:
        # 1. Seed Data Sources
        sources_seeded = 0
        for src in DATA_SOURCES:
            existing = session.query(DataSource).filter_by(id=src["id"]).first()
            if existing:
                for k, v in src.items():
                    setattr(existing, k, v)
            else:
                session.add(DataSource(**src))
            sources_seeded += 1
        session.commit()
        logger.info("Successfully seeded/updated %d data sources.", sources_seeded)

        # 2. Seed Indicators
        indicators_seeded = 0
        for ind in INDICATORS:
            existing = session.query(Indicator).filter_by(id=ind["id"]).first()
            if existing:
                for k, v in ind.items():
                    setattr(existing, k, v)
            else:
                session.add(Indicator(**ind))
            indicators_seeded += 1
        session.commit()
        logger.info("Successfully seeded/updated %d indicators.", indicators_seeded)

        total_indicators = session.query(Indicator).count()
        total_sources = session.query(DataSource).count()
        logger.info(
            "Seeding verification completed: Total Sources = %d, Total Indicators = %d.",
            total_sources,
            total_indicators,
        )

    except Exception as exc:
        session.rollback()
        logger.error("Error occurred while seeding database: %s", exc)
        raise exc
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
