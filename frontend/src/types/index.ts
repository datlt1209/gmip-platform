export type Category = "MACRO" | "RATES" | "FX" | "COMMODITY" | "EQUITY" | "SENTIMENT";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type RangeKey = "1W" | "1M" | "3M" | "1Y" | "ALL";

export interface ApiResponse<T> {
  status: string;
  data: T | null;
  message?: string | null;
}

/** Điểm lịch sử: GET /indicators/{id}/history -> data[] */
export interface HistoryPoint {
  date: string;
  value: number;
  ma_20?: number | null;
  ma_50?: number | null;
}

/** Theo SRS 9.1 #1 (phẳng). */
export interface Indicator {
  id: string;
  symbol: string;
  name_vi: string;
  name_en?: string;
  category: Category;
  unit: string;
  latest_value: number | null;
  change_1d?: number | null;
  change_1w?: number | null;
  change_1m?: number | null;
  change_yoy?: number | null;
  trend_state?: string | null;
  record_date?: string | null;
  sparkline?: number[];
}

export interface SnapshotItem {
  symbol: string;
  value: number;
  change_1d?: number | null;
}

export interface ReportSummary {
  id: string;
  report_date: string;
  title: string;
  summary?: string | null;
  risk_level: RiskLevel;
  status: string;
  published_at?: string | null;
}

export interface DailyReport extends ReportSummary {
  content_markdown: string;
  snapshot?: SnapshotItem[];
}
