"""
Base Data Ingestion Classes and Data Sanitizer / Validator.
Defines common interfaces and validation rules according to docs/TECH_ARCHITECTURE.md Section 5.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
import math
from typing import List, Optional, Tuple


@dataclass
class DataPoint:
    """Standardized single observation point."""
    record_date: date
    value: float


class BaseFetcher(ABC):
    """Abstract Base Class for all market and macroeconomic data fetchers."""

    @abstractmethod
    def fetch_series(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[DataPoint]:
        """
        Fetch historical time-series data for a given symbol.
        Must return a chronologically sorted list of DataPoint objects.
        """
        pass


def validate_indicator_value(
    indicator_id: str,
    value: float,
    prev_value: Optional[float] = None,
    category: str = "",
) -> Tuple[bool, Optional[str]]:
    """
    Data Sanity Check (Kiểm tra rác) according to docs/TECH_ARCHITECTURE.md Section 5:
    1. Value must not be None, NaN, or infinite.
    2. Value must not be negative for assets strictly requiring positivity (Equity, Commodity, FX, Sentiment).
    3. Daily variation must not exceed +/- 50% compared to previous session (avoids decimal formatting errors),
       except for interest rate spreads which can jump in bps.

    Returns:
        (is_valid, error_reason)
    """
    if value is None:
        return False, f"Indicator {indicator_id}: Value is None"

    if math.isnan(value) or math.isinf(value):
        return False, f"Indicator {indicator_id}: Value is NaN or Inf"

    # Positivity check for non-rate assets
    cat = category.upper()
    non_negative_categories = {"EQUITY", "COMMODITY", "FX", "SENTIMENT"}
    if cat in non_negative_categories and value <= 0:
        return False, f"Indicator {indicator_id}: Non-positive value ({value}) invalid for category {cat}"

    # Extreme variation check (+/- 50% threshold for non-rate assets)
    if prev_value is not None and prev_value > 0 and cat not in {"RATES", "MACRO"}:
        pct_change = abs(value - prev_value) / prev_value
        if pct_change > 0.50:
            return (
                False,
                f"Indicator {indicator_id}: Extreme change detected ({pct_change*100:.2f}% > 50%) "
                f"from previous {prev_value} to {value}",
            )

    return True, None
