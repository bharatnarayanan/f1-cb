# Trading Intelligence Platform — Architecture

Source of truth: `docs/buildspec.json`. This document expands the `tech` and
`solution` sections into a concrete system design. If anything here
conflicts with `buildspec.json`, the spec wins. Read-only/no-order-placement
boundary (`docs/CLAUDE.md` §2) applies to every component below without
exception.

## 1. System overview

```
                         ┌───────────────────────────┐
                         │         Frontend           │
                         │  React + Vite + TS SPA     │
                         └────────────┬───────────────┘
                                      │ REST + WS (JWT)
                         ┌────────────▼───────────────┐
                         │         API service          │
                         │    FastAPI (Python 3.11)     │
                         │  - auth                       │
                         │  - recommendations read/deep-dive│
                         │  - strategy marketplace CRUD    │
                         │  - trade journal / feedback     │
                         │  - paper trading control         │
                         │  - risk/watchlist settings        │
                         └───┬───────────────┬─────────┘
                             │               │
                  ┌──────────▼───┐   ┌───────▼────────┐
                  │  TimescaleDB  │   │     Redis       │
                  │  candles, OI, │   │  live tick cache,│
                  │  recs, journal│   │  rate limiting,   │
                  │  strategies,  │   │  alert dedup       │
                  │  audit log    │   └───────┬────────┘
                  └───────▲───────┘           │
                          │                   │
                 ┌────────┴───────────────────▼──────┐
                 │            Worker service            │
                 │  APScheduler-driven pipeline          │
                 │  1. Market data ingestion (read-only) │
                 │  2. Pattern detection                  │
                 │  3. Negation prediction                 │
                 │  4. SR + heavyweight/sector scoring      │
                 │  5. Seasonality/impulse scan               │
                 │  6. Confidence/risk/conviction scoring      │
                 │  7. Rationale generation (Claude)            │
                 │  8. Recommendation + alert dispatch           │
                 │  9. Paper-trade fill simulation                │
                 │ 10. Weight-update job (from trade journal)       │
                 └──────────────────────────────────────────┘
                             │
                  ┌──────────▼──────────┐
                  │  Zerodha Kite Connect │
                  │  (READ-ONLY: candles, │
                  │   quotes, WS ticks,   │
                  │   OI/Greeks, VIX)      │
                  │  NO order-placement    │
                  │  scope requested        │
                  └────────────────────────┘
```

## 2. Components

### API service (`src/main.py` + `src/routes/`)
Stateless FastAPI app exposing the REST surface in `docs/api_routes.md`.
Reads recommendations/patterns/journal/strategies that the worker already
computed and wrote to TimescaleDB — the API process itself never talks to
Zerodha directly on the hot path; it only reads what the worker last wrote,
plus lightweight on-demand queries (e.g. "current quote for symbol X" for
the dashboard) that are still read-only Kite Connect calls behind the same
`src/market_data/` abstraction the worker uses.

### Worker service
Runs the intelligence pipeline on a scheduled cadence (default: every 60s
for tick aggregation, every 5m-candle-close for pattern/recommendation
evaluation — configurable, not sub-second, matching the founder's own
manual-review cadence):

1. **Market data ingestion** (`src/market_data/`) — Kite Connect WebSocket
   ticks aggregated into 5m base candles in TimescaleDB; continuous
   aggregates roll these up to 10m/15m/30m/1h/2h/3h/1d. India VIX and
   heavyweight/sector index quotes pulled on the same cadence. **Read-only.**
2. **Pattern engine** (`src/patterns/`) — TA-Lib + pandas-ta candlestick
   detection (Engulfing, 3-candle inside/outside, Harami, Doji, Pin Bar)
   run per symbol per timeframe on each new candle close. Writes
   `patterns_detected`.
3. **Negation model** (`src/negation/`) — MVP: looks up the historical
   average candles-to-negate for this pattern type × timeframe × current
   VIX regime (precomputed nightly from backtest data) and writes a
   predicted negation window to `negation_predictions`. Interface is
   designed so a v1.1 LSTM model can be swapped in behind the same call
   signature (see `docs/assumptions.md` #3).
4. **Support/Resistance engine** (`src/levels/`) — pivot levels computed
   per timeframe (W→D→4h→1h→30m→5m), scored by historical hit frequency;
   confluence across timeframes raises the level's strength score. Writes
   `sr_levels`.
5. **Heavyweight/sector correlation** (`src/correlation/`) — for each
   index-level pattern, checks whether the top-15-by-weight constituents
   and the relevant sector index show the same pattern/direction at the
   same timeframe; produces an alignment score (0-1).
6. **Seasonality & impulse engine** (`src/seasonality/`) — runs a focused
   scan at the fixed intraday windows (10:00, 11:00, 12:30, 13:30, 14:00,
   14:30-15:00 IST) looking for outsized 5m moves + volume/OI spikes that
   don't fit the normal pattern-negation flow; flags these as **Impulse**
   category candidates independent of the main tactical pipeline.
7. **Confidence/risk/conviction scoring** (`src/scoring/`) — pure function
   over the outputs of steps 2-6 plus RSI: applies the fixed weighted
   confidence formula (`docs/buildspec.json` → `solution.core_features_mvp`),
   a separate risk score from VIX regime/expiry proximity/liquidity, and a
   conviction score. **Deterministic — no LLM involvement.**
8. **Rationale generation** (`src/rationale/`) — takes the structured
   factor scores from step 7 and asks Claude to narrate them into the
   collapsible reasoning tree shown in the UI. Claude receives only the
   already-computed numbers/labels; it does not receive raw market data
   and cannot alter the score.
9. **Recommendation + alert dispatch** (`src/recommendations/`,
   `src/alerts/`) — writes the `recommendations` row (category, entry/
   exit/strike where applicable, scores, rationale JSON) and dispatches to
   enabled channels (Telegram, dashboard, email), writing `alerts_log`.
10. **Paper-trade simulation** (`src/paper_trading/`) — when Paper mode is
    active for a user, opens a simulated position on a new recommendation
    and tracks it to a simulated exit using the same live/historical data,
    writing `paper_trades`. **No real order is ever placed in this or any
    other mode.**
11. **Weight-update job** (`src/learning/`) — nightly job that reads new
    `trade_journal` entries and applies a Bayesian update to pattern/
    negation confidence weights used by steps 2-3 going forward.

### Strategy Marketplace (`src/marketplace/`)
Separate from the main tactical pipeline, triggered by user submission
rather than the scheduled cadence:

1. **Ingestion** — accepts a YouTube URL, free-text description,
   pseudocode, or Pine Script.
2. **Strategy Agent** — for video sources, a transcription step (e.g.
   Whisper) produces a transcript; Claude then extracts canonical trading
   logic (indicators, thresholds, entry/exit rules) from the transcript or
   text/pseudocode input.
3. **Strategy Compiler** — converts canonical logic into (a) an executable
   `vectorbt`-compatible Python backtest function and (b) a Pine Script
   export.
4. **Independent backtest engine** — runs the compiled strategy against
   historical TimescaleDB OHLCV data, independent of and without bias from
   any existing strategy, producing win rate/Sharpe/drawdown/confidence.
5. **Fusion engine** — merges two strategies' rule sets (the founder's own
   + a marketplace strategy, or two marketplace strategies) with explicit
   conflict resolution, then re-runs the independent backtest on the fused
   rule set before it's marked usable.

The founder's own **BVWR (Breakout VWAP Retracement)** rule set is seeded
as the first Marketplace entry (`source_type: "user_rule"`) rather than the
system launching with an empty marketplace.

### Data model
See `database/schema.sql`. TimescaleDB hypertables (`candles`,
`oi_snapshots`, `india_vix_snapshots`) handle the time-series volume with
continuous aggregates for multi-timeframe rollups; standard relational
tables handle recommendations, trade journal, strategies, and the
append-only audit trail (`audit_log`, `alerts_log`, `strategy_audit_log`).

## 3. Why these choices (rationale from the spec)

| Decision | Why |
|---|---|
| FastAPI + separate worker | Async API stays responsive for dashboard reads while the intelligence pipeline (pattern detection, scoring, alerts) runs on its own schedule without blocking requests. |
| TimescaleDB over plain Postgres | Native continuous aggregates make multi-timeframe rollup (5m→3h) a query-time concern, not a write-time duplication problem. |
| TA-Lib + pandas-ta over custom pattern math | Battle-tested candlestick detection; spec explicitly prefers reusable open-source tech over reinventing indicator math. |
| Heuristic negation model before LSTM | An LSTM needs a labeled dataset that doesn't exist on day one; the heuristic ships value immediately and the trade journal it generates becomes the LSTM's future training data. |
| `vectorbt` for Strategy Marketplace backtests | Apache-2.0 (permissive, unlike `backtrader`/`backtesting.py`'s GPL/AGPL), fast enough to re-run on every fusion/ingestion event. |
| Claude for narration/extraction only, never scoring | Keeps the actual trade-relevant decision (confidence/risk/entry/exit) deterministic, testable, and auditable — the LLM's failure mode is a bad sentence, never a bad number. |
| No order-placement code path, anywhere | Structural safety requirement (`docs/CLAUDE.md` §2) — the founder trades manually; automating execution is a distinct decision this build does not make. |
| Docker Compose, not Kubernetes | Single-founder/single-VM MVP; matches the session's own phasing (Compose now, K8s only if it's ever needed later). |

## 4. Explicit non-goals (do not build)

Any order-placement path (automated or "optional live-algo"), real-money
paper trading, public multi-tenant SaaS/billing, direct push into a user's
TradingView account, a trained LSTM before the heuristic ships. Full list
and reasoning in `docs/buildspec.json` → `solution.explicit_non_goals` and
`docs/assumptions.md`.
