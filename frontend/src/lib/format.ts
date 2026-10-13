import type { Category, RangeKey, RiskLevel } from "@/types";

export type Trend = "up" | "down" | "flat";

export const CATEGORY_ORDER: Category[] = ["MACRO", "RATES", "FX", "COMMODITY", "EQUITY", "SENTIMENT"];
export const CATEGORY_LABEL: Record<Category, string> = {
  MACRO: "Vĩ mô",
  RATES: "Lãi suất",
  FX: "Ngoại hối",
  COMMODITY: "Hàng hóa",
  EQUITY: "Chứng khoán",
  SENTIMENT: "Tâm lý thị trường",
};

export const RANGE_LABEL: Record<RangeKey, string> = {
  "1D": "1 Ngày",
  "1W": "1 Tuần",
  "1M": "1 Tháng",
  "1Q": "1 Quý",
  "3M": "1 Quý",
  "1Y": "1 Năm",
  "2Y": "2 Năm",
  "3Y": "3 Năm",
  ALL: "Tất cả",
};

export const RANGE_DESC: Record<RangeKey, string> = {
  "1D": "1 Ngày (24h qua)",
  "1W": "1 Tuần (7 ngày)",
  "1M": "1 Tháng (30 ngày)",
  "1Q": "1 Quý (90 ngày)",
  "3M": "1 Quý (90 ngày)",
  "1Y": "1 Năm (365 ngày)",
  "2Y": "2 Năm (730 ngày)",
  "3Y": "3 Năm (1095 ngày)",
  ALL: "Tất cả lịch sử",
};

export const RISK_LABEL: Record<RiskLevel, string> = {
  LOW: "Rủi ro thấp",
  MEDIUM: "Rủi ro trung bình",
  HIGH: "Rủi ro cao",
};

/** Ngưỡng đi ngang: |Δ| < 0.05% */
export function trendOf(change?: number | null): Trend {
  if (change == null || Math.abs(change) < 0.05) return "flat";
  return change > 0 ? "up" : "down";
}

export function formatNumber(v?: number | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("vi-VN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function formatPercent(v?: number | null): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${formatNumber(v, 2)}%`;
}

export function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}
