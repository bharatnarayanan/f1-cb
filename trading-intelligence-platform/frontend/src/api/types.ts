// Mirrors src/routes/recommendations.py and src/routes/paper_trades.py's
// JSON response shapes. Kept hand-in-sync with the backend, same convention
// as packages/spec in the sibling f1-cb monorepo (no codegen here — this
// project is small enough that hand-sync is the pragmatic choice).

export type RecommendationCategory = "tactical" | "impulse" | "strategic" | "btst";
export type RecommendationAction = "BUY_CE" | "BUY_PE" | "SELL_CE" | "SELL_PE" | "NO_TRADE";
export type VixRegime = "normal" | "elevated" | "high" | "extreme";

export interface RecommendationSummary {
  id: string;
  symbol: string;
  category: RecommendationCategory;
  action: RecommendationAction;
  forecast_horizon: string | null;
  confidence_score: number;
  risk_score: number;
  conviction_score: number;
  vix_regime_at_creation: VixRegime;
  status: string;
  created_at: string;
}

export interface ConfidenceFactor {
  value: number;
  base_weight: number;
  renormalized_weight: number;
  contribution: number;
}

export interface Rationale {
  pattern: { type: string; direction: "bullish" | "bearish"; timeframe: string; bar_ts: string };
  negation: { model_version: string; predicted_candles: number; predicted_window_end: string };
  correlation: { score: number; constituents: { symbol: string; direction: string }[] };
  rsi: number | null;
  confidence: { score: number; factors: Record<string, ConfidenceFactor>; unavailable_factors: string[] };
  risk: { score: number; reasons: string[]; vix_regime: VixRegime; is_expiry_day: boolean; is_low_liquidity: boolean };
  conviction_score: number;
  narrative: string | null;
}

export interface RecommendationDetail extends RecommendationSummary {
  rationale: Rationale;
}

export interface PaperTrade {
  id: string;
  recommendation_id: string;
  status: "open" | "closed";
  simulated_entry_price: number;
  simulated_exit_price: number | null;
  simulated_pnl_pct: number | null;
  opened_at: string | null;
  closed_at: string | null;
}
