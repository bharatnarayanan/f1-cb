import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { closePaperTrade, listPaperTrades } from "../api/client";
import { EquityCurve } from "../components/EquityCurve";

export function PaperTrading() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["paper-trades"],
    queryFn: () => listPaperTrades(),
    refetchInterval: 30_000,
  });

  const close = useMutation({
    mutationFn: (id: string) => closePaperTrade(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["paper-trades"] }),
  });

  const trades = data?.paper_trades ?? [];
  const open = trades.filter((t) => t.status === "open");
  const closed = trades.filter((t) => t.status === "closed");

  if (isLoading) return <div className="empty-state">Loading…</div>;
  if (error) return <div className="empty-state bearish">{(error as Error).message}</div>;

  return (
    <div>
      <h2 style={{ fontSize: 15, marginBottom: 8 }}>Open positions</h2>
      {open.length === 0 && <div className="empty-state">No open paper trades — open one from a recommendation's deep-dive.</div>}
      {open.map((t) => (
        <div className="card trade-row" key={t.id}>
          <span className="mono">{t.id.slice(0, 8)}</span>
          <span className="mono">Entry {t.simulated_entry_price}</span>
          <button className="btn secondary" disabled={close.isPending} onClick={() => close.mutate(t.id)}>
            Close
          </button>
        </div>
      ))}

      <h2 style={{ fontSize: 15, margin: "24px 0 8px" }}>Simulated equity curve</h2>
      <div className="card">
        <EquityCurve trades={trades} />
      </div>

      <h2 style={{ fontSize: 15, margin: "24px 0 8px" }}>Closed trades</h2>
      {closed.length === 0 && <div className="empty-state">None yet.</div>}
      {closed.map((t) => (
        <div className="card trade-row" key={t.id}>
          <span className="mono">{t.id.slice(0, 8)}</span>
          <span className="mono">
            {t.simulated_entry_price} &rarr; {t.simulated_exit_price}
          </span>
          <span className={`mono ${(t.simulated_pnl_pct ?? 0) >= 0 ? "bullish" : "bearish"}`}>
            {t.simulated_pnl_pct !== null ? `${t.simulated_pnl_pct > 0 ? "+" : ""}${t.simulated_pnl_pct}%` : "—"}
          </span>
        </div>
      ))}

      <p className="safety-footer">
        Simulated fills only — no real order was ever placed, no real money is involved. See docs/CLAUDE.md section 2.
      </p>
    </div>
  );
}
