import type { RangeKey } from "@/types";

const RANGES: RangeKey[] = ["1W", "1M", "1Y", "ALL"];

export default function RangeTabs({ value, onChange }: { value: RangeKey; onChange: (r: RangeKey) => void }) {
  return (
    <div className="tabs" role="tablist" aria-label="Khung thời gian">
      {RANGES.map((r) => (
        <button key={r} role="tab" aria-selected={r === value} className={r === value ? "tab active" : "tab"} onClick={() => onChange(r)}>
          {r === "ALL" ? "Tất cả" : r}
        </button>
      ))}
    </div>
  );
}
