import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface PnlPoint {
  time: string;
  cumulative_pnl_pct: number;
}

export function CumulativePnlChart({ points }: { points: PnlPoint[] }) {
  const last = points.at(-1)?.cumulative_pnl_pct ?? 0;

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
        <Line type="monotone" dataKey="cumulative_pnl_pct" stroke={last >= 0 ? "#2fbf71" : "#e5484d"} strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
