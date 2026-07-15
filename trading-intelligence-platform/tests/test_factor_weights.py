"""Tests for src/db/factor_weights.py (CLAUDE.md item 9's Bayesian
weight-update job) — resolver + recompute orchestration, DB mocked.
"""

import uuid
from unittest.mock import MagicMock

from src.db.factor_weights import get_confidence_weights, recompute_factor_weights
from src.db.models import FactorWeight, Recommendation, TradeJournalEntry
from src.engine.scoring import CONFIDENCE_WEIGHTS


def _factor_weight_row(name: str, weight: float, alpha: float = 5.0, beta: float = 5.0) -> FactorWeight:
    return FactorWeight(factor_name=name, weight=weight, alpha=alpha, beta=beta)


def test_get_confidence_weights_prefers_db_rows():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [
        _factor_weight_row("macro_sr_alignment", 0.30),
        _factor_weight_row("rsi_alignment", 0.10),
    ]

    weights = get_confidence_weights(db)

    assert weights == {"macro_sr_alignment": 0.30, "rsi_alignment": 0.10}


def test_get_confidence_weights_falls_back_to_constant_when_table_empty():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = []

    weights = get_confidence_weights(db)

    assert weights == dict(CONFIDENCE_WEIGHTS)


def _recommendation(rec_id, factors: dict) -> Recommendation:
    return Recommendation(
        id=rec_id,
        category="tactical",
        symbol="NSE:RELIANCE",
        action="BUY_CE",
        confidence_score=60.0,
        risk_score=20.0,
        conviction_score=50.0,
        rationale={"confidence": {"factors": factors}},
        vix_regime_at_creation="normal",
    )


def test_recompute_counts_wins_and_losses_for_aligned_factors_only():
    rec_id_win = uuid.uuid4()
    rec_id_loss = uuid.uuid4()
    rec_id_not_aligned = uuid.uuid4()

    entries = [
        TradeJournalEntry(recommendation_id=rec_id_win, user_id=uuid.uuid4(), outcome="win"),
        TradeJournalEntry(recommendation_id=rec_id_loss, user_id=uuid.uuid4(), outcome="loss"),
        # This factor wasn't aligned (value below threshold) for this trade
        # — its outcome must not count toward macro_sr_alignment's tally.
        TradeJournalEntry(recommendation_id=rec_id_not_aligned, user_id=uuid.uuid4(), outcome="win"),
        # breakeven/not_taken must be excluded entirely.
        TradeJournalEntry(recommendation_id=None, user_id=uuid.uuid4(), outcome="breakeven"),
    ]
    recommendations = [
        _recommendation(rec_id_win, {"macro_sr_alignment": {"value": 0.8}}),
        _recommendation(rec_id_loss, {"macro_sr_alignment": {"value": 0.9}}),
        _recommendation(rec_id_not_aligned, {"macro_sr_alignment": {"value": 0.1}}),
    ]

    db = MagicMock()
    db.execute.side_effect = [
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=entries)))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=recommendations)))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
    ]

    summary = recompute_factor_weights(db)

    assert summary["macro_sr_alignment"]["num_outcomes"] == 2  # only the win + loss, not the unaligned or breakeven
    assert db.add.called
    assert db.commit.called


def test_recompute_handles_no_journal_entries():
    db = MagicMock()
    db.execute.side_effect = [
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
    ]

    summary = recompute_factor_weights(db)

    for factor_name in CONFIDENCE_WEIGHTS:
        assert summary[factor_name]["num_outcomes"] == 0
