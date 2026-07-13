import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { backtestStrategy, exportStrategy, fuseStrategies, getStrategy, ingestStrategy, listStrategies } from "../api/client";
import { CumulativePnlChart } from "../components/CumulativePnlChart";
import type { BacktestResult, StrategySourceType } from "../api/types";

function SubmitStrategyForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState<StrategySourceType>("text");
  const [rawInput, setRawInput] = useState("");
  const queryClient = useQueryClient();

  const submit = useMutation({
    mutationFn: () => ingestStrategy({ name, source_type: sourceType, raw_input: rawInput }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategies"] });
      onDone();
    },
  });

  return (
    <div className="card">
      <div style={{ marginBottom: 10, fontWeight: 600 }}>Submit strategy</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        {(["text", "pseudocode", "pine_script", "video"] as StrategySourceType[]).map((t) => (
          <label key={t} style={{ fontSize: 12, color: "var(--text-dim)" }}>
            <input type="radio" checked={sourceType === t} onChange={() => setSourceType(t)} /> {t}
          </label>
        ))}
      </div>
      <input
        placeholder="Strategy name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        style={{ width: "100%", marginBottom: 8, padding: 6, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 }}
      />
      <textarea
        placeholder={sourceType === "video" ? "Paste the video's description/transcript — this app never downloads or transcribes video automatically" : "Describe the strategy in plain English, pseudocode, or Pine Script"}
        value={rawInput}
        onChange={(e) => setRawInput(e.target.value)}
        rows={4}
        style={{ width: "100%", marginBottom: 8, padding: 6, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4, fontFamily: "var(--font-mono)", fontSize: 12 }}
      />
      <button className="btn" disabled={!name || !rawInput || submit.isPending} onClick={() => submit.mutate()}>
        Submit
      </button>
      {submit.isSuccess && !submit.data.canonical_logic && (
        <div className="empty-state bearish" style={{ padding: "8px 0" }}>{submit.data.extraction_error}</div>
      )}
      {submit.isError && <div className="empty-state bearish" style={{ padding: "8px 0" }}>{(submit.error as Error).message}</div>}
    </div>
  );
}

function BacktestResultPanel({ result }: { result: BacktestResult }) {
  let cumulative = 0;
  const points = result.trade_log.map((t) => {
    cumulative += t.return_pct;
    return { time: new Date(t.exit_ts).toLocaleDateString(), cumulative_pnl_pct: Number(cumulative.toFixed(2)) };
  });

  return (
    <div className="card">
      <div className="scores" style={{ marginBottom: 12 }}>
        <div className="score-block"><div className="label">Trades</div><div className="value">{result.num_trades}</div></div>
        <div className="score-block"><div className="label">Win rate</div><div className="value">{result.win_rate_pct ?? "—"}%</div></div>
        <div className="score-block"><div className="label">Sharpe</div><div className="value">{result.sharpe_ratio ?? "—"}</div></div>
        <div className="score-block"><div className="label">Max DD</div><div className="value">{result.max_drawdown_pct ?? "—"}%</div></div>
        <div className="score-block"><div className="label">Confidence</div><div className="value">{result.confidence_score}</div></div>
      </div>
      {points.length > 0 ? <CumulativePnlChart points={points} /> : <div className="empty-state">No trades triggered in this backtest window.</div>}
      <div className="narrative-box" style={{ marginTop: 12 }}>
        <strong>Assumptions:</strong>
        <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
          {result.assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function StrategyMarketplace() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showSubmit, setShowSubmit] = useState(false);
  const [fuseTargetId, setFuseTargetId] = useState<string | null>(null);
  const [fuseName, setFuseName] = useState("");
  const queryClient = useQueryClient();

  const { data: listData } = useQuery({ queryKey: ["strategies"], queryFn: listStrategies });
  const { data: detail } = useQuery({
    queryKey: ["strategy", selectedId],
    queryFn: () => getStrategy(selectedId!),
    enabled: !!selectedId,
  });

  const backtest = useMutation({ mutationFn: (id: string) => backtestStrategy(id) });
  const exportPine = useMutation({ mutationFn: (id: string) => exportStrategy(id) });
  const fuse = useMutation({
    mutationFn: () => fuseStrategies({ name: fuseName, base_strategy_id: selectedId!, other_strategy_id: fuseTargetId! }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategies"] });
      setFuseTargetId(null);
      setFuseName("");
    },
  });

  const strategies = listData?.strategies ?? [];

  return (
    <div style={{ display: "flex", gap: 20 }}>
      <div style={{ flex: 1, minWidth: 280 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <h2 style={{ fontSize: 15 }}>Strategies</h2>
          <button className="btn secondary" onClick={() => setShowSubmit((s) => !s)}>
            {showSubmit ? "Cancel" : "+ Submit strategy"}
          </button>
        </div>
        {showSubmit && <SubmitStrategyForm onDone={() => setShowSubmit(false)} />}
        {strategies.map((s) => (
          <div key={s.id} className="card" style={{ cursor: "pointer" }} onClick={() => setSelectedId(s.id)}>
            <div className="rec-card-main">
              <div className="symbol">{s.name}</div>
              <div className="meta">
                {s.source_type} &middot; {s.status}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ flex: 2 }}>
        {!detail && <div className="empty-state">Select a strategy to see its rule set, backtest it, or export it.</div>}
        {detail && (
          <div>
            <h2 style={{ fontSize: 16 }}>{detail.name}</h2>
            <p className="meta" style={{ marginBottom: 12 }}>
              {detail.source_type} &middot; {detail.status}
            </p>

            {!detail.canonical_logic && <div className="empty-state">No canonical_logic yet — extraction hasn't run or hasn't succeeded.</div>}

            {detail.canonical_logic && (
              <>
                <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                  <button className="btn" disabled={backtest.isPending} onClick={() => backtest.mutate(detail.id)}>
                    {backtest.isPending ? "Running backtest…" : "Run backtest"}
                  </button>
                  <button className="btn secondary" disabled={exportPine.isPending} onClick={() => exportPine.mutate(detail.id)}>
                    Export Pine Script
                  </button>
                </div>

                {backtest.data && <BacktestResultPanel result={backtest.data} />}
                {backtest.isError && <div className="empty-state bearish">{(backtest.error as Error).message}</div>}

                {exportPine.data && (
                  <pre className="card mono" style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                    {exportPine.data.pine_script}
                  </pre>
                )}

                <div className="card" style={{ marginTop: 16 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>Fuse with another strategy</div>
                  <select
                    value={fuseTargetId ?? ""}
                    onChange={(e) => setFuseTargetId(e.target.value || null)}
                    style={{ marginRight: 8, background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 4, padding: 4 }}
                  >
                    <option value="">Choose a strategy…</option>
                    {strategies.filter((s) => s.id !== detail.id).map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                  <input
                    placeholder="Fused strategy name"
                    value={fuseName}
                    onChange={(e) => setFuseName(e.target.value)}
                    style={{ marginRight: 8, padding: 4, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 }}
                  />
                  <button className="btn" disabled={!fuseTargetId || !fuseName || fuse.isPending} onClick={() => fuse.mutate()}>
                    Fuse
                  </button>
                  {fuse.isSuccess && <div style={{ marginTop: 8 }} className="bullish">Fused strategy created — see it in the list.</div>}
                  {fuse.isError && <div className="empty-state bearish">{(fuse.error as Error).message}</div>}
                </div>

                <details style={{ marginTop: 16 }}>
                  <summary style={{ cursor: "pointer", color: "var(--text-dim)", fontSize: 12 }}>Raw canonical_logic</summary>
                  <pre className="mono" style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>
                    {JSON.stringify(detail.canonical_logic, null, 2)}
                  </pre>
                </details>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
