# Assumptions made while reconstructing the spec

The F1 session (`docs/f1_session_output.md`) locked scope and architecture at
a conversational level of detail but never rendered the full artifact set —
`buildspec.json` generation was cut off mid-Phase-3, and `architecture.md`,
`api_routes.md`, `ui_wireframes.md`, `strategy_schema.json`,
`database/schema.sql` were never generated at all in-session. Everything
below is a concrete technical decision I made to fill those gaps, consistent
with what was explicitly said. Review and correct anything that doesn't
match your intent.

## Safety-critical (please confirm these explicitly)

1. **No order placement, anywhere, ever, in this codebase.** The session
   kept "Live-algo (optional, future)" as an open execution mode, and one
   answer said "prefer have a switch mode to actual trade." Per your
   instruction in this task ("read-only market data, no order placement, no
   real money paths"), I have treated automated/live order execution as a
   **hard non-goal**, not a future phase — there is no order-placement
   client, no broker credentials with trading scope, and no route that
   submits an order. Only two execution modes exist: **Paper-trade**
   (simulated fills against real/historical data) and **Live-manual**
   (system recommends, you place the trade yourself in Zerodha's own app).
   If you later want real order placement, that's a distinct, explicit
   decision with its own compliance review — I did not build toward it even
   as a flag or stub.
2. Zerodha Kite Connect is used **read-only**: historical candles, quotes,
   OHLC, WebSocket ticks, OI/Greeks via the instruments/quote APIs. No
   `place_order`/`modify_order`/`cancel_order` calls exist in `src/`.

## Architecture / ML

3. **Negation-timing model**: the session locked PyTorch LSTM as the
   long-term choice, but that needs a labeled historical dataset that
   doesn't exist on day one. MVP ships a **statistical/heuristic model**
   (average candles-to-negate per pattern type × timeframe × VIX regime,
   computed from backtest data) with the LSTM as a documented v1.1 upgrade
   once enough labeled trade-journal data exists. Schema (`negation_predictions.model_version`)
   is built so swapping the model doesn't require a migration.
4. **Rationale generation uses Claude (Anthropic) only.** The session
   mentioned "GPT-4 + Claude" loosely for the strategy-marketplace video
   pipeline; I standardized on a single LLM vendor for a solo-founder MVP.
   Its job is narrating a rationale tree from numbers the deterministic
   engine already computed — it never decides confidence/risk/entry/exit
   itself, and it never sees or influences order flow.
5. **News/sentiment source is unresolved** (session never named a vendor).
   Modeled as a pluggable `news_ingestion` interface behind a feature flag,
   off by default. Matches this repo's existing convention of marking
   unresolved fields "unknown" rather than guessing a vendor with a real
   ToS/cost implication.
6. **Heavyweight watchlist**: defaulted to top 15 NIFTY constituents by
   index weight (Reliance, HDFC Bank, ICICI Bank, Infosys, TCS, L&T, Bharti
   Airtel, ITC, Kotak Bank, Axis Bank, SBI, Bajaj Finance, HUL, M&M, Sun
   Pharma) + 5 sector indices (NIFTY BANK, NIFTY IT, NIFTY FMCG, NIFTY
   PHARMA, NIFTY AUTO). Configurable at runtime, not hardcoded past MVP.
7. **VIX regime thresholds** (session never gave numbers, only "be wise
   about VIX"): Normal < 15, Elevated 15–20 (reduce conviction), High 20–30
   (tactical recs flagged low-conviction with warning), Extreme > 30
   (suppress new tactical recommendations, macro/BTST only). Configurable
   per user in `risk_settings`.
8. **"TradingView alerts"** in the session meant two different things at
   different points: (a) push alerts to a TradingView account, and (b)
   export a Pine Script the user runs themselves. TradingView has no public
   API for pushing alerts into a user's account, so I implemented only (b):
   the Strategy Marketplace export layer generates Pine Script; live
   notification channels are Telegram + email + in-app dashboard only.
9. **Intraday seasonality windows**: fixed at 10:00, 11:00, 12:30 (EU-open
   proxy), 13:30, 14:00, 14:30–15:00 IST per your exact list, stored as a
   configurable table (`seasonality_windows`) rather than hardcoded, so you
   can add/adjust windows without a code change.
10. **Backtest library**: `vectorbt` (Apache-2.0, permissive) for the
    Strategy Marketplace's independent backtest engine — the session never
    named one for this platform (unlike the earlier TradeSignal draft,
    which isn't this project). Avoids the GPL/AGPL licensing flags that
    applied to `backtrader`/`backtesting.py`.
11. **Auth**: simple email/password + JWT, single-user/small-team scale.
    Session never discussed multi-tenant SaaS concerns (no freemium tiers,
    no billing) — this is a personal/co-founder tool, not TradeSignal's
    freemium product, so none of that machinery was carried over.
12. **BVWR** (your "Breakout VWAP Retracement" algo from the session) is
    seeded as the first real entry in the Strategy Marketplace schema/table,
    marked `source_type: "user_rule"`, so the marketplace isn't empty on
    day one.

## Phase 2 (Foundation Layer) — new decisions

13. **Alembic, not docker-compose's `docker-entrypoint-initdb.d` mount, now
    owns schema creation.** Both applied the identical `database/schema.sql`,
    so a fresh volume would apply it twice and the second pass would fail
    on "relation already exists." Removed the raw mount from
    `docker-compose.yml`; the `api` service now runs `alembic upgrade head`
    on startup (`alembic/versions/0001_initial_schema.py` executes
    `database/schema.sql` verbatim — still the single canonical DDL source,
    just applied through Alembic as docs/CLAUDE.md's tech-stack table
    already specified).
14. **Fixed a latent bug in `database/schema.sql`** surfaced by running it
    through Alembic for the first time: `CREATE MATERIALIZED VIEW ...
    WITH (timescaledb.continuous) AS ...` defaults to `WITH DATA`, and
    TimescaleDB refuses to run that initial materialization inside a
    transaction block — which Alembic always wraps migrations in. `psql`
    running the file directly (the old docker-compose path) never hit this
    because it doesn't wrap a multi-statement script in one transaction.
    Added `WITH NO DATA` to both `candles_15m` and `candles_1h`; there's no
    candle data to backfill yet regardless. The worker pipeline (later
    phase) adds a refresh policy once ingestion is live.
15. **Only two ORM models exist so far**: `AuditLog` and `IndiaVixSnapshot`
    (`src/db/models.py`) — the tables Phase 2's own code touches. Every
    other table in `database/schema.sql` (patterns, recommendations,
    strategies, ...) stays schema-only until the phase that builds routes
    or jobs against it defines its model, per docs/CLAUDE.md's "small,
    testable modules" convention.
16. **`GET /api/v1/market/quote/{symbol}`** caches the on-demand Kite quote
    in Redis for 5 seconds (`DEFAULT_QUOTE_TTL_SECONDS`, `src/cache/redis_client.py`)
    — a number I picked (not specified anywhere) to keep repeated dashboard
    refreshes from burning Zerodha's rate limit while still feeling live.
    Easy to retune later.
17. **`GET /api/v1/market/vix`** fetches a live India VIX quote, computes
    the regime (thresholds from #7 above), and writes a row to
    `india_vix_snapshots` on every call. This is a Phase 2 stand-in for the
    worker pipeline's scheduled VIX ingestion (later phase) — it proves the
    Zerodha -> scoring-logic -> TimescaleDB path end to end, but isn't the
    real recurring ingestion job.

18. **`DATA_MODE` env var (default `sample`) picks the market-data source.**
    Zerodha's daily access token kept expiring mid-build, blocking Phase 2
    verification. Added `SampleMarketDataClient`
    (`src/market_data/sample_client.py`) — an in-memory random walk seeded
    from realistic NIFTY/BANKNIFTY/VIX anchors, no network calls — as the
    default so the whole stack (DB, Redis, FastAPI, tests) is provable
    end-to-end without a live Kite login. `DATA_MODE=live` switches
    `src/market_data/factory.py` back to the real `KiteMarketDataClient`
    (and still fails loudly if Kite credentials are missing in that mode).
    `/health`, `/api/v1/market/quote/{symbol}`, and `/api/v1/market/vix`
    all echo `data_mode` in their response so sample data can never be
    mistaken for real prices downstream. `scripts/kite_daily_login.py`
    remains the on-ramp to `DATA_MODE=live` once a fresh token exists.

19. **New `MarketDataInvalidRequest` exception (400)**, distinct from
    `MarketDataAuthError` (401, bad credentials) and `MarketDataUnavailable`
    (503, transient outage). Added after a code review found
    `KiteMarketDataClient._call_with_retry` was retrying permanent Kite
    errors (`InputException` bad symbol, `PermissionException` scope) as if
    transient, then reporting them as a misleading 503. `data_mode` is also
    now a `Literal["sample", "live"]` in `src/config.py` (was a bare `str`)
    so a `DATA_MODE` typo fails loudly at startup instead of silently
    falling through to the live-Kite branch in `src/market_data/factory.py`.

## Explicitly not built (matches session's own phasing)

- Live order execution (see #1 — permanent, not phase-gated).
- The actual LSTM negation model, video-transcription pipeline execution,
  and trained pattern-weight learning loop are Phase 3+/4+ per the
  `buildspec.json` phasing — MVP ships their schemas, interfaces, and a
  heuristic fallback, not the trained models themselves.
- Kubernetes/cloud deploy — Docker Compose only, matching the session's
  "start with Docker Compose, K8s for production later."
