import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listJournalEntries, logJournalOutcome } from "../api/client";
import type { JournalOutcome } from "../api/types";

const OUTCOMES: JournalOutcome[] = ["win", "loss", "breakeven", "not_taken"];

export function TradeJournal({ prefillRecommendationId }: { prefillRecommendationId?: string }) {
  const [recommendationId, setRecommendationId] = useState(prefillRecommendationId ?? "");
  const [outcome, setOutcome] = useState<JournalOutcome>("win");
  const [pnl, setPnl] = useState("");
  const [observation, setObservation] = useState("");
  const queryClient = useQueryClient();

  const { data } = useQuery({ queryKey: ["journal"], queryFn: listJournalEntries });

  const save = useMutation({
    mutationFn: () =>
      logJournalOutcome({
        recommendation_id: recommendationId || undefined,
        outcome,
        realized_pnl_pct: pnl ? Number(pnl) : undefined,
        observation: observation || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["journal"] });
      setObservation("");
      setPnl("");
    },
  });

  return (
    <div>
      <div className="card">
        <div style={{ fontWeight: 600, marginBottom: 10 }}>Log an outcome</div>
        {prefillRecommendationId && (
          <p className="meta" style={{ marginBottom: 8 }}>
            Logging against recommendation <span className="mono">{prefillRecommendationId.slice(0, 8)}</span>
          </p>
        )}
        {!prefillRecommendationId && (
          <input
            placeholder="Recommendation id (optional)"
            value={recommendationId}
            onChange={(e) => setRecommendationId(e.target.value)}
            style={{ width: "100%", marginBottom: 8, padding: 6, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 }}
          />
        )}
        <div style={{ display: "flex", gap: 12, marginBottom: 8 }}>
          {OUTCOMES.map((o) => (
            <label key={o} style={{ fontSize: 12, color: "var(--text-dim)" }}>
              <input type="radio" checked={outcome === o} onChange={() => setOutcome(o)} /> {o.replace("_", " ")}
            </label>
          ))}
        </div>
        <input
          placeholder="Realized P&L % (optional)"
          value={pnl}
          onChange={(e) => setPnl(e.target.value)}
          style={{ width: 200, marginBottom: 8, padding: 6, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 }}
        />
        <textarea
          placeholder="Observation (optional) — e.g. 'negation happened faster than predicted'"
          value={observation}
          onChange={(e) => setObservation(e.target.value)}
          rows={2}
          style={{ width: "100%", marginBottom: 8, padding: 6, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 }}
        />
        <button className="btn" disabled={save.isPending} onClick={() => save.mutate()}>
          Save entry
        </button>
        {save.isError && <div className="empty-state bearish">{(save.error as Error).message}</div>}
      </div>

      <h2 style={{ fontSize: 15, margin: "20px 0 8px" }}>History</h2>
      {(data?.entries.length ?? 0) === 0 && <div className="empty-state">No entries logged yet.</div>}
      {data?.entries.map((e) => (
        <div className="card trade-row" key={e.id}>
          <span className={e.outcome === "win" ? "bullish" : e.outcome === "loss" ? "bearish" : ""}>{e.outcome}</span>
          <span className="mono">{e.realized_pnl_pct !== null ? `${e.realized_pnl_pct}%` : "—"}</span>
          <span style={{ color: "var(--text-dim)", fontSize: 12 }}>{e.observation ?? ""}</span>
        </div>
      ))}

      <p className="safety-footer">
        This log is the seed data for a future weight-update job (not built yet — needs a scheduled worker service).
        Logging here doesn't change any scoring today.
      </p>
    </div>
  );
}
