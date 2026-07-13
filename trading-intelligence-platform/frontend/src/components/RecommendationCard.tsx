import type { RecommendationSummary } from "../api/types";

interface Props {
  recommendation: RecommendationSummary;
  onSelect: (id: string) => void;
}

export function RecommendationCard({ recommendation: rec, onSelect }: Props) {
  const isBullish = rec.action === "BUY_CE";
  return (
    <div className="card rec-card" onClick={() => onSelect(rec.id)}>
      <div className="rec-card-main">
        <div className="symbol">
          {rec.symbol.replace("NSE:", "")}{" "}
          <span className={isBullish ? "bullish" : "bearish"}>{rec.action}</span>
        </div>
        <div className="meta">
          {rec.category} &middot; {rec.forecast_horizon ?? "—"} &middot; VIX {rec.vix_regime_at_creation}
        </div>
      </div>
      <div className="scores">
        <div className="score-block">
          <div className="label">Confidence</div>
          <div className="value">{rec.confidence_score.toFixed(0)}</div>
        </div>
        <div className="score-block">
          <div className="label">Risk</div>
          <div className="value">{rec.risk_score.toFixed(0)}</div>
        </div>
        <div className="score-block">
          <div className="label">Conv</div>
          <div className="value">{rec.conviction_score.toFixed(0)}</div>
        </div>
      </div>
    </div>
  );
}
