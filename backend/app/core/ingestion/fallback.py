"""
Failover Coordinator and Ingestion Pipeline Orchestrator.
Coordinates data ingestion across primary and fallback sources (FRED, Yahoo, Stooq).
Enforces sanity validation, structured audit logging (ingestion_logs), and resilient fallback.
"""

from datetime import date, datetime, timezone
import logging
import time
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session


from app.core.ingestion.base import BaseFetcher, DataPoint, validate_indicator_value
from app.core.ingestion.fred import FredFetcher
from app.core.ingestion.yahoo import YahooFetcher
from app.core.ingestion.stooq import StooqFetcher
from app.db.models import Indicator, IndicatorValue, IngestionLog

logger = logging.getLogger(__name__)

# Fallback symbol dictionary according to docs/SRS.md Section 2
FALLBACK_SYMBOLS: Dict[str, str] = {
    "SP500": "^SPX",
    "NASDAQ100": "^NDQ",
    "DOW_JONES": "^DJI",
    "NIKKEI225": "^NKX",
    "VIX": "^VIX",
    "GOLD": "XAUUSD",
    "COPPER": "HG.F",
    "DXY": "USD_I",
    "EUR_USD": "EURUSD",
    "USD_JPY": "USDJPY",
    "USD_VND": "VND=X",
    "US_MANUF_PMI": "^PMI",
    "US_10Y_YIELD": "DGS10",
    "US_02Y_YIELD": "DGS2",
    "BRENT_OIL": "DCOILBRENTEU",
    "WTI_OIL": "DCOILWTICO",
}


class FailoverCoordinator:
    """Coordinates fetching from primary source and falling back gracefully on failure."""

    def __init__(
        self,
        fred_fetcher: Optional[FredFetcher] = None,
        yahoo_fetcher: Optional[YahooFetcher] = None,
        stooq_fetcher: Optional[StooqFetcher] = None,
    ):
        self.fetchers: Dict[str, BaseFetcher] = {
            "FRED": fred_fetcher or FredFetcher(),
            "YAHOO": yahoo_fetcher or YahooFetcher(),
            "STOOQ": stooq_fetcher or StooqFetcher(),
        }

    def _get_fetcher(self, source_id: str) -> Optional[BaseFetcher]:
        """Get the fetcher instance mapped to a data source ID."""
        return self.fetchers.get(source_id.upper())

    def _log_ingestion_attempt(
        self,
        db: Session,
        indicator_id: str,
        source_id: str,
        status: str,
        response_time_ms: int,
        error_message: Optional[str] = None,
    ) -> IngestionLog:
        """Record an ingestion log entry in the database."""
        log_entry = IngestionLog(
            indicator_id=indicator_id,
            source_id=source_id,
            status=status,
            response_time_ms=response_time_ms,
            error_message=error_message,
            executed_at=datetime.now(timezone.utc),
        )
        db.add(log_entry)
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Failed to commit IngestionLog: %s", exc)
        return log_entry

    def ingest_indicator(
        self,
        indicator: Indicator,
        db: Session,
        target_date: Optional[date] = None,
    ) -> Tuple[bool, Optional[IndicatorValue], str]:
        """
        Ingest data for a single indicator following the failover lifecycle:
        1. Try Primary Source -> Validate Sanity -> Save to DB.
        2. If Primary fails -> Try Fallback Source -> Validate -> Save to DB.
        3. If Fallback fails -> Retain Last Known Value to prevent downtime.

        Returns:
            (is_success, indicator_value_record, source_used)
        """
        primary_source_id = indicator.primary_source_id.upper()
        fallback_source_id = (
            indicator.fallback_source_id.upper() if indicator.fallback_source_id else None
        )

        # Retrieve previous value for variation sanity checking
        prev_record = (
            db.query(IndicatorValue)
            .filter(IndicatorValue.indicator_id == indicator.id)
            .order_by(IndicatorValue.record_date.desc())
            .first()
        )
        prev_val = prev_record.value if prev_record else None

        # ----------------------------------------------------------------------
        # Step 1: Attempt Primary Source
        # ----------------------------------------------------------------------
        primary_fetcher = self._get_fetcher(primary_source_id)
        if primary_fetcher:
            t0 = time.time()
            try:
                data_points = primary_fetcher.fetch_series(indicator.symbol)
                elapsed_ms = int((time.time() - t0) * 1000)

                if not data_points:
                    raise ValueError(f"Primary source '{primary_source_id}' returned no data points")

                # Select latest observation or specific date
                target_point = data_points[-1]
                if target_date:
                    for dp in data_points:
                        if dp.record_date == target_date:
                            target_point = dp
                            break

                # Sanity validation
                is_valid, reason = validate_indicator_value(
                    indicator.id,
                    target_point.value,
                    prev_value=prev_val,
                    category=indicator.category,
                )
                if not is_valid:
                    raise ValueError(f"Sanity check failed: {reason}")

                # Success with primary source
                self._log_ingestion_attempt(
                    db=db,
                    indicator_id=indicator.id,
                    source_id=primary_source_id,
                    status="SUCCESS",
                    response_time_ms=elapsed_ms,
                )

                saved_record = self._save_or_update_value(
                    db=db,
                    indicator_id=indicator.id,
                    record_date=target_point.record_date,
                    value=target_point.value,
                    source_used=primary_source_id,
                )
                return True, saved_record, primary_source_id

            except Exception as exc:
                elapsed_ms = int((time.time() - t0) * 1000)
                logger.warning(
                    "Primary source '%s' failed for indicator '%s': %s",
                    primary_source_id,
                    indicator.id,
                    exc,
                )
                self._log_ingestion_attempt(
                    db=db,
                    indicator_id=indicator.id,
                    source_id=primary_source_id,
                    status="FAILED",
                    response_time_ms=elapsed_ms,
                    error_message=str(exc),
                )
        else:
            logger.error("Primary fetcher not configured for source '%s'", primary_source_id)

        # ----------------------------------------------------------------------
        # Step 2: Attempt Fallback Source (Circuit Breaker)
        # ----------------------------------------------------------------------
        if fallback_source_id:
            fallback_fetcher = self._get_fetcher(fallback_source_id)
            if fallback_fetcher:
                fb_symbol = FALLBACK_SYMBOLS.get(indicator.id, indicator.symbol)
                logger.info(
                    "Switching to fallback source '%s' (symbol: '%s') for indicator '%s'...",
                    fallback_source_id,
                    fb_symbol,
                    indicator.id,
                )
                t0_fb = time.time()
                try:
                    fb_points = fallback_fetcher.fetch_series(fb_symbol)
                    elapsed_fb_ms = int((time.time() - t0_fb) * 1000)

                    if not fb_points:
                        raise ValueError(f"Fallback source '{fallback_source_id}' returned no data points")

                    target_point = fb_points[-1]
                    if target_date:
                        for dp in fb_points:
                            if dp.record_date == target_date:
                                target_point = dp
                                break

                    is_valid, reason = validate_indicator_value(
                        indicator.id,
                        target_point.value,
                        prev_value=prev_val,
                        category=indicator.category,
                    )
                    if not is_valid:
                        raise ValueError(f"Fallback sanity check failed: {reason}")

                    # Fallback success
                    self._log_ingestion_attempt(
                        db=db,
                        indicator_id=indicator.id,
                        source_id=fallback_source_id,
                        status="FALLBACK_SUCCESS",
                        response_time_ms=elapsed_fb_ms,
                    )

                    saved_record = self._save_or_update_value(
                        db=db,
                        indicator_id=indicator.id,
                        record_date=target_point.record_date,
                        value=target_point.value,
                        source_used=fallback_source_id,
                    )
                    return True, saved_record, fallback_source_id

                except Exception as fb_exc:
                    elapsed_fb_ms = int((time.time() - t0_fb) * 1000)
                    logger.error(
                        "Fallback source '%s' also failed for indicator '%s': %s",
                        fallback_source_id,
                        indicator.id,
                        fb_exc,
                    )
                    self._log_ingestion_attempt(
                        db=db,
                        indicator_id=indicator.id,
                        source_id=fallback_source_id,
                        status="FAILED",
                        response_time_ms=elapsed_fb_ms,
                        error_message=str(fb_exc),
                    )

        # ----------------------------------------------------------------------
        # Step 3: Use Last Known Value (Resilience Fallback)
        # ----------------------------------------------------------------------
        if prev_record:
            logger.warning(
                "All ingestion attempts failed for '%s'. Retaining last known value (date=%s, value=%.2f).",
                indicator.id,
                prev_record.record_date,
                prev_record.value,
            )
            return True, prev_record, "LAST_KNOWN"

        logger.error("All ingestion sources failed and no historical record exists for '%s'.", indicator.id)
        return False, None, "NONE"

    def _save_or_update_value(
        self,
        db: Session,
        indicator_id: str,
        record_date: date,
        value: float,
        source_used: str,
    ) -> IndicatorValue:
        """Idempotently persist or update observed indicator value."""
        record = (
            db.query(IndicatorValue)
            .filter(
                IndicatorValue.indicator_id == indicator_id,
                IndicatorValue.record_date == record_date,
            )
            .first()
        )
        if record:
            record.value = value
            record.source_used = source_used
            record.fetched_at = datetime.now(timezone.utc)
        else:
            record = IndicatorValue(
                indicator_id=indicator_id,
                record_date=record_date,
                value=value,
                source_used=source_used,
                fetched_at=datetime.now(timezone.utc),
            )
            db.add(record)

        db.commit()
        db.refresh(record)
        return record

    def ingest_all(
        self,
        db: Session,
        target_date: Optional[date] = None,
        delay_between_requests: float = 0.0,
    ) -> Dict[str, int]:
        """
        Run the complete ingestion pipeline across all active indicators.
        Returns execution summary metrics.
        """
        indicators = db.query(Indicator).filter(Indicator.is_active == True).all()
        summary = {
            "total": len(indicators),
            "success": 0,
            "fallback_success": 0,
            "failed": 0,
        }

        logger.info("Starting batch ingestion for %d indicators...", len(indicators))
        for ind in indicators:
            success, _, source_used = self.ingest_indicator(ind, db=db, target_date=target_date)
            if success:
                if source_used == ind.primary_source_id:
                    summary["success"] += 1
                elif source_used != "NONE":
                    summary["fallback_success"] += 1
                else:
                    summary["failed"] += 1
            else:
                summary["failed"] += 1

            if delay_between_requests > 0:
                time.sleep(delay_between_requests)

        logger.info("Batch ingestion finished: %s", summary)
        return summary
