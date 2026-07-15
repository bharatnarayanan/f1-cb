"""Bayesian confidence-factor weight update (CLAUDE.md item 9: "Trade-
journal feedback loop -> Bayesian weight-update job"). Pure functions, no
I/O — a deterministic computation over structured win/loss counts, same
posture as every other scoring function in src/engine/ (docs/CLAUDE.md
section 3). The LLM never touches this number.

Method: Beta-Bernoulli conjugate update. Each factor has a Beta(alpha,
beta) posterior over "when this factor said a setup was aligned, did the
trade actually win?" alpha counts wins, beta counts losses, among trades
where the factor was aligned (value >= ALIGNMENT_THRESHOLD) for that
recommendation — a trade where the factor wasn't aligned doesn't test the
factor's correctness, so it isn't counted either way.

The prior is informative and per-factor: it's centered on that factor's
existing CONFIDENCE_WEIGHTS default (not a uniform 0.5 for every factor)
with PRIOR_STRENGTH pseudo-observations behind it — so a factor nobody has
real trade evidence on yet keeps its original documented weight instead of
silently collapsing toward 0.5, and a handful of real trades can't wildly
swing a weight away from that starting point either. A first version of
this used a flat alpha=beta=5 prior for every factor; live-testing caught
that it reset every zero-evidence factor's weight to exactly 0.5 the
moment recompute ran at all, which is wrong — corrected to a per-factor
prior instead.

recompute_factor_weight recomputes alpha/beta from the *full* history of
matching trade_journal outcomes every time it's called, rather than
incrementally updating a running total — simpler, avoids any
double-counting bug from a partially-applied previous run, and the
founder's trade volume is small enough that recomputing from scratch is
cheap.
"""

# Total pseudo-observations behind each factor's prior — split between
# alpha/beta in proportion to that factor's CONFIDENCE_WEIGHTS default
# (default_prior below), not a flat alpha=beta split.
PRIOR_STRENGTH = 10.0

# A factor's `value` (0-1) counts as "this factor said the setup was
# aligned" at or above this threshold — below it, the factor had no strong
# opinion on this particular trade, so the trade's outcome doesn't test
# whether the factor was right.
ALIGNMENT_THRESHOLD = 0.5

# No factor's weight may collapse to (near) zero or dominate outright —
# same "soft not hard" posture as src/engine/risk_guardrails.py's expiry
# dampening: strong evidence should move a weight, not eliminate a factor
# from the confidence formula entirely.
MIN_WEIGHT = 0.05
MAX_WEIGHT = 0.50


def default_prior(base_weight: float, strength: float = PRIOR_STRENGTH) -> tuple[float, float]:
    """The Beta(alpha, beta) prior for a factor whose documented default
    weight (CONFIDENCE_WEIGHTS) is base_weight — mean equals base_weight,
    total pseudo-observation count equals strength.
    """
    return base_weight * strength, (1.0 - base_weight) * strength


def recompute_factor_weight(outcomes: list[bool], prior_alpha: float, prior_beta: float) -> tuple[float, float, float]:
    """outcomes: one bool per trade_journal entry where this factor was
    aligned (value >= ALIGNMENT_THRESHOLD) for that recommendation — True
    for a win, False for a loss. Breakeven/not_taken outcomes and trades
    where this factor wasn't aligned are excluded before calling this
    (src/db/factor_weights.py's recompute_factor_weights does the
    filtering).

    prior_alpha/prior_beta: this factor's starting prior — see
    default_prior. Kept as explicit parameters (not a module constant) so
    each factor's prior can be centered on its own documented default
    weight instead of a single value shared by every factor.

    Returns (alpha, beta, weight) — alpha/beta persisted for the next
    recompute's audit trail, weight is what src/engine/scoring.py actually
    uses.
    """
    alpha = prior_alpha + sum(1 for won in outcomes if won)
    beta = prior_beta + sum(1 for won in outcomes if not won)
    posterior_mean = alpha / (alpha + beta)
    weight = round(max(MIN_WEIGHT, min(MAX_WEIGHT, posterior_mean)), 4)
    return alpha, beta, weight
