"""Multi-timeframe support/resistance engine (F3.4).

Fractal swing-high/low detection + price-proximity clustering with
hit-frequency confluence scoring, per docs/CLAUDE.md section 4 ("numpy,
scipy" — no ML, a deterministic geometric computation over candle data,
consistent with section 3's "deterministic computations over structured
data" rule).

A bar is a swing high if its high is the strict local max within
+/- swing_lookback bars either side (a fractal peak); swing low similarly.
Swing points within cluster_tolerance_pct of each other are merged into one
level; confluence_score is that level's hit_count normalized against the
most-touched level in the same call (0-1, matching sr_levels.confluence_score's
documented range).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

_DEFAULT_SWING_LOOKBACK = 3
_DEFAULT_CLUSTER_TOLERANCE_PCT = 0.001


@dataclass
class SrLevel:
    level_price: float
    level_type: str  # "support" | "resistance"
    hit_count: int
    confluence_score: float
    last_hit_ts: datetime


def calculate_sr_levels(
    candles: list[dict[str, Any]],
    swing_lookback: int = _DEFAULT_SWING_LOOKBACK,
    cluster_tolerance_pct: float = _DEFAULT_CLUSTER_TOLERANCE_PCT,
) -> list[SrLevel]:
    if len(candles) < swing_lookback * 2 + 1:
        return []

    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    timestamps = [c.get("date") or c["ts"] for c in candles]
    n = len(candles)

    swing_highs: list[tuple[float, datetime]] = []
    swing_lows: list[tuple[float, datetime]] = []
    for i in range(swing_lookback, n - swing_lookback):
        window_highs = highs[i - swing_lookback : i + swing_lookback + 1]
        if highs[i] == max(window_highs) and window_highs.count(highs[i]) == 1:
            swing_highs.append((highs[i], timestamps[i]))

        window_lows = lows[i - swing_lookback : i + swing_lookback + 1]
        if lows[i] == min(window_lows) and window_lows.count(lows[i]) == 1:
            swing_lows.append((lows[i], timestamps[i]))

    all_levels = _cluster_levels(swing_highs, cluster_tolerance_pct, "resistance") + _cluster_levels(
        swing_lows, cluster_tolerance_pct, "support"
    )
    if not all_levels:
        return []

    max_hits = max(level.hit_count for level in all_levels)
    for level in all_levels:
        level.confluence_score = round(level.hit_count / max_hits, 3)
    return all_levels


def _cluster_levels(
    points: list[tuple[float, datetime]], tolerance_pct: float, level_type: str
) -> list[SrLevel]:
    if not points:
        return []

    points_sorted = sorted(points, key=lambda p: p[0])
    clusters: list[list[tuple[float, datetime]]] = []
    for price, ts in points_sorted:
        if clusters and abs(price - clusters[-1][-1][0]) / clusters[-1][-1][0] <= tolerance_pct:
            clusters[-1].append((price, ts))
        else:
            clusters.append([(price, ts)])

    levels = []
    for cluster in clusters:
        avg_price = sum(price for price, _ in cluster) / len(cluster)
        last_hit = max(ts for _, ts in cluster)
        levels.append(
            SrLevel(
                level_price=round(avg_price, 2),
                level_type=level_type,
                hit_count=len(cluster),
                confluence_score=0.0,  # normalized by the caller once all levels are known
                last_hit_ts=last_hit,
            )
        )
    return levels
