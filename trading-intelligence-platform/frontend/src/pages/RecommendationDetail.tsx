import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getRecommendation, openPaperTrade } from "../api/client";
import { ReasoningTree } from "../components/ReasoningTree";

interface Props {
  id: string;
  onBack: () => void;
  onLogOutcome: (recommendationId: string) => void;
}

export function RecommendationDetail({ id, onBack, onLogOutcome }: Props) {
  const queryClient = useQueryClient();
  const { data: rec, isLoading, error } = useQuery({
    queryKey: ["recommendation", id],
    queryFn: () => getRecommendation(id),
  });

  const openTrade = useMutation({
    mutationFn: () => openPaperTrade(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["paper-trades"] }),
  });

  if (isLoading) return <div className="empty-state">Loading…</div>;
  if (error || !rec) return <div className="empty-state bearish">{(error as Error)?.message ?? "Not found."}</div>;

  const isBullish = rec.action === "BUY_CE";

  return (
    <div>
      <button className="back-link" onClick={onBack}>
        &larr; Back to dashboard
      </button>

      <div className="card">
        <div className="rec-card-main" style={{ marginBottom: 12 }}>
          <div className="symbol">
            {rec.symbol.replace("NSE:", "")} — {rec.category} — {rec.forecast_horizon} horizon{" "}
            <span className={isBullish ? "bullish" : "bearish"}>{rec.action}</span>
          </div>
          <div className="meta">Confidence {rec.confidence_score.toFixed(0)} | Risk {rec.risk_score.toFixed(0)} | Conviction {rec.conviction_score.toFixed(0)}</div>
        </div>

        <ReasoningTree rationale={rec.rationale} />

        <div style={{ marginTop: 16, display: "flex", gap: 8, alignItems: "center" }}>
          <button className="btn" disabled={openTrade.isPending || openTrade.isSuccess} onClick={() => openTrade.mutate()}>
            {openTrade.isSuccess ? "Paper trade opened" : "Open paper trade"}
          </button>
          <button className="btn secondary" onClick={() => onLogOutcome(id)}>
            Log outcome
          </button>
          {openTrade.isError && <span className="bearish">{(openTrade.error as Error).message}</span>}
        </div>
      </div>

      <p className="safety-footer">
        Informational only — this system never places, modifies, or cancels a real order. Execute manually in your
        own broker app if you choose to act on this.
      </p>
    </div>
  );
}
