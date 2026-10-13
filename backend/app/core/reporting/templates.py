"""
Report Formatting Helpers and Vietnamese Template Utilities.
Provides standard trend labels, formatters, and report section templates.
"""

from typing import Dict, Any, Optional


TREND_LABELS = {
    "STRONG_BULLISH": "🟢🔼 Tăng mạnh",
    "BULLISH": "🟢▲ Tăng nhẹ",
    "NEUTRAL": "⚪➖ Đi ngang / Ổn định",
    "BEARISH": "🔴▼ Giảm nhẹ",
    "STRONG_BEARISH": "🔴🔽 Giảm mạnh",
}


def format_trend_label(trend_state: Optional[str]) -> str:
    """Return Vietnamese display label for a trend state."""
    return TREND_LABELS.get(trend_state or "NEUTRAL", "⚪➖ Đi ngang")


def format_change_str(change: Optional[float], unit: str = "%") -> str:
    """Format numeric change with positive sign and unit."""
    if change is None:
        return "N/A"
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.2f}{unit}"


def format_value_str(val: Optional[float], unit: str = "") -> str:
    """Format numeric value with proper decimals and unit."""
    if val is None:
        return "N/A"
    if unit == "$/thùng" or unit == "USD/thùng":
        return f"${val:,.2f}/thùng"
    elif unit == "USD/Ounce":
        return f"${val:,.2f}/oz"
    elif unit == "%":
        return f"{val:.2f}%"
    elif unit == "bps":
        return f"{val:+.1f} bps"
    elif val > 1000:
        return f"{val:,.2f}"
    else:
        return f"{val:.4f}" if val < 10 else f"{val:.2f}"
