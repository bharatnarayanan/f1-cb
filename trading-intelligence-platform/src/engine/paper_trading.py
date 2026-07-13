"""Paper-trading simulator (F6.1) — simulated fills ONLY, no real order, no
real money anywhere in this codebase (docs/CLAUDE.md section 2).

No formula for a recommendation's target/stop exists anywhere in the spec
(Phase 4 deliberately left entry_price/stop_loss/target_price unset on
Recommendation — no option-chain data, see docs/assumptions.md #33). This
module is the new, documented heuristic that fills that gap for paper
trading specifically: reuse Phase 3's support/resistance levels (the
nearest favorable level as target, nearest adverse level as stop) and
Phase 3's negation-window prediction as a max-hold-time fallback — a trade
that hits neither target nor stop before its pattern's predicted negation
window closes is force-closed at market, since the setup that justified it
is no longer expected to hold.

The exit rule is resolved ONCE, at open time, and stored on the PaperTrade
row (src/db/models.py, migration 0005) — never recomputed on close. Real
trades don't have their stop silently move because the market shifted; a
simulated one shouldn't either.
"""

from dataclasses import dataclass
from datetime import datetime

from src.engine.scoring import SrContextLevel

# Fallback band when Phase 3 found no usable S/R level on either side —
# a documented starting default, not derived from real trade outcomes yet.
_FALLBACK_TARGET_PCT = 0.01
_FALLBACK_STOP_PCT = 0.005


@dataclass(frozen=True)
class ExitRule:
    target_price: float
    stop_loss_price: float


def resolve_exit_rule(direction: str, entry_price: float, sr_levels: list[SrContextLevel]) -> ExitRule:
    if direction not in ("bullish", "bearish"):
        raise ValueError(f"unknown direction={direction!r}")

    if direction == "bullish":
        favorable = [lvl.level_price for lvl in sr_levels if lvl.level_type == "resistance" and lvl.level_price > entry_price]
        adverse = [lvl.level_price for lvl in sr_levels if lvl.level_type == "support" and lvl.level_price < entry_price]
        target = min(favorable) if favorable else entry_price * (1 + _FALLBACK_TARGET_PCT)
        stop = max(adverse) if adverse else entry_price * (1 - _FALLBACK_STOP_PCT)
    else:
        favorable = [lvl.level_price for lvl in sr_levels if lvl.level_type == "support" and lvl.level_price < entry_price]
        adverse = [lvl.level_price for lvl in sr_levels if lvl.level_type == "resistance" and lvl.level_price > entry_price]
        target = max(favorable) if favorable else entry_price * (1 - _FALLBACK_TARGET_PCT)
        stop = min(adverse) if adverse else entry_price * (1 + _FALLBACK_STOP_PCT)

    return ExitRule(target_price=round(target, 2), stop_loss_price=round(stop, 2))


def evaluate_exit(
    direction: str,
    current_price: float,
    target_price: float,
    stop_loss_price: float,
    now: datetime,
    expiry_at: datetime | None,
) -> str | None:
    """Returns a close reason ("target" | "stop_loss" | "expiry"), or None
    if the trade should stay open.
    """
    if direction not in ("bullish", "bearish"):
        raise ValueError(f"unknown direction={direction!r}")

    if direction == "bullish":
        if current_price >= target_price:
            return "target"
        if current_price <= stop_loss_price:
            return "stop_loss"
    else:
        if current_price <= target_price:
            return "target"
        if current_price >= stop_loss_price:
            return "stop_loss"

    if expiry_at is not None and now >= expiry_at:
        return "expiry"
    return None


def compute_pnl_pct(direction: str, entry_price: float, exit_price: float) -> float:
    if direction not in ("bullish", "bearish"):
        raise ValueError(f"unknown direction={direction!r}")

    if direction == "bullish":
        return round((exit_price - entry_price) / entry_price * 100, 2)
    return round((entry_price - exit_price) / entry_price * 100, 2)
