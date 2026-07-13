import type { PaperTrade, RecommendationDetail, RecommendationSummary } from "./types";

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
