import type { DailyReport, HistoryPoint, Indicator, RangeKey, ReportSummary } from "@/types";

const DEFS: Array<[string, string, string, Indicator["category"], string, number, number]> = [
  // MACRO (6)
  ["US_CPI_YOY", "CPIAUCSL", "Lạm phát CPI Mỹ (YoY)", "MACRO", "%", 2.4, 0.08],
  ["US_CORE_CPI_YOY", "CPILFESL", "Lạm phát lõi Mỹ (Core CPI YoY)", "MACRO", "%", 3.2, 0.06],
  ["US_GDP_QOQ", "A191RL1Q225SBEA", "Tăng trưởng GDP Mỹ (QoQ)", "MACRO", "%", 2.8, 0.1],
  ["US_UNEMP_RATE", "UNRATE", "Tỷ lệ thất nghiệp Mỹ", "MACRO", "%", 4.1, 0.05],
  ["US_NONFARM_PAYROLL", "PAYEMS", "Bảng lương phi nông nghiệp", "MACRO", "Nghìn", 254, 12],
  ["US_MANUF_PMI", "ISM_PMI", "Chỉ số sản xuất PMI (ISM)", "MACRO", "Điểm", 47.2, 0.4],
  // RATES (5)
  ["FED_FUNDS_RATE", "FEDFUNDS", "Lãi suất điều hành Fed", "RATES", "%", 4.83, 0.02],
  ["US_10Y_YIELD", "^TNX", "Lợi suất TPCP Mỹ 10 năm", "RATES", "%", 4.15, 0.04],
  ["US_02Y_YIELD", "^IRX", "Lợi suất TPCP Mỹ 2 năm", "RATES", "%", 3.98, 0.04],
  ["US_10Y_02Y_SPREAD", "T10Y2Y", "Chênh lệch lợi suất 10Y-2Y", "RATES", "bps", 17, 2.5],
  ["ECB_DEPOSIT_RATE", "ECBDFR", "Lãi suất tiền gửi ECB", "RATES", "%", 3.5, 0.02],
  // FX (4)
  ["DXY", "DX-Y.NYB", "Chỉ số sức mạnh đồng USD (DXY)", "FX", "Điểm", 102.85, 0.35],
  ["EUR_USD", "EURUSD=X", "Tỷ giá EUR/USD", "FX", "USD/EUR", 1.0925, 0.004],
  ["USD_JPY", "JPY=X", "Tỷ giá USD/JPY", "FX", "JPY/USD", 149.2, 0.6],
  ["USD_VND", "VND=X", "Tỷ giá USD/VND", "FX", "VND/USD", 24850, 35],
  // COMMODITY (4)
  ["BRENT_OIL", "BZ=F", "Giá dầu thô Brent", "COMMODITY", "USD/thùng", 84.2, 1.1],
  ["WTI_OIL", "CL=F", "Giá dầu thô WTI", "COMMODITY", "USD/thùng", 80.5, 1.1],
  ["GOLD", "GC=F", "Giá vàng thế giới", "COMMODITY", "USD/oz", 2655.4, 15],
  ["COPPER", "HG=F", "Giá đồng thế giới (Copper)", "COMMODITY", "USD/Lbs", 4.42, 0.05],
  // EQUITY (4)
  ["SP500", "^GSPC", "Chỉ số S&P 500", "EQUITY", "Điểm", 5815.2, 32],
  ["NASDAQ100", "^NDX", "Chỉ số Nasdaq 100", "EQUITY", "Điểm", 20240.1, 130],
  ["DOW_JONES", "^DJI", "Chỉ số Dow Jones", "EQUITY", "Điểm", 42860.0, 160],
  ["NIKKEI225", "^N225", "Chỉ số Nikkei 225", "EQUITY", "Điểm", 39605.0, 220],
  // SENTIMENT (1)
  ["VIX", "^VIX", "Chỉ số biến động & sợ hãi VIX", "SENTIMENT", "Điểm", 15.4, 0.9],
];

function rng(seed: number) {
  let s = seed;
  return () => ((s = (s * 16807) % 2147483647) / 2147483647) - 0.5;
}

function series(id: string, base: number, vol: number, n: number): HistoryPoint[] {
  const r = rng([...id].reduce((a, c) => a + c.charCodeAt(0), 7));
  const out: HistoryPoint[] = [];
  let v = base * 0.92;
  const today = new Date();
  for (let i = n - 1; i >= 0; i--) {
    v += r() * vol + (base - v) * 0.03;
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    out.push({ date: d.toISOString().slice(0, 10), value: +v.toFixed(4) });
  }
  return out.map((p, i, a) => {
    const w = a.slice(Math.max(0, i - 19), i + 1);
    return { ...p, ma_20: +(w.reduce((s, x) => s + x.value, 0) / w.length).toFixed(4) };
  });
}

const DAYS: Record<RangeKey, number> = { "1W": 7, "1M": 30, "3M": 90, "1Y": 365, ALL: 730 };
const pct = (a: number, b: number) => (a / b - 1) * 100;

export function mockIndicators(): Indicator[] {
  return DEFS.map(([id, symbol, name_vi, category, unit, base, vol]) => {
    const s = series(id, base, vol, 400);
    const last = s[s.length - 1];
    const c1d = pct(last.value, s[s.length - 2].value);
    return {
      id,
      symbol,
      name_vi,
      name_en: id,
      category,
      unit,
      latest_value: last.value,
      change_1d: c1d,
      change_1w: pct(last.value, s[s.length - 8].value),
      trend_state: c1d > 0.05 ? "BULLISH" : c1d < -0.05 ? "BEARISH" : "NEUTRAL",
      record_date: last.date,
      sparkline: s.slice(-30).map((p) => p.value),
    };
  });
}

export function mockHistory(id: string, range: RangeKey): HistoryPoint[] {
  const d = DEFS.find((x) => x[0] === id);
  if (!d) return [];
  return series(id, d[5], d[6], 730).slice(-DAYS[range]);
}

const RISKS = ["LOW", "MEDIUM", "HIGH"] as const;

function reportFor(offset: number): DailyReport {
  const d = new Date();
  d.setDate(d.getDate() - offset);
  const date = d.toISOString().slice(0, 10);
  const vnDate = date.split("-").reverse().join("/");
  return {
    id: `REPORT-${date.replace(/-/g, "")}`,
    report_date: date,
    title: `Báo cáo Nhịp đập Kinh tế Thế giới — ${vnDate}`,
    summary:
      "Thị trường chứng khoán Mỹ duy trì sắc xanh nhờ nhóm công nghệ, lợi suất TPCP Mỹ 10Y ở mức 4,15%, đường cong lợi suất 10Y-2Y duy trì mức dương +17 bps và chỉ số VIX ở vùng an toàn 15,40 điểm.",
    risk_level: RISKS[offset % 3],
    status: "PUBLISHED",
    published_at: `${date}T07:00:00`,
    snapshot: [
      { symbol: "SP500", value: 5815.2, change_1d: 0.61 },
      { symbol: "NASDAQ100", value: 20240.1, change_1d: 0.85 },
      { symbol: "DXY", value: 102.85, change_1d: 0.22 },
      { symbol: "US_10Y_YIELD", value: 4.15, change_1d: 0.78 },
      { symbol: "BRENT_OIL", value: 84.2, change_1d: -0.45 },
      { symbol: "GOLD", value: 2655.4, change_1d: 0.35 },
      { symbol: "VIX", value: 15.4, change_1d: -3.2 },
    ],
    content_markdown: `# BÁO CÁO NHỊP ĐẬP KINH TẾ THẾ GIỚI — ${vnDate}
*Hệ thống GMIP phát hành tự động lúc 07:00 AM (Giờ Việt Nam - GMT+7)*

---

### I. TỔNG QUAN THỊ TRƯỜNG (EXECUTIVE SUMMARY)
Khép lại phiên giao dịch gần nhất, thị trường tài chính thế giới chứng kiến diễn biến phân hóa rõ nét khi tâm lý nhà đầu tư thận trọng theo dõi tín hiệu chính sách tiền tệ. Đồng Đô la Mỹ (**DXY**) duy trì đà phục hồi nhẹ quanh 102,85 điểm, trong khi lợi suất trái phiếu chính phủ Mỹ kỳ hạn 10 năm nhích tăng lên mức **4,15%**. Thị trường chứng khoán Mỹ ghi nhận sắc xanh chiếm ưu thế nhờ nhóm cổ phiếu công nghệ và bán dẫn, trong khi giá dầu Brent neo quanh mốc **84,20 USD/thùng**.

#### Bảng Tóm Tắt Nhanh Các Chỉ Số Trọng Yếu:
| Chỉ số | Mã | Mức đóng cửa | Thay đổi 1D | Thay đổi 1W | Trạng thái xu hướng |
|---|---|---:|---:|---:|---|
| **S&P 500** | \`^GSPC\` | 5.815,20 | +0,61% | +1,25% | 🟢 Tăng nhẹ |
| **Nasdaq 100** | \`^NDX\` | 20.240,10 | +0,85% | +1,80% | 🟢 Tăng nhẹ |
| **USD Index (DXY)**| \`DX-Y.NYB\` | 102,85 | +0,22% | +0,55% | 🟢 Tăng nhẹ |
| **Lợi suất Mỹ 10Y** | \`^TNX\` | 4,15% | +3,2 bps | +8,5 bps | ⚪ Ổn định |
| **Dầu Brent** | \`BZ=F\` | 84,20 USD/thùng | -0,45% | +2,10% | ⚪ Đi ngang |
| **Giá Vàng thế giới**| \`GC=F\` | 2.655,40 USD/oz | +0,35% | +0,90% | ⚪ Ổn định |
| **Biến động VIX** | \`^VIX\` | 15,40 | -3,20% | -6,50% | 🟢 Vùng an toàn |

---

### II. VĨ MÔ TOÀN CẦU & CHÍNH SÁCH TIỀN TỆ
1. **Lợi suất Trái phiếu & Fed:** Lợi suất TPCP Mỹ kỳ hạn 10 năm (\`US_10Y_YIELD\`) đóng cửa ở **4,15%** (+3,2 bps), kỳ hạn 2 năm (\`US_02Y_YIELD\`) ở mức **3,98%** (+2,1 bps). Chênh lệch kỳ hạn 10Y - 2Y (\`US_10Y_02Y_SPREAD\`) duy trì mức dương **+17 bps**, đánh dấu sự dốc lên dần của đường cong lợi suất sau thời gian dài đảo ngược, phản ánh kỳ vọng của thị trường về kịch bản hạ cánh mềm (*Soft Landing*). Lãi suất điều hành Fed (\`FED_FUNDS_RATE\`) hiện ở mức **4,83%**, trong khi lãi suất tiền gửi ECB (\`ECB_DEPOSIT_RATE\`) giữ ở mức **3,50%**.
2. **Lạm phát, Tăng trưởng & Việc làm:** Báo cáo CPI Mỹ (\`US_CPI_YOY\`) ghi nhận mức tăng **2,4%** so với cùng kỳ, lạm phát lõi (\`US_CORE_CPI_YOY\`) ở mức **3,2%**, tiếp tục xu hướng hạ nhiệt về gần mục tiêu 2,0% của Cục Dự trữ Liên bang Mỹ (Fed). Tăng trưởng GDP thực Mỹ (\`US_GDP_QOQ\`) đạt **2,8%**, tỷ lệ thất nghiệp (\`US_UNEMP_RATE\`) duy trì ở mức **4,1%** và bảng lương phi nông nghiệp (\`US_NONFARM_PAYROLL\`) đạt **254 nghìn việc làm**, cho thấy thị trường lao động Mỹ vẫn vững vàng. Chỉ số sản xuất ISM PMI (\`US_MANUF_PMI\`) đạt **47,2 điểm**.

---

### III. DIỄN BIẾN THỊ TRƯỜNG TÀI SẢN
- **Thị trường Chứng khoán:** Chỉ số **S&P 500** tăng 0,61% lên 5.815,20 điểm; **Nasdaq 100** tăng 0,85% lên 20.240,10 điểm và **Dow Jones** đạt 42.860,00 điểm. Tại châu Á, chỉ số **Nikkei 225** giao dịch tích cực quanh mốc 39.605,00 điểm. Tâm lý thị trường ổn định với chỉ số biến động **VIX** giảm về **15,40 điểm**.
- **Thị trường Ngoại hối & Tiền tệ:** Chỉ số **DXY** tăng 0,22% lên 102,85 điểm trong bối cảnh đồng Euro suy yếu nhẹ (**EUR/USD** ở mức 1,0925). Tỷ giá **USD/JPY** giữ quanh mức 149,20 JPY/USD. Tỷ giá **USD/VND** giao dịch quanh mốc 24.850 VND/USD, dao động ổn định trong biên độ điều hành.
- **Thị trường Hàng hóa:** Giá dầu thô **Brent** chững lại ở mức 84,20 USD/thùng (-0,45%), dầu **WTI** ở mức 80,50 USD/thùng. **Vàng thế giới (Gold)** giữ vững ngưỡng hỗ trợ quan trọng 2.655,40 USD/oz (+0,35%) nhờ nhu cầu phòng vệ danh mục. Giá **Đồng (Copper)** duy trì quanh 4,42 USD/Lbs.

---

### IV. ĐIỂM CẦN CHÚ Ý & SỰ KIỆN TRONG NGÀY
- **21:00 (Giờ VN):** Công bố chỉ số niềm tin người tiêu dùng Mỹ và khảo sát hoạt động sản xuất khu vực.
- **Phát biểu của quan chức NHTW:** Theo dõi phát biểu của các thành viên FOMC và ECB về lộ trình điều chỉnh lãi suất trong quý tới.
- **Thị trường năng lượng & hàng hóa:** Báo cáo tồn kho dầu thô thương mại Mỹ từ EIA và diễn biến chuỗi cung ứng toàn cầu.

---

### V. LA BÀN RỦI RO & NHẬN ĐỊNH TỔNG QUAN
- **Mức độ rủi ro hệ thống:** **THẤP - TRUNG BÌNH (Low-Medium Risk)**.
- **Kiểm tra các ngưỡng cảnh báo định lượng:**
  * *Đường cong lợi suất 10Y-2Y:* Dương (+17 bps) — Không có tín hiệu cảnh báo đảo ngược đường cong lợi suất.
  * *Chỉ số sợ hãi VIX:* 15,40 điểm — Thấp hơn nhiều so với ngưỡng cảnh báo 30,0 điểm, khẩu vị rủi ro của nhà đầu tư duy trì tích cực.
  * *Cú sốc giá năng lượng:* Biến động dầu Brent (-0,45%) nằm trong biên độ ổn định (< 4,0%/ngày).
- **Liên hệ bối cảnh Việt Nam:** Tỷ giá USD/VND và mặt bằng lãi suất liên ngân hàng duy trì ổn định; dòng vốn đầu tư toàn cầu có xu hướng tích cực hỗ trợ tâm lý thị trường mới nổi và cận biên.
`,
  };
}

export function mockReport(date?: string): DailyReport | null {
  if (!date) return reportFor(0);
  for (let i = 0; i < 30; i++) {
    const r = reportFor(i);
    if (r.report_date === date) return r;
  }
  return null;
}

export function mockReportList(): ReportSummary[] {
  return Array.from({ length: 30 }, (_, i) => {
    const { content_markdown: _c, snapshot: _s, ...s } = reportFor(i);
    void _c;
    void _s;
    return s;
  });
}
