import type { RiskLevel } from "@/types";
import { RISK_LABEL } from "@/lib/format";

export default function RiskBadge({ level }: { level: RiskLevel }) {
  return <span className={`badge risk-${level.toLowerCase()}`}>● {RISK_LABEL[level] ?? level}</span>;
}
