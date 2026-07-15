"""Tests for src/engine/weight_update.py (Bayesian confidence-factor
weight update, CLAUDE.md item 9) — pure functions, no I/O.
"""

from src.engine.weight_update import (
    MAX_WEIGHT,
    MIN_WEIGHT,
    PRIOR_STRENGTH,
    default_prior,
    recompute_factor_weight,
)

_UNIFORM_PRIOR = (5.0, 5.0)  # alpha=beta=5, mean 0.5 — used where the exact center doesn't matter


def test_default_prior_mean_equals_the_base_weight():
    alpha, beta = default_prior(0.25)

    assert alpha / (alpha + beta) == 0.25
    assert alpha + beta == PRIOR_STRENGTH


def test_default_prior_for_a_different_base_weight():
    alpha, beta = default_prior(0.15)

    assert round(alpha / (alpha + beta), 4) == 0.15


def test_no_outcomes_returns_the_prior_mean_unchanged():
    # This is the exact bug live-testing caught: a factor with zero real
    # trade evidence must keep its own prior's mean, not collapse toward
    # some value shared by every factor.
    prior_alpha, prior_beta = default_prior(0.15)

    alpha, beta, weight = recompute_factor_weight([], prior_alpha, prior_beta)

    assert alpha == prior_alpha
    assert beta == prior_beta
    assert weight == 0.15


def test_all_wins_pushes_weight_up_toward_the_cap():
    _, _, weight = recompute_factor_weight([True] * 20, *_UNIFORM_PRIOR)

    assert weight == MAX_WEIGHT


def test_all_losses_pushes_weight_down_toward_the_floor():
    # Needs enough losses to actually overpower the informative prior and
    # cross the clamp boundary.
    _, _, weight = recompute_factor_weight([False] * 200, *_UNIFORM_PRIOR)

    assert weight == MIN_WEIGHT


def test_a_small_number_of_outcomes_does_not_swing_the_weight_much():
    # A handful of trades against a 10-pseudo-observation prior shouldn't
    # move the weight far from the prior's own mean.
    _, _, weight = recompute_factor_weight([True, True, False], *_UNIFORM_PRIOR)

    assert 0.45 < weight < 0.65


def test_alpha_beta_counts_match_win_loss_counts():
    prior_alpha, prior_beta = _UNIFORM_PRIOR

    alpha, beta, _ = recompute_factor_weight([True, True, True, False], prior_alpha, prior_beta)

    assert alpha == prior_alpha + 3
    assert beta == prior_beta + 1


def test_weight_is_monotonic_in_win_rate():
    # Kept below the 0.50 cap for all three so the comparison tests the
    # underlying posterior math, not the clamp.
    _, _, low = recompute_factor_weight([True] + [False] * 5, *_UNIFORM_PRIOR)
    _, _, mid = recompute_factor_weight([True, True] + [False] * 4, *_UNIFORM_PRIOR)
    _, _, high = recompute_factor_weight([True, True, True] + [False] * 3, *_UNIFORM_PRIOR)

    assert low < mid < high
