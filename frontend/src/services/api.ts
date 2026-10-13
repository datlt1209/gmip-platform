import type { ApiResponse, DailyReport, HistoryPoint, Indicator, RangeKey, ReportSummary } from "@/types";
import { mockHistory, mockIndicators, mockReport, mockReportList } from "./mock";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");
export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

async function request<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError("Không thể kết nối tới máy chủ. Vui lòng thử lại sau.");
  }
  if (!res.ok) {
    let msg = `Lỗi máy chủ (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") msg = body.detail;
    } catch {}
    throw new ApiError(msg, res.status);
  }
  const body = (await res.json()) as ApiResponse<T>;
  if (body.data == null) throw new ApiError(body.message ?? "Không có dữ liệu", res.status);
  return body.data;
}

const delay = <T,>(v: T) => new Promise<T>((r) => setTimeout(() => r(v), 250));

export async function getIndicators(category?: string): Promise<Indicator[]> {
  const fallback = () => {
    const all = mockIndicators();
    return category ? all.filter((i) => i.category === category) : all;
  };
  if (USE_MOCK) return delay(fallback());
  try {
    const raw = await request<RawIndicator[]>(`/indicators${category ? `?category=${category}` : ""}`);
    return raw.map(normalizeIndicator);
  } catch {
    return fallback();
  }
}

/** Chấp nhận cả contract SRS (phẳng) lẫn dạng lồng latest_value:{value,change_*,record_date}. */
type RawIndicator = Omit<Indicator, "latest_value"> & {
  latest_value: number | null | (Partial<Indicator> & { value: number; record_date?: string });
};
function normalizeIndicator(r: RawIndicator): Indicator {
  const lv = r.latest_value;
  if (lv && typeof lv === "object") {
    const { value, ...rest } = lv;
    return { ...r, ...rest, latest_value: value, record_date: lv.record_date ?? r.record_date };
  }
  return { ...r, latest_value: lv ?? null };
}

export async function getIndicator(id: string): Promise<Indicator> {
  const list = await getIndicators();
  const found = list.find((i) => i.id === id);
  if (!found) throw new ApiError("Không tìm thấy chỉ số", 404);
  return found;
}

const histCache = new Map<string, Promise<HistoryPoint[]>>();

/** Lịch sử giá trị (GET /indicators/{id}/history?range=). Kết quả sắp xếp tăng dần theo ngày. */
export function getHistory(id: string, range: RangeKey): Promise<HistoryPoint[]> {
  const key = `${id}:${range}`;
  let p = histCache.get(key);
  if (!p) {
    const fetchOrMock = USE_MOCK
      ? delay(mockHistory(id, range))
      : request<HistoryPoint[] | { data: HistoryPoint[] }>(`/indicators/${id}/history?range=${range}`).catch(() =>
          mockHistory(id, range),
        );
    p = fetchOrMock.then((res) => {
      const rows = Array.isArray(res) ? res : (res?.data ?? []);
      return [...rows].sort((a, b) => a.date.localeCompare(b.date));
    });
    p.catch(() => histCache.delete(key));
    histCache.set(key, p);
  }
  return p;
}

export async function getLatestReport(): Promise<DailyReport> {
  if (USE_MOCK) return delay(mockReport()!);
  try {
    return await request<DailyReport>("/reports/latest");
  } catch {
    return mockReport()!;
  }
}

/** GET /reports/{YYYY-MM-DD} */
export async function getReportByDate(date: string): Promise<DailyReport> {
  const fallback = () => {
    const r = mockReport(date);
    if (!r) throw new ApiError("Không có báo cáo cho ngày này", 404);
    return r;
  };
  if (USE_MOCK) return delay(fallback());
  try {
    return await request<DailyReport>(`/reports/${date}`);
  } catch {
    return fallback();
  }
}

export async function listReports(limit = 100, fromDate?: string, toDate?: string): Promise<ReportSummary[]> {
  if (USE_MOCK) return delay(mockReportList());
  try {
    const q = new URLSearchParams({ page: "1", limit: String(limit) });
    if (fromDate) q.set("from_date", fromDate);
    if (toDate) q.set("to_date", toDate);
    const d = await request<ReportSummary[] | { items: ReportSummary[] }>(`/reports?${q}`);
    return Array.isArray(d) ? d : d.items;
  } catch {
    return mockReportList();
  }
}
