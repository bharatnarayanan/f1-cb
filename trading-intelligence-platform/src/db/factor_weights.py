"""Resolves and recomputes confidence-factor weights (CLAUDE.md item 9's
Bayesian weight-update job). Prefers the `factor_weights` DB row per
factor (editable only via recompute, not directly, unlike risk_settings)
over src/engine/scoring.py's CONFIDENCE_WEIGHTS constant — same
"the row actually controls behavior" posture as src/db/risk_settings.py.

recompute_factor_weights does real I/O (reads trade_journal + the linked
recommendations' rationale, writes factor_weights + an audit_log entry) —
the actual Beta-Bernoulli math lives in src/engine/weight_update.py, kept
pure per docs/CLAUDE.md section 3.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import AuditLog, FactorWeight, Recommendation, TradeJournalEntry
from src.engine.scoring import CONFIDENCE_WEIGHTS
from src.engine.weight_update import ALIGNMENT_THRESHOLD, default_prior, recompute_factor_weight

_COUNTED_OUTCOMES = {"win", "loss"}


def get_confidence_weights(db: Session) -> dict[str, float]:
    rows = db.execute(select(FactorWeight)).scalars().all()
    if not rows:
        return dict(CONFIDENCE_WEIGHTS)
    return {row.factor_name: float(row.weight) for row in rows}


def recompute_factor_weights(db: Session) -> dict[str, Any]:
    """Recomputes every factor's alpha/beta/weight from the *full* history
    of win/loss trade_journal entries whose recommendation is still
    resolvable (recommendation_id can be NULL — ON DELETE SET NULL — or
    point at a recommendation with no confidence rationale, e.g. an
    Impulse category recommendation that skipped some factors; both are
    silently excluded rather than erroring, same as
    src/engine/correlation.py treating "no data" as excluded, not
    disagreement).
    """
    entries = db.execute(
        select(TradeJournalEntry).where(TradeJournalEntry.outcome.in_(_COUNTED_OUTCOMES))
    ).scalars().all()

    recommendation_ids = {e.recommendation_id for e in entries if e.recommendation_id is not None}
    recommendations_by_id = {}
    if recommendation_ids:
        rows = db.execute(
            select(Recommendation).where(Recommendation.id.in_(recommendation_ids))
        ).scalars().all()
        recommendations_by_id = {r.id: r for r in rows}

    outcomes_by_factor: dict[str, list[bool]] = {name: [] for name in CONFIDENCE_WEIGHTS}
    for entry in entries:
        recommendation = recommendations_by_id.get(entry.recommendation_id)
        if recommendation is None:
            continue
        factors = (recommendation.rationale or {}).get("confidence", {}).get("factors", {})
        won = entry.outcome == "win"
        for factor_name, factor_data in factors.items():
            if factor_name not in outcomes_by_factor:
                continue
            if factor_data.get("value") is None or factor_data["value"] < ALIGNMENT_THRESHOLD:
                continue
            outcomes_by_factor[factor_name].append(won)

    existing_rows = {row.factor_name: row for row in db.execute(select(FactorWeight)).scalars().all()}

    summary: dict[str, Any] = {}
    for factor_name, outcomes in outcomes_by_factor.items():
        prior_alpha, prior_beta = default_prior(CONFIDENCE_WEIGHTS[factor_name])
        alpha, beta, weight = recompute_factor_weight(outcomes, prior_alpha, prior_beta)
        row = existing_rows.get(factor_name)
        before_weight = float(row.weight) if row is not None else CONFIDENCE_WEIGHTS[factor_name]

        if row is None:
            row = FactorWeight(factor_name=factor_name, weight=weight, alpha=alpha, beta=beta)
            db.add(row)
        else:
            row.weight = weight
            row.alpha = alpha
            row.beta = beta

        summary[factor_name] = {
            "before_weight": before_weight,
            "after_weight": weight,
            "alpha": alpha,
            "beta": beta,
            "num_outcomes": len(outcomes),
        }

    db.add(AuditLog(event_type="factor_weights_recomputed", entity_id=None, payload=summary))
    db.commit()

    return summary
