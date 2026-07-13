import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  getAlertsStatus,
  getRiskSettings,
  getWatchlist,
  toggleConstituent,
  toggleSector,
  updateRiskSettings,
} from "../api/client";
import type { ExecutionMode } from "../api/types";

function WatchlistSection() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["watchlist"], queryFn: getWatchlist });

  const toggleC = useMutation({
    mutationFn: ({ symbol, isActive }: { symbol: string; isActive: boolean }) => toggleConstituent(symbol, isActive),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });
  const toggleS = useMutation({
    mutationFn: ({ symbol, isActive }: { symbol: string; isActive: boolean }) => toggleSector(symbol, isActive),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  if (isLoading) return <div className="empty-state">Loading…</div>;

  return (
    <div className="card">
      <div style={{ fontWeight: 600, marginBottom: 10 }}>Heavyweight constituents ({data?.constituents.length ?? 0})</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 16 }}>
        {data?.constituents.map((c) => (
          <label key={c.symbol} className="mono" style={{ fontSize: 12, color: c.is_active ? "var(--text)" : "var(--text-dim)" }}>
            <input
              type="checkbox"
              checked={c.is_active}
              onChange={(e) => toggleC.mutate({ symbol: c.symbol, isActive: e.target.checked })}
            />{" "}
            {c.symbol}
          </label>
        ))}
      </div>

      <div style={{ fontWeight: 600, marginBottom: 10 }}>Sector indices ({data?.sectors.length ?? 0})</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {data?.sectors.map((s) => (
          <label key={s.symbol} className="mono" style={{ fontSize: 12, color: s.is_active ? "var(--text)" : "var(--text-dim)" }}>
            <input
              type="checkbox"
              checked={s.is_active}
              onChange={(e) => toggleS.mutate({ symbol: s.symbol, isActive: e.target.checked })}
            />{" "}
            {s.symbol}
          </label>
        ))}
      </div>
      <p className="meta" style={{ marginTop: 10 }}>
        Inactive symbols are skipped by the heavyweight/sector correlation check on future recommendations.
      </p>
    </div>
  );
}

function RiskSettingsSection() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["risk-settings"], queryFn: getRiskSettings });
  const [form, setForm] = useState({
    vix_normal_max: 15,
    vix_elevated_max: 20,
    vix_high_max: 30,
    suppress_tactical_on_extreme: true,
    expiry_day_dampening: true,
    max_daily_recommendations: 20,
    execution_mode: "paper" as ExecutionMode,
  });

  useEffect(() => {
    if (data) setForm({ ...data });
  }, [data]);

  const save = useMutation({
    mutationFn: () => updateRiskSettings(form),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["risk-settings"] }),
  });

  if (isLoading || !data) return <div className="empty-state">Loading…</div>;

  return (
    <div className="card">
      <div style={{ fontWeight: 600, marginBottom: 10 }}>VIX regime thresholds</div>
      <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
        <label className="meta">
          Normal &lt;{" "}
          <input
            type="number"
            value={form.vix_normal_max}
            onChange={(e) => setForm({ ...form, vix_normal_max: Number(e.target.value) })}
            style={{ width: 60, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 }}
          />
        </label>
        <label className="meta">
          Elevated &lt;{" "}
          <input
            type="number"
            value={form.vix_elevated_max}
            onChange={(e) => setForm({ ...form, vix_elevated_max: Number(e.target.value) })}
            style={{ width: 60, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 }}
          />
        </label>
        <label className="meta">
          High &lt;{" "}
          <input
            type="number"
            value={form.vix_high_max}
            onChange={(e) => setForm({ ...form, vix_high_max: Number(e.target.value) })}
            style={{ width: 60, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 }}
          />
        </label>
        <span className="meta">Extreme above that</span>
      </div>

      <label className="meta" style={{ display: "block", marginBottom: 8 }}>
        <input
          type="checkbox"
          checked={form.suppress_tactical_on_extreme}
          onChange={(e) => setForm({ ...form, suppress_tactical_on_extreme: e.target.checked })}
        />{" "}
        Suppress Tactical recommendations in Extreme VIX regime
      </label>
      <label className="meta" style={{ display: "block", marginBottom: 8 }}>
        <input
          type="checkbox"
          checked={form.expiry_day_dampening}
          onChange={(e) => setForm({ ...form, expiry_day_dampening: e.target.checked })}
        />{" "}
        Dampen conviction on expiry days
      </label>
      <label className="meta" style={{ display: "block", marginBottom: 12 }}>
        Max recommendations/day{" "}
        <input
          type="number"
          value={form.max_daily_recommendations}
          onChange={(e) => setForm({ ...form, max_daily_recommendations: Number(e.target.value) })}
          style={{ width: 60, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 }}
        />
      </label>

      <div style={{ marginBottom: 12 }}>
        <div className="meta" style={{ marginBottom: 4 }}>Execution mode</div>
        {(["paper", "live_manual"] as ExecutionMode[]).map((mode) => (
          <label key={mode} className="meta" style={{ marginRight: 16 }}>
            <input
              type="radio"
              checked={form.execution_mode === mode}
              onChange={() => setForm({ ...form, execution_mode: mode })}
            />{" "}
            {mode}
          </label>
        ))}
      </div>

      <button className="btn" disabled={save.isPending} onClick={() => save.mutate()}>
        Save risk settings
      </button>
      {save.isSuccess && <span className="bullish" style={{ marginLeft: 10 }}>Saved.</span>}
      {save.isError && <div className="empty-state bearish">{(save.error as Error).message}</div>}
    </div>
  );
}

function AlertsStatusSection() {
  const { data, isLoading } = useQuery({ queryKey: ["alerts-status"], queryFn: getAlertsStatus });

  if (isLoading) return <div className="empty-state">Loading…</div>;

  return (
    <div className="card">
      <div style={{ fontWeight: 600, marginBottom: 10 }}>Alert channels (read-only)</div>
      <div className="trade-row">
        <span>Telegram</span>
        <span className={data?.telegram_configured ? "bullish" : "bearish"}>
          {data?.telegram_configured ? "configured" : "not configured"}
        </span>
      </div>
      <div className="trade-row">
        <span>Email</span>
        <span className={data?.email_configured ? "bullish" : "bearish"}>
          {data?.email_configured ? "configured" : "not configured"}
        </span>
      </div>
      <div className="trade-row">
        <span>Dashboard</span>
        <span className="bullish">configured</span>
      </div>
      <p className="meta" style={{ marginTop: 10 }}>{data?.note}</p>
    </div>
  );
}

export function SettingsScreen() {
  return (
    <div>
      <h2 style={{ fontSize: 15, marginBottom: 8 }}>Watchlist</h2>
      <WatchlistSection />

      <h2 style={{ fontSize: 15, margin: "20px 0 8px" }}>Risk settings</h2>
      <RiskSettingsSection />

      <h2 style={{ fontSize: 15, margin: "20px 0 8px" }}>Alerts</h2>
      <AlertsStatusSection />
    </div>
  );
}
