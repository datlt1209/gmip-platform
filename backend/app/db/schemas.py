"""
Pydantic Schemas / DTOs for GMIP.
Provides request validation and response serialization models for API endpoints.
"""

from datetime import date, datetime, timezone
from typing import Optional, List, Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# -----------------------------------------------------------------------------
# Common / Generic API Wrappers
# -----------------------------------------------------------------------------
class ApiResponse(BaseModel, Generic[T]):
    """Standard unified API response wrapper."""
    status: str = Field(default="success", description="Status code or text: success, error")
    data: Optional[T] = Field(default=None, description="Payload data")
    message: Optional[str] = Field(default=None, description="Human-readable message or error summary")


class HealthResponse(BaseModel):
    """System health check response."""
    status: str = Field(default="healthy", json_schema_extra={"example": "healthy"})
    version: str = Field(default="1.0.0", json_schema_extra={"example": "1.0.0"})
    database: str = Field(default="connected", json_schema_extra={"example": "connected"})
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



# -----------------------------------------------------------------------------
# Data Source Schemas
# -----------------------------------------------------------------------------
class DataSourceBase(BaseModel):
    id: str
    name: str
    base_url: str
    auth_type: str = "NONE"
    rate_limit_per_minute: int = 60
    is_active: bool = True


class DataSourceCreate(DataSourceBase):
    pass


class DataSourceResponse(DataSourceBase):
    model_config = ConfigDict(from_attributes=True)

    created_at: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Indicator Value Schemas
# -----------------------------------------------------------------------------
class IndicatorValueBase(BaseModel):
    record_date: date
    value: float
    change_1d: Optional[float] = None
    change_1w: Optional[float] = None
    change_1m: Optional[float] = None
    change_yoy: Optional[float] = None
    ma_20: Optional[float] = None
    ma_50: Optional[float] = None
    trend_state: Optional[str] = None
    source_used: str


class IndicatorValueCreate(IndicatorValueBase):
    indicator_id: str


class IndicatorValueResponse(IndicatorValueBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    indicator_id: str
    fetched_at: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Indicator Schemas
# -----------------------------------------------------------------------------
class IndicatorBase(BaseModel):
    id: str
    symbol: str
    name_vi: str
    name_en: str
    category: str
    unit: str
    frequency: str = "DAILY"
    primary_source_id: str
    fallback_source_id: Optional[str] = None
    priority: int = 1
    is_active: bool = True


class IndicatorCreate(IndicatorBase):
    pass


class IndicatorResponse(IndicatorBase):
    model_config = ConfigDict(from_attributes=True)

    created_at: Optional[datetime] = None


class IndicatorWithLatestValueResponse(IndicatorResponse):
    """Indicator details populated with its most recent historical value."""
    model_config = ConfigDict(from_attributes=True)

    latest_value: Optional[IndicatorValueResponse] = None


# -----------------------------------------------------------------------------
# Daily Report Schemas
# -----------------------------------------------------------------------------
class DailyReportBase(BaseModel):
    id: str
    report_date: date
    title: str
    summary: Optional[str] = None
    risk_level: str = "MEDIUM"
    content_markdown: str
    status: str = "PUBLISHED"


class DailyReportCreate(DailyReportBase):
    pass


class DailyReportSummaryResponse(BaseModel):
    """Lightweight summary of a daily report for archive listing."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    report_date: date
    title: str
    summary: Optional[str] = None
    risk_level: str
    status: str
    published_at: Optional[datetime] = None


class DailyReportResponse(DailyReportBase):
    """Full daily report object including complete Markdown content."""
    model_config = ConfigDict(from_attributes=True)

    created_at: Optional[datetime] = None
    published_at: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Ingestion Log Schemas
# -----------------------------------------------------------------------------
class IngestionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    indicator_id: Optional[str] = None
    source_id: Optional[str] = None
    status: str
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    executed_at: Optional[datetime] = None
