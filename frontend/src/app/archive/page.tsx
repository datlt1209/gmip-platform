"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useAsync } from "@/lib/useAsync";
import { getReportByDate, listReports } from "@/services/api";
import { formatDate } from "@/lib/format";
import { downloadMarkdown } from "@/components/ReportView";
import RiskBadge from "@/components/RiskBadge";
import { Empty, ErrorState, Loading } from "@/components/States";

export default function ArchivePage() {
  const router = useRouter();
  const { data, loading, error, reload } = useAsync(() => listReports(), []);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [dlError, setDlError] = useState<string | null>(null);

  const rows = useMemo(
    () => (data ?? []).filter((r) => (!from || r.report_date >= from) && (!to || r.report_date <= to)),
    [data, from, to],
  );

  async function download(date: string) {
    setBusy(date); setDlError(null);
    try { downloadMarkdown(await getReportByDate(date)); }
    catch (e) { setDlError(e instanceof Error ? e.message : "Không tải được báo cáo"); }
    finally { setBusy(null); }
  }

  return (
    <main className="container">
      <h1>Kho lưu trữ báo cáo</h1>
      <div className="card filters no-print">
        <label>Chọn ngày <input type="date" onChange={(e) => e.target.value && router.push(`/report/${e.target.value}`)} /></label>
        <label>Từ ngày <input type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} /></label>
        <label>Đến ngày <input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} /></label>
        {(from || to) && <button className="btn" onClick={() => { setFrom(""); setTo(""); }}>Xóa lọc</button>}
      </div>
      {dlError && <ErrorState message={dlError} />}
      {loading && <Loading rows={4} />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {data && rows.length === 0 && <Empty message="Không có báo cáo nào trong khoảng thời gian đã chọn." />}
      <ul className="list">
        {rows.map((r) => (
          <li key={r.id} className="card item">
            <div>
              <Link href={`/report/${r.report_date}`}><strong>{formatDate(r.report_date)}</strong> — {r.title}</Link>
              {r.summary && <p className="muted">{r.summary}</p>}
            </div>
            <div className="item-side">
              <RiskBadge level={r.risk_level} />
              <button className="btn" disabled={busy === r.report_date} onClick={() => download(r.report_date)}>⬇ .md</button>
              <Link className="btn" href={`/report/${r.report_date}`} onClick={() => sessionStorage.setItem("gmip-print", "1")}>🖨 In</Link>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
