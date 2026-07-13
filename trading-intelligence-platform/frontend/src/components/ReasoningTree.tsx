import { useState, type ReactNode } from "react";
import type { Rationale } from "../api/types";

function Factor({ title, weight, children }: { title: string; weight?: string; children: ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="factor">
      <div className="factor-header" onClick={() => setOpen((o) => !o)}>
        <span>
          {open ? "▾" : "▸"} {title} {weight ? <span style={{ color: "var(--text-dim)" }}>(weight {weight})</span> : null}
        </span>
      </div>
      {open && <div className="factor-body">{children}</div>}
    </div>
  );
}

export function ReasoningTree({ rationale }: { rationale: Rationale }) {
  const { pattern, negation, correlation, rsi, confidence, risk } = rationale;

  const agreeing = correlation.constituents.filter((c) => c.direction === pattern.direction).length;
  const decisive = correlation.constituents.filter((c) => c.direction !== "flat").length;

  return (
    <div>
      <Factor title="Pattern" weight={confidence.factors.macro_sr_alignment ? "0.25" : undefined}>
        {pattern.direction} {pattern.type} on {pattern.timeframe} at {new Date(pattern.bar_ts).toLocaleString()}
      </Factor>

      <Factor title="Negation estimate">
        Model {negation.model_version}: pattern expected to remain valid for ~{negation.predicted_candles} candles
        (until {new Date(negation.predicted_window_end).toLocaleTimeString()})
      </Factor>

      {confidence.factors.macro_sr_alignment && (
        <Factor title="Macro S/R alignment" weight={String(confidence.factors.macro_sr_alignment.base_weight)}>
          Score {confidence.factors.macro_sr_alignment.value.toFixed(2)} — room to run before an adverse level,
          relative to distance from a supportive one.
        </Factor>
      )}

      <Factor
        title="Heavyweight/sector correlation"
        weight={confidence.factors.heavyweight_pattern_alignment ? String(confidence.factors.heavyweight_pattern_alignment.base_weight) : undefined}
      >
        {agreeing}/{decisive} watchlist constituents agree with this {pattern.direction} bias (score{" "}
        {correlation.score.toFixed(2)}).
      </Factor>

      {confidence.factors.rsi_alignment && (
        <Factor title="RSI alignment" weight={String(confidence.factors.rsi_alignment.base_weight)}>
          RSI {rsi ?? "unavailable"} — score {confidence.factors.rsi_alignment.value.toFixed(2)}
        </Factor>
      )}

      {confidence.unavailable_factors.length > 0 && (
        <Factor title="Not available this pass">
          {confidence.unavailable_factors.join(", ")} — no option-chain data fetched yet; weight redistributed
          across the factors above.
        </Factor>
      )}

      <Factor title="Risk">
        Score {risk.score.toFixed(0)} — {risk.reasons.join("; ")}
      </Factor>

      {rationale.narrative && <div className="narrative-box">{rationale.narrative}</div>}
    </div>
  );
}
