import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createRecommendation, listRecommendations } from "../api/client";
import { RecommendationCard } from "../components/RecommendationCard";
import type { RecommendationCategory } from "../api/types";

const CATEGORIES: RecommendationCategory[] = ["tactical", "impulse", "strategic", "btst"];
const HORIZONS = ["15m", "30m", "1h", "2h"];
const SCAN_SYMBOLS = ["NIFTY 50", "NIFTY BANK"];

export function Dashboard({ onSelect }: { onSelect: (id: string) => void }) {
  const [category, setCategory] = useState<RecommendationCategory>("tactical");
  const [horizon, setHorizon] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["recommendations", category],
    queryFn: () => listRecommendations({ category }),
    refetchInterval: 30_000,
  });

  const scan = useMutation({
    mutationFn: (symbol: string) => createRecommendation(symbol, horizon ?? "15m"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["recommendations"] }),
  });

  const recommendations = (data?.recommendations ?? []).filter((r) => !horizon || r.forecast_horizon === horizon);

  return (
    <div>
      <div className="tabs">
        {CATEGORIES.map((c) => (
          <button key={c} className={c === category ? "active" : ""} onClick={() => setCategory(c)}>
            {c[0].toUpperCase() + c.slice(1)}
          </button>
        ))}
      </div>

      <div className="horizon-selector">
        <button className={horizon === null ? "active" : ""} onClick={() => setHorizon(null)}>
          all
        </button>
        {HORIZONS.map((h) => (
          <button key={h} className={horizon === h ? "active" : ""} onClick={() => setHorizon(h)}>
            {h}
          </button>
        ))}
        <span style={{ flex: 1 }} />
        {SCAN_SYMBOLS.map((symbol) => (
          <button
            key={symbol}
            className="btn secondary"
            disabled={scan.isPending}
            onClick={() => scan.mutate(symbol)}
          >
            Scan {symbol}
          </button>
        ))}
      </div>

      {scan.isError && <div className="empty-state bearish">{(scan.error as Error).message}</div>}
      {scan.isSuccess && !scan.data.recommendation && (
        <div className="empty-state">{scan.data.message ?? "No setup found on this scan."}</div>
      )}

      {isLoading && <div className="empty-state">Loading…</div>}
      {error && <div className="empty-state bearish">{(error as Error).message}</div>}
      {!isLoading && recommendations.length === 0 && (
        <div className="empty-state">
          No {category} recommendations yet. Click "Scan" above to generate one from live sample data.
        </div>
      )}

      {recommendations.map((rec) => (
        <RecommendationCard key={rec.id} recommendation={rec} onSelect={onSelect} />
      ))}
    </div>
  );
}
