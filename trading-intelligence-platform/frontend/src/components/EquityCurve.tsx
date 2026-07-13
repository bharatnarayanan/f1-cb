import type { PaperTrade } from "../api/types";
import { CumulativePnlChart } from "./CumulativePnlChart";

export function EquityCurve({ trades }: { trades: PaperTrade[] }) {
  const closed = trades
    .filter((t) => t.status === "closed" && t.closed_at && t.simulated_pnl_pct !== null)
    .sort((a, b) => new Date(a.closed_at!).getTime() - new Date(b.closed_at!).getTime());

  if (closed.length === 0) {
    return <div className="empty-state">No closed paper trades yet — cumulative P&amp;L appears here once one closes.</div>;
  }

  let cumulative = 0;
  const points = closed.map((t) => {
    cumulative += t.simulated_pnl_pct!;
    return {
      time: new Date(t.closed_at!).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }),
      cumulative_pnl_pct: Number(cumulative.toFixed(2)),
    };
  });

  return <CumulativePnlChart points={points} />;
}
