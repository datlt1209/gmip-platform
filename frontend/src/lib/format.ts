import type { Category, RiskLevel } from "@/types";

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
