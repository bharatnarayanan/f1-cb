import type {
  AlertsStatus,
  BacktestResult,
  IngestStrategyResponse,
  JournalEntry,
  JournalOutcome,
  PaperTrade,
  RecommendationDetail,
  RecommendationSummary,
  RiskSettings,
  SectorIndexSummary,
  StrategyDetail,
  StrategySourceType,
  StrategySummary,
  WatchlistConstituentSummary,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? `Request to ${path} failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function listRecommendations(params: { category?: string; limit?: number } = {}) {
  const query = new URLSearchParams();
  if (params.category) query.set("category", params.category);
  query.set("limit", String(params.limit ?? 50));
  return request<{ recommendations: RecommendationSummary[] }>(`/api/v1/recommendations?${query}`);
}

export function getRecommendation(id: string) {
  return request<RecommendationDetail>(`/api/v1/recommendations/${id}`);
}

export function createRecommendation(symbol: string, timeframe = "15m") {
  const query = new URLSearchParams({ timeframe });
  return request<{
    symbol: string;
    data_mode: string;
    vix_regime: string;
    recommendation: RecommendationDetail | null;
    message?: string;
  }>(`/api/v1/recommendations/${encodeURIComponent(symbol)}?${query}`, { method: "POST" });
}

export function listPaperTrades(status?: string) {
  const query = status ? `?status=${status}` : "";
  return request<{ paper_trades: PaperTrade[] }>(`/api/v1/paper-trades${query}`);
}

export function openPaperTrade(recommendationId: string) {
  return request<PaperTrade>("/api/v1/paper-trades", {
    method: "POST",
    body: JSON.stringify({ recommendation_id: recommendationId }),
  });
}

export function closePaperTrade(id: string, force = false) {
  return request<PaperTrade & { close_reason: string | null }>(`/api/v1/paper-trades/${id}/close`, {
    method: "POST",
    body: JSON.stringify({ force }),
  });
}

export function fetchHealth() {
  return request<{ status: string; data_mode: string; safety_notice: string }>("/health");
}

export function listStrategies() {
  return request<{ strategies: StrategySummary[] }>("/api/v1/strategies");
}

export function getStrategy(id: string) {
  return request<StrategyDetail>(`/api/v1/strategies/${id}`);
}

export function ingestStrategy(body: { name: string; source_type: StrategySourceType; raw_input: string; source_ref?: string }) {
  return request<IngestStrategyResponse>("/api/v1/strategies", { method: "POST", body: JSON.stringify(body) });
}

export function backtestStrategy(id: string) {
  return request<BacktestResult>(`/api/v1/strategies/${id}/backtest`, { method: "POST" });
}

export function fuseStrategies(body: { name: string; base_strategy_id: string; other_strategy_id: string }) {
  return request<{ fused_strategy_id: string; resolved_logic: Record<string, unknown> }>("/api/v1/strategies/fuse", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function exportStrategy(id: string) {
  return request<{ strategy_id: string; pine_script: string }>(`/api/v1/strategies/${id}/export`);
}

export function listJournalEntries() {
  return request<{ entries: JournalEntry[] }>("/api/v1/journal");
}

export function logJournalOutcome(body: { recommendation_id?: string; outcome: JournalOutcome; realized_pnl_pct?: number; observation?: string }) {
  return request<JournalEntry>("/api/v1/journal", { method: "POST", body: JSON.stringify(body) });
}

export function getWatchlist() {
  return request<{ constituents: WatchlistConstituentSummary[]; sectors: SectorIndexSummary[] }>("/api/v1/settings/watchlist");
}

export function toggleConstituent(symbol: string, isActive: boolean) {
  return request<WatchlistConstituentSummary>(`/api/v1/settings/watchlist/constituents/${encodeURIComponent(symbol)}`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export function toggleSector(symbol: string, isActive: boolean) {
  return request<SectorIndexSummary>(`/api/v1/settings/watchlist/sectors/${encodeURIComponent(symbol)}`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export function getRiskSettings() {
  return request<RiskSettings>("/api/v1/settings/risk");
}

export function updateRiskSettings(body: Partial<RiskSettings>) {
  return request<RiskSettings>("/api/v1/settings/risk", { method: "PUT", body: JSON.stringify(body) });
}

export function getAlertsStatus() {
  return request<AlertsStatus>("/api/v1/settings/alerts");
}
