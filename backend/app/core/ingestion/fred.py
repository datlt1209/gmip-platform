"""
FRED (Federal Reserve Economic Data) API Ingestion Fetcher.
Fetches macroeconomic data points (CPI, GDP, Fed Funds, Yield spreads) from St. Louis Fed.
"""

from datetime import date, datetime
import logging
from typing import List, Optional
import requests

from app.config import get_settings
from app.core.ingestion.base import BaseFetcher, DataPoint

logger = logging.getLogger(__name__)


class FredFetcherError(Exception):
    """Custom exception for FRED fetching errors."""
    pass


class FredFetcher(BaseFetcher):
    """Fetcher for FRED REST API."""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 10):
        settings = get_settings()
        self.api_key = api_key or settings.FRED_API_KEY
        self.timeout = timeout
        self.base_url = "https://api.stlouisfed.org/fred/series/observations"

    def fetch_series(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[DataPoint]:
        """
        Fetch series observations from FRED API.
        """
        if not self.api_key:
            raise FredFetcherError("FRED API key is not configured.")

        params = {
            "series_id": symbol,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "asc",
        }
        if start_date:
            params["observation_start"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["observation_end"] = end_date.strftime("%Y-%m-%d")

        try:
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as exc:
            logger.error("FRED API request failed for symbol '%s': %s", symbol, exc)
            raise FredFetcherError(f"FRED API request failed: {exc}") from exc
        except ValueError as exc:
            logger.error("FRED API JSON decode error for symbol '%s': %s", symbol, exc)
            raise FredFetcherError(f"Invalid JSON received from FRED: {exc}") from exc

        observations = data.get("observations", [])
        data_points: List[DataPoint] = []

        for obs in observations:
            val_str = obs.get("value", "").strip()
            date_str = obs.get("date", "").strip()
            if not val_str or val_str == "." or not date_str:
                continue

            try:
                rec_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                val_float = float(val_str)
                data_points.append(DataPoint(record_date=rec_date, value=val_float))
            except ValueError:
                continue

        # Ensure chronological ordering
        data_points.sort(key=lambda dp: dp.record_date)
        return data_points
