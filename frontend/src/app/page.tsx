"use client";
import { useState } from "react";
import type { Category, RangeKey } from "@/types";
import { useAsync } from "@/lib/useAsync";
import { getIndicators } from "@/services/api";
import { CATEGORY_LABEL, CATEGORY_ORDER, RANGE_DESC, RANGE_LABEL } from "@/lib/format";
import MetricCard from "@/components/MetricCard";
import { Empty, ErrorState, Loading } from "@/components/States";

const DASHBOARD_RANGES: RangeKey[] = ["1D", "1W", "1M", "1Q", "1Y", "2Y", "3Y", "ALL"];

export default function DashboardPage() {
  const [range, setRange] = useState<RangeKey>("1D");
  const [selectedCat, setSelectedCat] = useState<Category | "ALL">("ALL");
  const { data, loading, error, reload } = useAsync(() => getIndicators(undefined, range), [range]);

  const categoriesToRender = selectedCat === "ALL" ? CATEGORY_ORDER : [selectedCat];

  return (
    <main className="container">
      <div className="dash-head">
        <div>
          <h1>Bảng điều khiển vĩ mô</h1>
          <p className="muted legend">
            <span className="up">▲ Tăng</span> · <span className="down">▼ Giảm</span> · <span className="flat">■ Đi ngang</span> —{" "}
            <strong>Biến động theo kỳ hạn: {RANGE_DESC[range]}</strong>
          </p>
        </div>
      </div>

      <div className="card filter-bar">
        <div className="filter-group">
          <span className="filter-label">Kỳ hạn biến động:</span>
          <div className="tabs" role="tablist" aria-label="Bộ lọc kỳ hạn thời gian">
            {DASHBOARD_RANGES.map((r) => (
              <button
                key={r}
                type="button"
                role="tab"
                aria-selected={range === r}
                className={range === r ? "tab active" : "tab"}
                onClick={() => setRange(r)}
              >
                {RANGE_LABEL[r]}
              </button>
            ))}
          </div>
        </div>

        <div className="filter-group">
          <span className="filter-label">Nhóm chỉ số:</span>
          <div className="tabs" role="tablist" aria-label="Bộ lọc nhóm chỉ số">
            <button
              type="button"
              role="tab"
              aria-selected={selectedCat === "ALL"}
              className={selectedCat === "ALL" ? "tab active" : "tab"}
              onClick={() => setSelectedCat("ALL")}
            >
              Tất cả nhóm (24)
            </button>
            {CATEGORY_ORDER.map((cat) => (
              <button
                key={cat}
                type="button"
                role="tab"
                aria-selected={selectedCat === cat}
                className={selectedCat === cat ? "tab active" : "tab"}
                onClick={() => setSelectedCat(cat)}
              >
                {CATEGORY_LABEL[cat]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && <Loading rows={8} />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {data && data.length === 0 && <Empty message="Chưa có dữ liệu chỉ số." />}
      {data &&
        categoriesToRender.map((cat) => {
          const items = data.filter((i) => i.category === cat);
          if (!items.length) return null;
          return (
            <section key={cat}>
              <h2>{CATEGORY_LABEL[cat]} ({items.length})</h2>
              <div className="grid">
                {items.map((i) => (
                  <MetricCard key={i.id} indicator={i} range={range} />
                ))}
              </div>
            </section>
          );
        })}
    </main>
  );
}
