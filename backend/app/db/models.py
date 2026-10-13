"""
SQLAlchemy ORM Models for GMIP.
Defines database tables: data_sources, indicators, indicator_values, daily_reports, ingestion_logs.
Adheres strictly to docs/TECH_ARCHITECTURE.md Section 4.2 and docs/SRS.md.
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Float,
    Boolean,
    Date,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class DataSource(Base):
    """
    Data source definition table (e.g. FRED, Yahoo Finance, Stooq).
    """
    __tablename__ = "data_sources"

    id = Column(String(32), primary_key=True, comment="Source identifier: FRED, YAHOO, STOOQ")
    name = Column(String(128), nullable=False, comment="Descriptive provider name")
    base_url = Column(String(255), nullable=False, comment="Base endpoint URL")
    auth_type = Column(String(32), default="NONE", comment="Authentication type: NONE, API_KEY, BEARER")
    rate_limit_per_minute = Column(Integer, default=60, comment="Rate limit threshold per minute")
    is_active = Column(Boolean, default=True, comment="Source active status")
    created_at = Column(DateTime, server_default=func.now(), comment="Creation timestamp")

    # Relationships
    primary_indicators = relationship(
        "Indicator",
        foreign_keys="Indicator.primary_source_id",
        back_populates="primary_source",
    )
    fallback_indicators = relationship(
        "Indicator",
        foreign_keys="Indicator.fallback_source_id",
        back_populates="fallback_source",
    )
    logs = relationship("IngestionLog", back_populates="source")

    def __repr__(self) -> str:
        return f"<DataSource(id='{self.id}', name='{self.name}')>"


class Indicator(Base):
    """
    Macroeconomic & Financial Indicator master catalog table (24 core indicators).
    """
    __tablename__ = "indicators"

    id = Column(String(64), primary_key=True, comment="Standard ID e.g. SP500, US_CPI_YOY, US_10Y_YIELD")
    symbol = Column(String(64), nullable=False, comment="Source ticker/series identifier e.g. ^GSPC, CPIAUCSL")
    name_vi = Column(String(255), nullable=False, comment="Vietnamese display name")
    name_en = Column(String(255), nullable=False, comment="English display name")
    category = Column(
        String(32),
        nullable=False,
        comment="Category: MACRO, RATES, FX, COMMODITY, EQUITY, SENTIMENT",
    )
    unit = Column(String(32), nullable=False, comment="Measurement unit: %, USD, Points, bps")
    frequency = Column(String(32), default="DAILY", comment="Update frequency: DAILY, MONTHLY, QUARTERLY")
    primary_source_id = Column(String(32), ForeignKey("data_sources.id"), nullable=False)
    fallback_source_id = Column(String(32), ForeignKey("data_sources.id"), nullable=True)
    priority = Column(Integer, default=1, comment="Priority level: 1 (P1 MVP core), 2 (P2 extended)")
    is_active = Column(Boolean, default=True, comment="Active tracking indicator flag")
    created_at = Column(DateTime, server_default=func.now(), comment="Creation timestamp")

    # Relationships
    primary_source = relationship("DataSource", foreign_keys=[primary_source_id], back_populates="primary_indicators")
    fallback_source = relationship("DataSource", foreign_keys=[fallback_source_id], back_populates="fallback_indicators")
    values = relationship("IndicatorValue", back_populates="indicator", cascade="all, delete-orphan")
    logs = relationship("IngestionLog", back_populates="indicator")

    def __repr__(self) -> str:
        return f"<Indicator(id='{self.id}', symbol='{self.symbol}', category='{self.category}')>"


class IndicatorValue(Base):
    """
    Historical time-series values and computed indicators for trend analysis.
    """
    __tablename__ = "indicator_values"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    indicator_id = Column(
        String(64),
        ForeignKey("indicators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_date = Column(Date, nullable=False, index=True, comment="Trading or observation date (YYYY-MM-DD)")
    value = Column(Float, nullable=False, comment="Observed numeric value")
    change_1d = Column(Float, nullable=True, comment="1-day relative or bps change")
    change_1w = Column(Float, nullable=True, comment="1-week relative or bps change")
    change_1m = Column(Float, nullable=True, comment="1-month relative or bps change")
    change_yoy = Column(Float, nullable=True, comment="Year-over-Year relative change")
    ma_20 = Column(Float, nullable=True, comment="20-day Simple Moving Average")
    ma_50 = Column(Float, nullable=True, comment="50-day Simple Moving Average")
    trend_state = Column(
        String(32),
        nullable=True,
        comment="Trend: STRONG_BULLISH, BULLISH, NEUTRAL, BEARISH, STRONG_BEARISH",
    )
    source_used = Column(String(32), nullable=False, comment="Actual source used: FRED, YAHOO, STOOQ")
    fetched_at = Column(DateTime, server_default=func.now(), comment="Timestamp when record was ingested")

    # Unique constraint per indicator per record date
    __table_args__ = (
        UniqueConstraint("indicator_id", "record_date", name="uq_indicator_date"),
        Index("idx_indicator_values_query", "indicator_id", "record_date"),
    )

    # Relationships
    indicator = relationship("Indicator", back_populates="values")

    def __repr__(self) -> str:
        return f"<IndicatorValue(indicator_id='{self.indicator_id}', date='{self.record_date}', value={self.value})>"


class DailyReport(Base):
    """
    Generated daily macroeconomic reports stored as standardized Markdown.
    """
    __tablename__ = "daily_reports"

    id = Column(String(64), primary_key=True, comment="Report ID format: REPORT-YYYYMMDD")
    report_date = Column(Date, nullable=False, unique=True, index=True, comment="Publication report date")
    title = Column(String(255), nullable=False, comment="Headline title")
    summary = Column(Text, nullable=True, comment="Executive summary of 3-5 highlights")
    risk_level = Column(String(32), default="MEDIUM", comment="Macro risk assessment: LOW, MEDIUM, HIGH")
    content_markdown = Column(Text, nullable=False, comment="Full 5-section report in Markdown format")
    status = Column(String(32), default="PUBLISHED", comment="Status: DRAFT, PUBLISHED, FAILED")
    created_at = Column(DateTime, server_default=func.now(), comment="Creation timestamp")
    published_at = Column(DateTime, nullable=True, comment="Publication timestamp")

    __table_args__ = (
        Index("idx_daily_reports_date", "report_date"),
    )

    def __repr__(self) -> str:
        return f"<DailyReport(id='{self.id}', date='{self.report_date}', risk='{self.risk_level}')>"


class IngestionLog(Base):
    """
    Audit log records for every data fetching execution and failover event.
    """
    __tablename__ = "ingestion_logs"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    indicator_id = Column(String(64), ForeignKey("indicators.id"), nullable=True, index=True)
    source_id = Column(String(32), ForeignKey("data_sources.id"), nullable=True, index=True)
    status = Column(String(32), nullable=False, comment="Ingestion status: SUCCESS, FAILED, FALLBACK_SUCCESS")
    response_time_ms = Column(Integer, nullable=True, comment="Execution latency in milliseconds")
    error_message = Column(Text, nullable=True, comment="Captured exception or error description")
    executed_at = Column(DateTime, server_default=func.now(), index=True, comment="Execution timestamp")

    __table_args__ = (
        Index("idx_ingestion_logs_date", "executed_at"),
    )

    # Relationships
    indicator = relationship("Indicator", back_populates="logs")
    source = relationship("DataSource", back_populates="logs")

    def __repr__(self) -> str:
        return f"<IngestionLog(id={self.id}, indicator='{self.indicator_id}', status='{self.status}')>"
