import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PaperTrade } from "../api/types";

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

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="#232838" strokeDasharray="3 3" />
        <XAxis dataKey="time" stroke="#8b93a7" fontSize={11} tickLine={false} />
        <YAxis stroke="#8b93a7" fontSize={11} tickLine={false} unit="%" />
        <Tooltip
          contentStyle={{ background: "#12161f", border: "1px solid #232838", fontSize: 12 }}
          labelStyle={{ color: "#e6e9ef" }}
        />
        <Line
          type="monotone"
          dataKey="cumulative_pnl_pct"
          stroke={cumulative >= 0 ? "#2fbf71" : "#e5484d"}
          strokeWidth={2}
          dot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
