"use client";
import { useAsync } from "@/lib/useAsync";
import { getIndicators } from "@/services/api";
import { CATEGORY_LABEL, CATEGORY_ORDER } from "@/lib/format";
import MetricCard from "@/components/MetricCard";
import { Empty, ErrorState, Loading } from "@/components/States";

export default function DashboardPage() {
  const { data, loading, error, reload } = useAsync(() => getIndicators(), []);
  return (
    <main className="container">
      <h1>Bảng điều khiển vĩ mô</h1>
      <p className="muted legend">
        <span className="up">▲ Tăng</span> · <span className="down">▼ Giảm</span> · <span className="flat">■ Đi ngang</span> (biến động 1 ngày)
      </p>
      {loading && <Loading rows={8} />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {data && data.length === 0 && <Empty message="Chưa có dữ liệu chỉ số." />}
      {data &&
        CATEGORY_ORDER.map((cat) => {
          const items = data.filter((i) => i.category === cat);
          if (!items.length) return null;
          return (
            <section key={cat}>
              <h2>{CATEGORY_LABEL[cat]}</h2>
              <div className="grid">{items.map((i) => <MetricCard key={i.id} indicator={i} />)}</div>
            </section>
          );
        })}
    </main>
  );
}
