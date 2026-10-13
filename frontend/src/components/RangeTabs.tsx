import type { RangeKey } from "@/types";
import { RANGE_LABEL } from "@/lib/format";

export const CHART_RANGES: RangeKey[] = ["1W", "1M", "1Q", "1Y", "2Y", "3Y", "ALL"];

export default function RangeTabs({ value, onChange }: { value: RangeKey; onChange: (r: RangeKey) => void }) {
  return (
    <div className="tabs" role="tablist" aria-label="Khung thời gian">
      {CHART_RANGES.map((r) => (
        <button
          key={r}
          role="tab"
          aria-selected={r === value}
          className={r === value ? "tab active" : "tab"}
          onClick={() => onChange(r)}
        >
          {RANGE_LABEL[r]} ({r})
        </button>
      ))}
    </div>
  );
}
