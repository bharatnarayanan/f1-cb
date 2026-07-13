"""Strategy fusion (F5.4) — merges two canonical_logic trees into one,
independently re-backtested before it's trusted (the route layer's job;
this module only produces the merged rule set).

No fusion formula exists anywhere in the spec — this is a new, documented
heuristic, same posture as conviction_score (Phase 4) and the negation
heuristic table (Phase 3):
- entry: union both strategies' conditions, ANDed together — a fused
  signal requires BOTH parents' entry criteria to agree, not either alone.
- guards: union both guard lists, plus `other`'s stop_loss folded in as an
  extra guard wherever it's expressible as a boolean condition (below_ma/
  above_ma/below_vwap/above_vwap) — keeps the merge at least as
  conservative as either parent on that axis.
- exit.targets: union both target lists (first to hit still triggers exit,
  same as a single strategy's multiple targets already work).
- exit.stop_loss: `base`'s stop_loss is kept as-is. Merging two DIFFERENT
  stop_loss types abstractly isn't well-defined without evaluating both
  against real data, so `base`'s own stop reasoning is preserved rather
  than silently overwritten, and `other`'s is added as a guard instead
  (see above) rather than dropped entirely.
"""

from typing import Any


def _stop_loss_as_guard(stop_loss: dict) -> dict | None:
    stop_type = stop_loss.get("type")
    if stop_type == "below_ma":
        return {"left": {"field": "close"}, "operator": ">", "right": stop_loss["reference_indicator"]}
    if stop_type == "above_ma":
        return {"left": {"field": "close"}, "operator": "<", "right": stop_loss["reference_indicator"]}
    if stop_type == "below_vwap":
        return {"left": {"field": "close"}, "operator": ">", "right": {"indicator": "VWAP", "period": 1}}
    if stop_type == "above_vwap":
        return {"left": {"field": "close"}, "operator": "<", "right": {"indicator": "VWAP", "period": 1}}
    return None  # fixed_points isn't expressible as a boolean condition


def fuse_strategies(base: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    if base["instrument"]["underlying"] != other["instrument"]["underlying"]:
        raise ValueError(
            f"cannot fuse strategies for different underlyings: "
            f"{base['instrument']['underlying']!r} vs {other['instrument']['underlying']!r}"
        )

    merged_conditions = list(base["entry"]["conditions"]) + list(other["entry"]["conditions"])

    merged_guards = list(base.get("guards", [])) + list(other.get("guards", []))
    other_stop_guard = _stop_loss_as_guard(other["exit"]["stop_loss"])
    if other_stop_guard is not None:
        merged_guards.append(other_stop_guard)

    base_targets = list(base["exit"]["targets"])
    merged_targets = base_targets + [t for t in other["exit"]["targets"] if t not in base_targets]

    return {
        "version": "1.0",
        "instrument": base["instrument"],
        "timeframe": base["timeframe"],
        "pattern_trigger": base.get("pattern_trigger"),
        "time_filters": base.get("time_filters", []),
        "entry": {
            "logic": "AND",
            "retracement_reference": base["entry"].get("retracement_reference", "none"),
            "conditions": merged_conditions,
        },
        "exit": {"targets": merged_targets, "stop_loss": base["exit"]["stop_loss"]},
        "guards": merged_guards,
        "is_preset": False,
    }
