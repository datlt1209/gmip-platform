"""
Application Configuration Module for GMIP.
Manages environment variables, secrets, and system settings using Pydantic Settings.
"""

from functools import lru_cache
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """System settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General App Config
    PROJECT_NAME: str = Field(
        default="Global Macro Intelligence Platform (GMIP)",
        description="Application name",
    )
    API_V1_PREFIX: str = Field(
        default="/api/v1",
        description="Prefix for API version 1 routes",
    )
    ENVIRONMENT: str = Field(
        default="development",
        description="Deployment environment (development, staging, production)",
    )
    DEBUG: bool = Field(
        default=True,
        description="Debug flag for detailed logging",
    )
    TIMEZONE: str = Field(
        default="Asia/Ho_Chi_Minh",
        description="Application business timezone",
    )

    # Server Bindings
    HOST: str = Field(default="0.0.0.0", description="Server host interface")
    PORT: int = Field(default=8000, description="Server port")

    # Database Settings
    DATABASE_URL: str = Field(
        default="sqlite:///./data/gmip.db",
        description="Database connection URL (SQLite default or PostgreSQL)",
    )

    # External APIs & Authentication
    FRED_API_KEY: str = Field(
        default="",
        description="FRED API key from St. Louis Fed",
    )
    ADMIN_SECRET_KEY: str = Field(
        default="gmip-secure-secret-key-change-in-production",
        description="Secret key for protected admin endpoints",
    )

    # Network & Ingestion Controls
    REQUEST_TIMEOUT_SECONDS: int = Field(
        default=10,
        description="HTTP request timeout in seconds",
    )
    INGESTION_RATE_LIMIT_DELAY: float = Field(
        default=1.2,
        description="Delay in seconds between requests to avoid rate limiting",
    )
    MAX_RETRY_ATTEMPTS: int = Field(
        default=3,
        description="Maximum retry attempts on external API failure",
    )

    # CORS Settings
    CORS_ORIGINS: Union[str, List[str]] = Field(
        default="*",
        description="Allowed CORS origins (wildcard or comma-separated/list)",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        """Parse comma-separated string or list into List[str]."""
        if isinstance(value, str):
            if value.strip() == "*":
                return ["*"]
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache()
def get_settings() -> Settings:
    """Return cached singleton instance of system settings."""
    return Settings()
