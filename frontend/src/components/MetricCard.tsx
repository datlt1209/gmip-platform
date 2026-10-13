import Link from "next/link";
import type { Indicator, RangeKey } from "@/types";
import { formatNumber, formatPercent, RANGE_LABEL, trendOf } from "@/lib/format";
import Sparkline from "./Sparkline";

const ARROW = { up: "▲", down: "▼", flat: "■" } as const;

export default function MetricCard({ indicator, range = "1D" }: { indicator: Indicator; range?: RangeKey }) {
  const v = indicator.latest_value;
  const changeVal = indicator.period_change ?? indicator.change_1d;
  const trend = trendOf(changeVal);
  const targetRange = range && range !== "1D" ? range : "1M";
  const rangeLabel = RANGE_LABEL[range] ?? range;

  return (
    <Link href={`/indicators/${indicator.id}?range=${targetRange}`} className={`card metric ${trend}`}>
      <div className="metric-head">
        <span className="metric-name">{indicator.name_vi}</span>
        <span className="metric-symbol">{indicator.symbol}</span>
      </div>
      <div className="metric-body">
        <div>
          <div className="metric-value">
            {v != null ? formatNumber(v, v >= 1000 ? 0 : 2) : "—"} <small>{indicator.unit}</small>
          </div>
          <div className={`metric-change ${trend}`}>
            {ARROW[trend]} {formatPercent(changeVal)} <small className="muted">({rangeLabel})</small>
          </div>
        </div>
        <Sparkline data={indicator.sparkline ?? []} trend={trend} />
      </div>
    </Link>
  );
}
