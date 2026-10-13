"""
Stooq.com CSV Mirror Fetcher.
Secondary / Fallback data provider for equity indices, commodities, currencies, and bond yields.
Downloads and parses CSV feeds directly without authentication.
"""

import csv
from datetime import date, datetime
import io
import logging
from typing import List, Optional
import requests

from app.core.ingestion.base import BaseFetcher, DataPoint

logger = logging.getLogger(__name__)


class StooqFetcherError(Exception):
    """Custom exception for Stooq CSV fetching errors."""
    pass


class StooqFetcher(BaseFetcher):
    """Fetcher for Stooq.com daily CSV time series."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.base_url = "https://stooq.com/q/d/l/"

    def fetch_series(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[DataPoint]:
        """
        Fetch daily CSV from Stooq and parse into DataPoint list.
        URL format: https://stooq.com/q/d/l/?s={symbol}&i=d
        """
        params = {"s": symbol, "i": "d"}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }

        try:
            response = requests.get(self.base_url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            text = response.text
        except requests.exceptions.RequestException as exc:
            logger.error("Stooq request failed for symbol '%s': %s", symbol, exc)
            raise StooqFetcherError(f"Stooq request failed: {exc}") from exc

        # Check for empty or "no data" message
        if not text or "No data" in text or "Exceeded the daily hits limit" in text:
            raise StooqFetcherError(f"Stooq returned no data or hit limit for '{symbol}'")

        data_points: List[DataPoint] = []
        try:
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                date_str = row.get("Date", "").strip()
                close_str = row.get("Close", "").strip()
                if not date_str or not close_str:
                    continue

                try:
                    rec_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if start_date and rec_date < start_date:
                        continue
                    if end_date and rec_date > end_date:
                        continue
                    close_val = float(close_str)
                    data_points.append(DataPoint(record_date=rec_date, value=close_val))
                except ValueError:
                    continue
        except Exception as exc:
            raise StooqFetcherError(f"Failed to parse CSV response from Stooq for '{symbol}': {exc}") from exc

        if not data_points:
            raise StooqFetcherError(f"No valid historical records found in Stooq CSV for '{symbol}'")

        data_points.sort(key=lambda dp: dp.record_date)
        return data_points
