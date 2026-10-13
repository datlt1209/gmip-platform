"use client";
import Link from "next/link";
import { use, useState } from "react";
import type { RangeKey } from "@/types";
import { useAsync } from "@/lib/useAsync";
import { getHistory, getIndicator } from "@/services/api";
import { formatDate, formatNumber, formatPercent, trendOf } from "@/lib/format";
import HistoryChart from "@/components/HistoryChart";
import RangeTabs from "@/components/RangeTabs";
import { Empty, ErrorState, Loading } from "@/components/States";

const COLORS = { up: "#16a34a", down: "#dc2626", flat: "#6b7280" };

export default function IndicatorDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [range, setRange] = useState<RangeKey>("1M");
  const ind = useAsync(() => getIndicator(id), [id]);
  const hist = useAsync(() => getHistory(id, range), [id, range]);
  const d = ind.data;
  const trend = trendOf(d?.change_1d);

  return (
    <main className="container">
      <Link href="/" className="muted">← Quay lại Dashboard</Link>
      {ind.error && <ErrorState message={ind.error} onRetry={ind.reload} />}
      {ind.loading && <Loading />}
      {ind.data && (
        <>
          <h1>{ind.data.name_vi} <small className="muted">({ind.data.symbol})</small></h1>
          <div className="stats">
            <div className="card stat"><span className="muted">Giá trị mới nhất</span><strong>{formatNumber(d?.latest_value)} {ind.data.unit}</strong></div>
            {([["1 ngày", d?.change_1d], ["1 tuần", d?.change_1w]] as const).map(([l, c]) => (
              <div key={l} className="card stat"><span className="muted">{l}</span><strong className={trendOf(c)}>{formatPercent(c)}</strong></div>
            ))}
          </div>
          <section className="card">
            <div className="chart-head"><h2>Biểu đồ</h2><RangeTabs value={range} onChange={setRange} /></div>
            {hist.loading && <Loading />}
            {hist.error && <ErrorState message={hist.error} onRetry={hist.reload} />}
            {hist.data && hist.data.length === 0 && <Empty message="Chưa có dữ liệu lịch sử." />}
            {hist.data && hist.data.length > 0 && <HistoryChart data={hist.data} unit={ind.data.unit} color={COLORS[trend]} />}
          </section>
          {hist.data && hist.data.length > 0 && (
            <section className="card">
              <h2>Lịch sử giá trị</h2>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Ngày</th><th>Giá trị</th><th>Δ so với phiên trước</th><th>MA20</th></tr></thead>
                  <tbody>
                    {hist.data.map((r, i, a) => ({ r, chg: i > 0 ? (r.value / a[i - 1].value - 1) * 100 : null })).reverse().slice(0, 100).map(({ r, chg }) => (
                      <tr key={r.date}>
                        <td>{formatDate(r.date)}</td>
                        <td>{formatNumber(r.value)}</td>
                        <td className={trendOf(chg)}>{formatPercent(chg)}</td>
                        <td>{formatNumber(r.ma_20)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </main>
  );
}
