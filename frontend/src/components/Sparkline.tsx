import type { Trend } from "@/lib/format";

const COLOR: Record<Trend, string> = { up: "var(--up)", down: "var(--down)", flat: "var(--flat)" };

export default function Sparkline({ data, trend, width = 110, height = 36 }: { data: number[]; trend: Trend; width?: number; height?: number }) {
  if (data.length < 2) return <div style={{ width, height }} aria-hidden />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const pts = data
    .map((v, i) => `${((i / (data.length - 1)) * width).toFixed(1)},${(height - 3 - ((v - min) / span) * (height - 6)).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Biểu đồ xu hướng thu nhỏ">
      <polyline points={pts} fill="none" stroke={COLOR[trend]} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
