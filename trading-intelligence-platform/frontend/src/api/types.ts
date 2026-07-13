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

// Mirrors src/routes/strategies.py — canonical_logic's exact shape is
// docs/strategy_schema.json; the frontend never needs to construct or
// validate it, only display it (as JSON) and pass it through, so it's
// typed loosely here rather than mirroring every nested field.
export type StrategySourceType = "video" | "text" | "pseudocode" | "pine_script" | "user_rule";
export type StrategyStatus = "ingested" | "extracted" | "backtested" | "usable" | "rejected";

export interface StrategySummary {
  id: string;
  name: string;
  source_type: StrategySourceType;
  status: StrategyStatus;
}

export interface StrategyDetail extends StrategySummary {
  canonical_logic: Record<string, unknown> | null;
}

export interface IngestStrategyResponse {
  id: string;
  name: string;
  status: StrategyStatus;
  canonical_logic: Record<string, unknown> | null;
  extraction_error: string | null;
}

export interface BacktestTrade {
  entry_ts: string;
  exit_ts: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  return_pct: number;
}

export interface BacktestResult {
  strategy_id: string;
  data_mode: string;
  num_trades: number;
  win_rate_pct: number | null;
  sharpe_ratio: number | null;
  max_drawdown_pct: number | null;
  total_return_pct: number | null;
  confidence_score: number;
  trade_log: BacktestTrade[];
  assumptions: string[];
}

// Mirrors src/routes/journal.py.
export type JournalOutcome = "win" | "loss" | "breakeven" | "not_taken";

export interface JournalEntry {
  id: string;
  recommendation_id: string | null;
  outcome: JournalOutcome;
  realized_pnl_pct: number | null;
  observation: string | null;
}
