import Link from "next/link";
import type { Indicator } from "@/types";
import { formatNumber, formatPercent, trendOf } from "@/lib/format";
import Sparkline from "./Sparkline";

const ARROW = { up: "▲", down: "▼", flat: "■" } as const;

export default function MetricCard({ indicator }: { indicator: Indicator }) {
  const v = indicator.latest_value;
  const trend = trendOf(indicator.change_1d);
  return (
    <Link href={`/indicators/${indicator.id}`} className={`card metric ${trend}`}>
      <div className="metric-head">
        <span className="metric-name">{indicator.name_vi}</span>
        <span className="metric-symbol">{indicator.symbol}</span>
      </div>
      <div className="metric-body">
        <div>
          <div className="metric-value">
            {v != null ? formatNumber(v, v >= 1000 ? 0 : 2) : "—"} <small>{indicator.unit}</small>
          </div>
          <div className={`metric-change ${trend}`}>{ARROW[trend]} {formatPercent(indicator.change_1d)}</div>
        </div>
        <Sparkline data={indicator.sparkline ?? []} trend={trend} />
      </div>
    </Link>
  );
}
