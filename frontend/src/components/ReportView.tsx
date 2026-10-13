"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { DailyReport } from "@/types";
import { formatDate, formatNumber, formatPercent, trendOf } from "@/lib/format";
import RiskBadge from "./RiskBadge";

export function downloadMarkdown(r: DailyReport) {
  const blob = new Blob([r.content_markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `gmip-report-${r.report_date}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ReportView({ report }: { report: DailyReport }) {
  return (
    <article className="card report">
      <div className="report-head">
        <div>
          <p className="muted">Ngày {formatDate(report.report_date)}</p>
          <h1>{report.title}</h1>
        </div>
        <RiskBadge level={report.risk_level} />
      </div>
      {report.summary && <p className="summary"><strong>Tóm tắt:</strong> {report.summary}</p>}
      <div className="actions no-print">
        <button className="btn" onClick={() => downloadMarkdown(report)}>⬇ Tải Markdown</button>
        <button className="btn" onClick={() => window.print()}>🖨 In / Lưu PDF</button>
      </div>
      {report.snapshot && report.snapshot.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Chỉ số</th><th>Giá trị</th><th>Δ 1D</th></tr></thead>
            <tbody>
              {report.snapshot.map((s) => (
                <tr key={s.symbol}><td>{s.symbol}</td><td>{formatNumber(s.value)}</td><td className={trendOf(s.change_1d)}>{formatPercent(s.change_1d)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="prose"><ReactMarkdown remarkPlugins={[remarkGfm]}>{report.content_markdown}</ReactMarkdown></div>
    </article>
  );
}
