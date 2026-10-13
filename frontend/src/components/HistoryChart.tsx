"use client";
import { Area, ComposedChart as AreaChart, Line, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HistoryPoint } from "@/types";
import { formatDate, formatNumber } from "@/lib/format";

export default function HistoryChart({ data, unit, color }: { data: HistoryPoint[]; unit: string; color: string }) {
  return (
    <div style={{ width: "100%", height: 340 }}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(d: string) => formatDate(d).slice(0, 5)} minTickGap={32} stroke="var(--muted)" fontSize={12} />
          <YAxis domain={["auto", "auto"]} width={64} tickFormatter={(v: number) => formatNumber(v, v >= 1000 ? 0 : 2)} stroke="var(--muted)" fontSize={12} />
          <Tooltip
            labelFormatter={(d) => formatDate(String(d))}
            formatter={(v, name) => [`${formatNumber(Number(v), 2)} ${unit}`, name === "ma_20" ? "MA20" : "Giá trị"]}
            contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8 }}
          />
          <Line type="monotone" dataKey="ma_20" name="MA20" stroke="var(--muted)" strokeDasharray="4 3" dot={false} isAnimationActive={false} />
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2} fill="url(#fill)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
