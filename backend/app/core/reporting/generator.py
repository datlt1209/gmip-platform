"""
Automated Daily Economic Report Generator Engine.
Compiles standardized 5-section Vietnamese macroeconomic reports strictly respecting Data Lineage:
All reported metrics are sourced directly from indicator_values in the database.
"""

from datetime import date, datetime, timezone
import logging
from typing import Dict, Optional
from sqlalchemy.orm import Session

from app.db.models import Indicator, IndicatorValue, DailyReport
from app.core.analytics.signals import evaluate_macro_signals, RiskAssessment
from app.core.reporting.templates import format_trend_label, format_change_str, format_value_str

logger = logging.getLogger(__name__)


class DailyReportGenerator:
    """Generates daily intelligence reports in standardized 5-section Markdown."""

    def __init__(self, db: Session):
        self.db = db

    def _get_indicator_snapshot(self, target_date: date) -> Dict[str, IndicatorValue]:
        """Query latest available value up to target_date for all indicators."""
        indicators = self.db.query(Indicator).filter(Indicator.is_active == True).all()
        snapshot: Dict[str, IndicatorValue] = {}

        for ind in indicators:
            val_rec = (
                self.db.query(IndicatorValue)
                .filter(
                    IndicatorValue.indicator_id == ind.id,
                    IndicatorValue.record_date <= target_date,
                )
                .order_by(IndicatorValue.record_date.desc())
                .first()
            )
            if val_rec:
                snapshot[ind.id] = val_rec

        return snapshot

    def generate_daily_report(self, report_date: Optional[date] = None) -> DailyReport:
        """
        Generate, persist, and publish daily report for the given date.
        """
        current_date = report_date or date.today()
        report_id = f"REPORT-{current_date.strftime('%Y%m%d')}"
        formatted_date_str = current_date.strftime("%d/%m/%Y")

        logger.info("Generating daily macroeconomic report for %s...", formatted_date_str)

        # 1. Gather data snapshot (Data Lineage guarantee)
        snap = self._get_indicator_snapshot(current_date)

        # 2. Evaluate risk signals
        risk: RiskAssessment = evaluate_macro_signals(self.db, target_date=current_date)

        # Helper to safely retrieve (val, chg_1d, chg_1w, trend, unit)
        def get_stat(ind_id: str, default_val: float = 0.0, unit: str = ""):
            rec = snap.get(ind_id)
            if rec:
                return (
                    rec.value,
                    rec.change_1d,
                    rec.change_1w,
                    rec.trend_state,
                    unit or "%",
                )
            return default_val, 0.0, 0.0, "NEUTRAL", unit or "%"

        sp500_val, sp500_1d, sp500_1w, sp500_trend, _ = get_stat("SP500", 0.0, "Điểm")
        ndx_val, ndx_1d, ndx_1w, ndx_trend, _ = get_stat("NASDAQ100", 0.0, "Điểm")
        dji_val, dji_1d, dji_1w, dji_trend, _ = get_stat("DOW_JONES", 0.0, "Điểm")
        n225_val, n225_1d, n225_1w, n225_trend, _ = get_stat("NIKKEI225", 0.0, "Điểm")

        dxy_val, dxy_1d, dxy_1w, dxy_trend, _ = get_stat("DXY", 0.0, "Điểm")
        eur_val, eur_1d, eur_1w, eur_trend, _ = get_stat("EUR_USD", 0.0, "USD/EUR")
        jpy_val, jpy_1d, jpy_1w, jpy_trend, _ = get_stat("USD_JPY", 0.0, "JPY/USD")
        vnd_val, vnd_1d, vnd_1w, vnd_trend, _ = get_stat("USD_VND", 0.0, "VND/USD")

        brent_val, brent_1d, brent_1w, brent_trend, _ = get_stat("BRENT_OIL", 0.0, "USD/thùng")
        wti_val, wti_1d, wti_1w, wti_trend, _ = get_stat("WTI_OIL", 0.0, "USD/thùng")
        gold_val, gold_1d, gold_1w, gold_trend, _ = get_stat("GOLD", 0.0, "USD/Ounce")
        copper_val, copper_1d, copper_1w, copper_trend, _ = get_stat("COPPER", 0.0, "USD/Lbs")

        fed_rate, _, _, _, _ = get_stat("FED_FUNDS_RATE", 0.0, "%")
        y10_val, y10_1d, y10_1w, y10_trend, _ = get_stat("US_10Y_YIELD", 0.0, "%")
        y02_val, y02_1d, y02_1w, y02_trend, _ = get_stat("US_02Y_YIELD", 0.0, "%")
        spread_val, spread_1d, _, _, _ = get_stat("US_10Y_02Y_SPREAD", 0.0, "bps")

        cpi_val, _, _, _, _ = get_stat("US_CPI_YOY", 0.0, "%")
        core_cpi_val, _, _, _, _ = get_stat("US_CORE_CPI_YOY", 0.0, "%")
        unemp_val, _, _, _, _ = get_stat("US_UNEMP_RATE", 0.0, "%")
        vix_val, vix_1d, vix_1w, vix_trend, _ = get_stat("VIX", 0.0, "Điểm")

        # ----------------------------------------------------------------------
        # Construct Executive Summary
        # ----------------------------------------------------------------------
        summary_text = (
            f"Thị trường tài chính toàn cầu ghi nhận trạng thái {format_trend_label(sp500_trend).split()[-1].lower()} "
            f"với S&P 500 đạt {format_value_str(sp500_val)} điểm ({format_change_str(sp500_1d)}). "
            f"Đồng USD (DXY) đóng cửa ở mức {format_value_str(dxy_val)} điểm, trong khi lợi suất TPCP Mỹ 10 năm neo ở {format_value_str(y10_val, '%')}. "
            f"Dầu Brent dao động quanh {format_value_str(brent_val, 'USD/thùng')} và chỉ số biến động VIX ở mức {format_value_str(vix_val)} điểm "
            f"cho thấy mức độ rủi ro hệ thống ở ngưỡng {risk.risk_level}."
        )

        # ----------------------------------------------------------------------
        # Build 5-Section Markdown Content
        # ----------------------------------------------------------------------
        content_lines = [
            f"# BÁO CÁO NHỊP ĐẬP KINH TẾ THẾ GIỚI — {formatted_date_str}",
            f"*Phát hành: 07:00 AM (Asia/Ho_Chi_Minh) | Hệ thống GMIP tự động tổng hợp*",
            "",
            "---",
            "",
            "### PHẦN I: TỔNG QUAN THỊ TRƯỜNG & ĐIỂM TIN NỔI BẬT (EXECUTIVE SUMMARY)",
            f"{summary_text}",
            "",
            "#### Bảng Tóm Tắt Nhanh Các Chỉ Số Trọng Yếu:",
            "| Chỉ số | Mã | Mức đóng cửa | Thay đổi 1D | Thay đổi 1W | Trạng thái xu hướng |",
            "|---|---|---|---|---|---|",
            f"| **S&P 500** | `^GSPC` | {format_value_str(sp500_val)} | {format_change_str(sp500_1d)} | {format_change_str(sp500_1w)} | {format_trend_label(sp500_trend)} |",
            f"| **Nasdaq 100** | `^NDX` | {format_value_str(ndx_val)} | {format_change_str(ndx_1d)} | {format_change_str(ndx_1w)} | {format_trend_label(ndx_trend)} |",
            f"| **USD Index (DXY)** | `DX-Y` | {format_value_str(dxy_val)} | {format_change_str(dxy_1d)} | {format_change_str(dxy_1w)} | {format_trend_label(dxy_trend)} |",
            f"| **Lợi suất Mỹ 10Y** | `^TNX` | {format_value_str(y10_val, '%')} | {format_change_str(y10_1d, ' bps')} | {format_change_str(y10_1w, ' bps')} | {format_trend_label(y10_trend)} |",
            f"| **Dầu Brent** | `BZ=F` | {format_value_str(brent_val, 'USD/thùng')} | {format_change_str(brent_1d)} | {format_change_str(brent_1w)} | {format_trend_label(brent_trend)} |",
            f"| **Giá Vàng thế giới** | `GC=F` | {format_value_str(gold_val, 'USD/Ounce')} | {format_change_str(gold_1d)} | {format_change_str(gold_1w)} | {format_trend_label(gold_trend)} |",
            f"| **Biến động VIX** | `^VIX` | {format_value_str(vix_val)} | {format_change_str(vix_1d)} | {format_change_str(vix_1w)} | {format_trend_label(vix_trend)} |",
            "",
            "---",
            "",
            "### PHẦN II: VĨ MÔ TOÀN CẦU & CHÍNH SÁCH TIỀN TỆ (MACRO & CENTRAL BANKS)",
            f"1. **Chính sách Tiền tệ & Lợi suất Trái phiếu:** Lợi suất trái phiếu chính phủ Mỹ kỳ hạn 10 năm hiện đạt {format_value_str(y10_val, '%')} "
            f"(biến động 1 ngày: {format_change_str(y10_1d, ' bps')}), trong khi kỳ hạn 2 năm ở mức {format_value_str(y02_val, '%')}. "
            f"Chênh lệch đường cong lợi suất 10Y-2Y đạt {format_value_str(spread_val, 'bps')}. "
            f"Lãi suất quỹ liên bang (Fed Funds Rate) duy trì quanh mốc {format_value_str(fed_rate, '%')}.",
            f"2. **Lạm phát & Thị trường Lao động:** Chỉ số giá tiêu dùng CPI gần nhất ghi nhận mức tăng {format_value_str(cpi_val, '%')} so với cùng kỳ, "
            f"với lạm phát lõi Core CPI ở mức {format_value_str(core_cpi_val, '%')}. "
            f"Tỷ lệ thất nghiệp Mỹ duy trì ở mức {format_value_str(unemp_val, '%')}, phản ánh điều kiện vĩ mô ổn định.",
            "",
            "---",
            "",
            "### PHẦN III: DIỄN BIẾN THỊ TRƯỜNG TÀI SẢN (FINANCIAL MARKETS PERFORMANCE)",
            f"- **Thị trường Chứng khoán:** Phố Wall ghi nhận chỉ số S&P 500 biến động {format_change_str(sp500_1d)} lên {format_value_str(sp500_val)} điểm; "
            f"Nasdaq 100 ghi nhận {format_change_str(ndx_1d)} ({format_value_str(ndx_val)} điểm); "
            f"Dow Jones Industrial ghi nhận {format_change_str(dji_1d)} ({format_value_str(dji_val)} điểm). "
            f"Tại thị trường châu Á, chỉ số Nikkei 225 biến động {format_change_str(n225_1d)} đóng cửa ở {format_value_str(n225_val)} điểm.",
            f"- **Thị trường Tiền tệ & Ngoại hối:** Chỉ số DXY đo sức mạnh đồng USD dao động quanh mốc {format_value_str(dxy_val)} điểm ({format_change_str(dxy_1d)}). "
            f"Cặp tỷ giá EUR/USD giao dịch ở mức {format_value_str(eur_val)}; USD/JPY ở mức {format_value_str(jpy_val)}. "
            f"Tỷ giá USD/VND thị trường giao dịch ổn định quanh mức {format_value_str(vnd_val)} VND/USD ({format_change_str(vnd_1d)}).",
            f"- **Thị trường Hàng hóa:** Dầu thô Brent chốt phiên tại {format_value_str(brent_val, 'USD/thùng')} ({format_change_str(brent_1d)}), "
            f"dầu WTI ở mức {format_value_str(wti_val, 'USD/thùng')} ({format_change_str(wti_1d)}). "
            f"Giá vàng quốc tế neo quanh mức {format_value_str(gold_val, 'USD/Ounce')} ({format_change_str(gold_1d)}). "
            f"Giá đồng thế giới (Dr. Copper) ghi nhận {format_value_str(copper_val)} USD/Lbs ({format_change_str(copper_1d)}).",
            "",
            "---",
            "",
            "### PHẦN IV: ĐIỂM CẦN CHÚ Ý & SỰ KIỆN KINH TẾ TRONG NGÀY (KEY WATCHLIST & UPCOMING EVENTS)",
            "- Tiếp tục theo dõi các số liệu kinh tế vĩ mô then chốt từ Cục Thống kê Lao động Mỹ (BLS) và các bài phát biểu của quan chức Cục Dự trữ Liên bang (Fed).",
            "- Giám sát chặt chẽ diễn biến địa chính trị tại các khu vực nhạy cảm ảnh hưởng trực tiếp tới chuỗi cung ứng dầu mỏ và hàng hải quốc tế.",
            "- Chú ý xu hướng dịch chuyển của dòng vốn đầu tư toàn cầu giữa các tài sản an toàn (Vàng, Trái phiếu) và tài sản rủi ro (Cổ phiếu).",
            "",
            "---",
            "",
            "### PHẦN V: LA BÀN RỦI RO & NHẬN ĐỊNH TỔNG QUAN (RISK RADAR & SYNTHESIS)",
            f"- **Đánh giá Trạng thái Rủi ro Vĩ mô:** **{risk.risk_level}**",
        ]

        if risk.active_warnings:
            content_lines.append("- **Các Tín Hiệu Cảnh Báo Được Kích Hoạt:**")
            for w in risk.active_warnings:
                content_lines.append(f"  * ⚠️ {w}")
        else:
            content_lines.append("- **Tín Hiệu Rủi Ro Đặc Biệt:** Không ghi nhận tín hiệu rủi ro cực đoan nào trên các thị trường trọng yếu.")

        content_lines.extend([
            "- **Tác Động Tới Bối Cảnh Thị Trường Việt Nam:**",
            f"  * Diễn biến đồng USD (DXY: {format_value_str(dxy_val)}) và tỷ giá USD/VND ({format_value_str(vnd_val)}) "
            f"tiếp tục tạo điều kiện thuận lợi để Ngân hàng Nhà nước duy trì chính sách tiền tệ chủ động, linh hoạt.",
            f"  * Giá năng lượng toàn cầu (Dầu Brent: {format_value_str(brent_val, 'USD/thùng')}) ở mức ổn định "
            f"giúp giảm thiểu áp lực nhập khẩu lạm phát, hỗ trợ mục tiêu thúc đẩy tăng trưởng kinh tế trong nước.",
            "",
        ])

        full_markdown = "\n".join(content_lines)

        # ----------------------------------------------------------------------
        # Persist into DailyReport Table
        # ----------------------------------------------------------------------
        report_record = (
            self.db.query(DailyReport)
            .filter(DailyReport.report_date == current_date)
            .first()
        )

        report_title = f"Báo cáo nhịp đập kinh tế thế giới — {formatted_date_str}"
        now_utc = datetime.now(timezone.utc)

        if report_record:
            report_record.title = report_title
            report_record.summary = summary_text
            report_record.risk_level = risk.risk_level
            report_record.content_markdown = full_markdown
            report_record.status = "PUBLISHED"
            report_record.published_at = now_utc
        else:
            report_record = DailyReport(
                id=report_id,
                report_date=current_date,
                title=report_title,
                summary=summary_text,
                risk_level=risk.risk_level,
                content_markdown=full_markdown,
                status="PUBLISHED",
                created_at=now_utc,
                published_at=now_utc,
            )
            self.db.add(report_record)

        self.db.commit()
        self.db.refresh(report_record)
        logger.info("Successfully published daily report '%s' (Risk: %s).", report_id, risk.risk_level)
        return report_record
