"""
Yahoo Finance Ingestion Fetcher.
Fetches equity indices, commodities, currencies, and volatility (VIX).
Implements rate-limit throttling (1.5s), strict 10s timeout, and 3-attempt exponential backoff (2s, 4s, 8s).
"""

from datetime import date, datetime
import logging
import time
from typing import List, Optional
import yfinance as yf
import requests

from app.core.ingestion.base import BaseFetcher, DataPoint

logger = logging.getLogger(__name__)


class YahooFetcherError(Exception):
    """Custom exception for Yahoo Finance fetching failures."""
    pass


class YahooFetcher(BaseFetcher):
    """Fetcher for Yahoo Finance with anti-ban throttling and exponential backoff."""

    def __init__(
        self,
        timeout: int = 10,
        throttle_seconds: float = 1.5,
        max_retries: int = 3,
        backoff_delays: Optional[List[float]] = None,
    ):
        self.timeout = timeout
        self.throttle_seconds = throttle_seconds
        self.max_retries = max_retries
        self.backoff_delays = backoff_delays if backoff_delays is not None else [2.0, 4.0, 8.0]
        self.last_request_time: float = 0.0

    def _throttle(self) -> None:
        """Enforce spacing between successive requests to prevent HTTP 429 rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.throttle_seconds:
            sleep_time = self.throttle_seconds - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def fetch_series(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[DataPoint]:
        """
        Fetch historical daily prices from Yahoo Finance with retry and backoff.
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                self._throttle()
                return self._fetch_internal(symbol, start_date, end_date)
            except Exception as exc:
                last_exception = exc
                delay = (
                    self.backoff_delays[attempt]
                    if attempt < len(self.backoff_delays)
                    else 2.0 ** (attempt + 1)
                )
                logger.warning(
                    "YahooFetcher attempt %d/%d failed for '%s': %s. Retrying in %.1fs...",
                    attempt + 1,
                    self.max_retries,
                    symbol,
                    exc,
                    delay,
                )
                if attempt < self.max_retries - 1 and delay > 0:
                    time.sleep(delay)

        raise YahooFetcherError(
            f"Failed to fetch data from Yahoo Finance for '{symbol}' after {self.max_retries} attempts: {last_exception}"
        ) from last_exception

    def _fetch_internal(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[DataPoint]:
        """Internal worker fetching via yfinance or REST chart API."""
        try:
            ticker = yf.Ticker(symbol)
            # Fetch 1 month or custom range
            if start_date:
                df = ticker.history(
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d") if end_date else None,
                    timeout=self.timeout,
                )
            else:
                df = ticker.history(period="1mo", timeout=self.timeout)

            if df is not None and not df.empty and "Close" in df.columns:
                points: List[DataPoint] = []
                for dt_idx, row in df.iterrows():
                    val = float(row["Close"])
                    rec_date = dt_idx.date() if hasattr(dt_idx, "date") else dt_idx
                    if val is not None and not (isinstance(val, float) and (val != val)):  # check NaN
                        points.append(DataPoint(record_date=rec_date, value=val))
                if points:
                    points.sort(key=lambda dp: dp.record_date)
                    return points
        except Exception as exc:
            logger.debug("yfinance history failed for '%s' (%s), trying direct chart REST API...", symbol, exc)

        # Fallback to direct Yahoo Chart API if yfinance fails
        return self._fetch_via_rest(symbol, start_date, end_date)

    def _fetch_via_rest(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[DataPoint]:
        """Direct REST call to Yahoo Chart API v8."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {"range": "1mo", "interval": "1d"}
        response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        result = data.get("chart", {}).get("result", [])
        if not result:
            raise YahooFetcherError(f"Empty result returned by Yahoo Chart API for '{symbol}'")

        timestamps = result[0].get("timestamp", [])
        indicators = result[0].get("indicators", {}).get("quote", [{}])[0]
        closes = indicators.get("close", [])

        data_points: List[DataPoint] = []
        for ts, close_val in zip(timestamps, closes):
            if close_val is not None:
                rec_date = datetime.fromtimestamp(ts).date()
                data_points.append(DataPoint(record_date=rec_date, value=float(close_val)))

        if not data_points:
            raise YahooFetcherError(f"No valid close prices found for '{symbol}' in Yahoo REST response")

        data_points.sort(key=lambda dp: dp.record_date)
        return data_points
