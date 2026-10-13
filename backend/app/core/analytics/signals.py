"""
Risk Signals and Macro Warning Detection Engine.
Identifies macroeconomic risk events:
1. Inverted Yield Curve (10Y - 2Y Spread < 0)
2. Extreme Market Fear (VIX >= 30.0)
3. Energy Price Shock (Brent / WTI 1D change >= +4.0%)
Evaluates overall macro risk level: LOW, MEDIUM, HIGH according to docs/SRS.md Section 4.3.
"""

from dataclasses import dataclass, field
from datetime import date
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models import IndicatorValue

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    """Consolidated macroeconomic risk appraisal and detected warnings."""
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    active_warnings: List[str] = field(default_factory=list)
    yield_spread: Optional[float] = None
    vix_value: Optional[float] = None
    oil_max_change_1d: Optional[float] = None


def check_inverted_yield_curve(
    spread_val: Optional[float] = None,
    yield_10y: Optional[float] = None,
    yield_02y: Optional[float] = None,
) -> Optional[str]:
    """
    Check for inverted yield curve condition: Spread < 0 or (10Y - 2Y < 0).
    """
    effective_spread = spread_val
    if effective_spread is None and yield_10y is not None and yield_02y is not None:
        effective_spread = yield_10y - yield_02y

    if effective_spread is not None and effective_spread < 0:
        return (
            "Cảnh báo: Đường cong lợi suất đảo ngược — "
            "Tín hiệu lịch sử dự báo suy thoái kinh tế Mỹ trong 6-18 tháng tới."
        )
    return None


def check_vix_extreme_fear(vix_value: Optional[float]) -> Optional[str]:
    """
    Check for extreme volatility and defensive positioning: VIX >= 30.0.
    """
    if vix_value is not None and vix_value >= 30.0:
        return (
            "Cảnh báo: Chỉ số biến động VIX vượt ngưỡng 30 điểm — "
            "Thị trường chứng khoán thế giới đang trong trạng thái phòng thủ và hoảng loạn."
        )
    return None


def check_energy_price_shock(
    brent_change_1d: Optional[float] = None,
    wti_change_1d: Optional[float] = None,
) -> Optional[str]:
    """
    Check for energy price spike: 1-day change in Brent or WTI >= +4.0%.
    """
    max_change = None
    for chg in (brent_change_1d, wti_change_1d):
        if chg is not None and (max_change is None or chg > max_change):
            max_change = chg

    if max_change is not None and max_change >= 4.0:
        return (
            "Cảnh báo: Giá dầu biến động đột biến — "
            "Áp lực lạm phát vĩ mô có xu hướng quay trở lại."
        )
    return None


def evaluate_macro_signals(db: Session, target_date: Optional[date] = None) -> RiskAssessment:
    """
    Query latest database values for risk indicators and evaluate macro risk status.
    """
    def get_latest_val(indicator_id: str) -> Optional[IndicatorValue]:
        query = db.query(IndicatorValue).filter(IndicatorValue.indicator_id == indicator_id)
        if target_date:
            query = query.filter(IndicatorValue.record_date <= target_date)
        return query.order_by(IndicatorValue.record_date.desc()).first()

    spread_rec = get_latest_val("US_10Y_02Y_SPREAD")
    y10_rec = get_latest_val("US_10Y_YIELD")
    y02_rec = get_latest_val("US_02Y_YIELD")
    vix_rec = get_latest_val("VIX")
    brent_rec = get_latest_val("BRENT_OIL")
    wti_rec = get_latest_val("WTI_OIL")

    # Extract observed values
    spread_val = spread_rec.value if spread_rec else None
    y10_val = y10_rec.value if y10_rec else None
    y02_val = y02_rec.value if y02_rec else None
    vix_val = vix_rec.value if vix_rec else None
    brent_1d = brent_rec.change_1d if brent_rec else None
    wti_1d = wti_rec.change_1d if wti_rec else None

    # Detect individual warning signals
    warnings: List[str] = []

    # 1. Inverted Curve Check
    inversion_msg = check_inverted_yield_curve(spread_val, y10_val, y02_val)
    if inversion_msg:
        warnings.append(inversion_msg)

    # 2. VIX Check
    vix_msg = check_vix_extreme_fear(vix_val)
    if vix_msg:
        warnings.append(vix_msg)

    # 3. Energy Shock Check
    oil_msg = check_energy_price_shock(brent_1d, wti_1d)
    if oil_msg:
        warnings.append(oil_msg)

    # Overall Risk Classification
    # HIGH: Inverted yield curve, VIX >= 30, or multiple warning triggers
    if inversion_msg or (vix_val is not None and vix_val >= 30.0) or len(warnings) >= 2:
        risk_level = "HIGH"
    elif (vix_val is not None and vix_val >= 20.0) or len(warnings) == 1:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    max_oil_change = max([c for c in (brent_1d, wti_1d) if c is not None], default=None)

    return RiskAssessment(
        risk_level=risk_level,
        active_warnings=warnings,
        yield_spread=spread_val if spread_val is not None else ((y10_val - y02_val) if y10_val and y02_val else None),
        vix_value=vix_val,
        oil_max_change_1d=max_oil_change,
    )
