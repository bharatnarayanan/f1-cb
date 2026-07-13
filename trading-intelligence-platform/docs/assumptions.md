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

## Phase 3 (Core Engine) — new decisions

20. **TA-Lib's C library is installed from its official prebuilt `.deb`**
    (`Dockerfile`, arch-detected via `dpkg --print-architecture`), not
    compiled from the old sourceforge 0.4.0 source tarball — that source
    fails to build on Debian trixie's gcc 14 (C23 makes an ABI mismatch in
    the generated Cython wrapper a hard error). `requirements.txt` pins the
    matching `TA-Lib==0.7.0` Python wrapper (also newer than originally
    planned — 0.4.28 predates the C23 fix).
21. **`pandas-ta` is deliberately NOT a dependency**, despite docs/CLAUDE.md
    section 4 listing "TA-Lib + pandas-ta." Confirmed with you directly:
    pandas-ta's PyPI releases now require Python 3.12+ (new maintainers,
    new versioning), incompatible with this repo's locked Python 3.11.
    TA-Lib alone covers every Phase 3 need — CDL* candlestick functions now
    (`src/engine/patterns.py`), RSI/ATR for confidence scoring later.
22. **Migration 0001 is now a frozen, one-time snapshot; 0002+ are
    incremental deltas.** `alembic/versions/0001_initial_schema.py` used to
    be described as re-runnable against `database/schema.sql`, but it's
    already been applied to a real database — editing it again after the
    fact is not safe Alembic practice. `0002_multi_timeframe_aggregates.py`
    is the first migration under the new convention: it carries its own DDL
    rather than re-executing schema.sql. `database/schema.sql` is still
    hand-kept in sync as the full current-state reference, but only 0001
    executes it verbatim (see the new header comment).
23. **Negation heuristic's base candles-to-negate table**
    (`src/engine/negation.py`) is a documented starting default (engulfing
    3.0, three_inside/three_outside 4.0, harami 5.0, doji 2.5, pin_bar 3.5),
    scaled by VIX regime and timeframe — no trade-journal history exists
    yet to derive it from real outcomes. Swap-in point for backtest-derived
    values or the v1.1 LSTM model is `model_version` (already
    `"heuristic-v1"` per docs/CLAUDE.md section 4), no schema change needed.
24. **"Pin bar" has no native TA-Lib function**, so it's detected with a
    hand-rolled geometric rule (small body relative to full range, a
    dominant wick at least 2.5x the body) — a standard price-action
    definition. Thresholds started looser (0.35 body-to-range, 2.0x wick)
    but were tightened after a real sample-mode scan showed ~15% of
    ordinary candles false-flagging as pin bars; real calibration is a
    trade-journal feedback-loop job (later phase), not further hand-tuning.
25. **TA-Lib's doji-family functions need ~11 bars of internal averaging
    lookback before they'll flag anything** (confirmed empirically) — the
    5-bar floor I initially picked was wrong and would have silently never
    detected a doji on a short candle series. `_MIN_BARS_FOR_DETECTION` in
    `src/engine/patterns.py` is now 15.
26. **`GET /api/v1/scan/{symbol}` is a Phase 3 stand-in for the scheduled
    `worker` service** (not built yet), same pattern as `/vix` standing in
    for scheduled VIX ingestion (#17 above). It chains pattern detection ->
    negation -> support/resistance across `SCAN_TIMEFRAMES = ["5m", "15m",
    "1h"]` and persists every result. Calling it repeatedly with
    overlapping lookback windows can persist duplicate rows — acceptable
    for demonstrating the engine end-to-end, not for production polling;
    the real worker will dedupe by only scanning newly-closed candles.
27. **Support/resistance is computed per-timeframe on whatever candles are
    passed in** (`src/engine/support_resistance.py`), not the raw session's
    "D, 4h, 1h, 30m" cross-timeframe confluence — there's no daily/4h
    aggregate or long-history ingestion yet (sample mode's scan window is
    hours, not weeks). True cross-timeframe SR confluence is future work
    once real historical depth exists.
28. **`resolve_instrument_token` (`src/market_data/instruments.py`) only
    resolves symbols present in `MarketDataClient.get_instruments()`.**
    Sample mode's instrument list was NIFTY 50 / NIFTY BANK / INDIA VIX only
    as of Phase 3; Phase 4 (#29 below) extended it to the full watchlist.
    Any symbol still outside that list fails with a 400 until added, or
    `DATA_MODE=live` is used.

## Phase 4 (Intelligence) — new decisions

Two scope forks were confirmed with you directly before building, since
both touch things nothing in this codebase does yet:

29. **Confidence scoring's `OI_accumulation` and `strike_candle_pattern`
    factors stay `None`/"unknown" this pass** — nothing fetches option-chain
    or strike-level data yet (only index/equity candles exist). Rather than
    silently zeroing their 0.15+0.20 combined weight (which would cap
    confidence at 65% of its stated scale forever), `compute_confidence`
    (`src/engine/scoring.py`) proportionally renormalizes the weights of
    whatever factors ARE known and reports which ones weren't in
    `unavailable_factors` — visible in every recommendation's rationale
    tree, never hidden. `SampleMarketDataClient` was extended with the full
    15-constituent + 5-sector-index watchlist (was NIFTY 50/BANK/VIX only)
    so `heavyweight_pattern_alignment` has real sample data to score against.
30. **Claude narration (`src/llm/narration.py`) is built but not
    live-tested** — no real `ANTHROPIC_API_KEY` in this environment. It
    degrades gracefully (an explicit "Narration unavailable" string, not a
    crash or a silent empty field) when the key is missing/placeholder or
    the API call fails, so a fully-scored, valid recommendation is never
    blocked by an optional narration layer. `ANTHROPIC_MODEL =
    "claude-sonnet-5"` is a starting choice, easy to change. Test coverage
    (`tests/test_narration.py`) mocks the Anthropic client throughout —
    you'll need to test the real narrated output yourself once a key exists.
31. **`conviction_score` has no formula anywhere in the original spec** —
    it's a new documented assumption: `confidence dampened by risk, capped
    at a 50% maximum reduction` (`compute_conviction`,
    `src/engine/scoring.py`), so a maxed-out risk score can never fully
    zero out a genuinely strong confidence signal (risk_score is already
    shown alongside it for that; conviction isn't meant to duplicate it).
32. **Only Tactical and Impulse recommendation categories are reachable**
    (`src/engine/recommendations.py`) — Strategic (2-5 day outlook) needs
    daily candles (this repo only aggregates up to 3h) and BTST
    (expiry-adjacent) needs an options-expiry calendar; neither exists yet.
    Requesting an unsupported timeframe raises loudly rather than
    mislabeling a recommendation's category.
33. **`action` is a directional CE/PE proxy only** (`BUY_CE` for bullish,
    `BUY_PE` for bearish) — `strike`, `option_type`, `entry_price`,
    `stop_loss`, `target_price` all stay unset on every recommendation.
    There's no strike-selection logic or option-chain pricing built yet
    (same gap as #29); recommending a specific strike or price here would
    fabricate precision this system doesn't actually have.
34. **`watchlist_constituents`/`sector_indices` are seeded (migration 0003)
    with symbol/name/sector only — `index_weight_pct` is left NULL.**
    Real NIFTY index weights drift over time and NSE publishes the
    authoritative current figures; hardcoding a possibly-stale percentage
    here would misrepresent it as current fact.
35. **`compute_macro_sr_alignment`'s "room to run" formula and the impulse-
    move 3x-average-range threshold** (`src/engine/seasonality.py`) are
    both documented starting heuristics, same caveat as Phase 3's
    negation-model table (#23) — not derived from real trade outcomes yet.

## Phase 5 (Strategy Marketplace) — new decisions

Two scope forks were confirmed with you directly before building (plan
proposed, approved as-is):

36. **No auth/login system exists yet, but `strategies.created_by` is a
    NOT NULL FK to `users`.** Rather than build login/JWT (its own,
    unbuilt phase), migration `0004_seed_founder_strategy.py` seeds one
    default founder user (`founder@local`, fixed UUID
    `00000000-0000-0000-0000-000000000001`) with a bcrypt-hashed random
    password that no login endpoint can ever authenticate with — it exists
    solely to satisfy the FK, not as a real credential.
37. **Video-URL ingestion accepts a URL field, but never downloads or
    transcribes anything.** `buildspec.json` lists video ingestion as MVP
    but separately marks *automated* transcription as v2-only ("MVP
    requires a manual trigger per submission"). `source_type="video"`
    strategies still require you to paste the actual description/transcript
    into `raw_input` yourself — no yt-dlp/speech-to-text dependency was
    added, avoiding both a heavy new dependency footprint and YouTube's
    ToS gray area around automated downloading.
38. **`vectorbt==0.28.5`, not the current `1.x`** — `vectorbt>=1.0.0`
    requires `numpy>=2.4.6`/`pandas>=3.0.3`, incompatible with the
    `numpy==1.26.4`/`pandas==2.1.4` this repo is already pinned to (TA-Lib,
    scipy). `0.28.5` is the newest release still on `numpy>=1.23,pandas<3.0`
    — same "avoid the just-bumped major" reasoning as Phase 3's TA-Lib/
    pandas-ta calls. `bcrypt==4.3.0` similarly pinned one minor behind its
    own fresh `5.0.0` major bump.
39. **The strategy interpreter (`src/engine/strategy_interpreter.py`) and
    backtest engine (`src/engine/backtest.py`) simulate a LONG-ONLY
    position on the underlying's close price** — a proxy for buying the
    strategy's declared option leg (CE/PE), not real option premium/
    greeks/time-decay P&L. Exit decisions happen on bar close only (no
    intrabar high/low look-ahead). `fixed_points` targets/stops are
    converted to a percentage via vectorbt's entry-relative `sl_stop`/
    `tp_stop`, using the first candle's close in the fetched window as the
    reference price. No commissions or slippage are modeled. All four are
    returned in every backtest response's `assumptions` field, per
    docs/CLAUDE.md section 6 ("backtests must document assumptions... no
    look-ahead bias") — never presented as idealized-but-unstated.
40. **`day_high`/`day_low` exit targets are an expanding max/min over the
    whole fetched window, not a true session-reset daily high/low** — this
    codebase doesn't track session/day boundaries anywhere yet.
41. **`VWAP` is a continuous cumulative VWAP over the fetched window, not a
    session-reset VWAP** — same session-boundary gap as #40.
42. **`backtest_confidence_score` (`src/engine/backtest.py`) has no formula
    anywhere in the spec** — a new documented heuristic: a blend of win
    rate, a capped Sharpe ratio, and drawdown severity, scaled down for a
    thin trade sample (fewer than 20 trades is weak evidence either way).
    Same posture as Phase 4's `conviction_score`.
43. **Strategy fusion's merge rule (`src/engine/fusion.py`) has no formula
    anywhere in the spec** — a new documented heuristic: entry conditions
    from both parents are unioned and ANDed (both must agree), guards are
    unioned, exit targets are unioned, and the base strategy's stop_loss is
    kept as-is (merging two different stop_loss TYPES isn't well-defined
    without evaluating both against real data) with the other strategy's
    stop folded in as an extra guard wherever it's expressible as one.
44. **Claude extraction (`src/llm/extraction.py`) is built and unit-tested
    against a mocked Anthropic client, not exercised against a real
    `ANTHROPIC_API_KEY`** — same posture as Phase 4's narration. Unlike
    narration, a missing key here raises `ExtractionUnavailable` (a hard
    failure) rather than degrading to a placeholder: canonical_logic has
    no honest "unknown" stand-in for an entire rule set the way narration's
    one optional paragraph did. A strategy submitted without extraction
    succeeding stays in `ingested` status, never silently marked ready.
45. **BVWR (the founder's own strategy) is seeded using the exact
    `canonical_logic` already hand-authored in `docs/strategy_schema.json`'s
    `examples`** — no extraction needed for this one, it's the schema's own
    worked example, seeded at `status="extracted"` (ready to backtest via
    the API; migrations don't call live backtest logic).

## Phase 6 (Execution + Alerts) — new decisions

Two scope forks confirmed with you directly before building (plan
proposed, approved as-is):

46. **Paper trades need a target/stop/exit rule, and none is defined
    anywhere in the spec** — Phase 4 deliberately left Recommendation's
    `entry_price`/`stop_loss`/`target_price` unset (#33, no option-chain
    data). `src/engine/paper_trading.py`'s `resolve_exit_rule` is a new
    documented heuristic: reuse Phase 3's support/resistance levels (the
    nearest favorable level as target, nearest adverse level as stop,
    falling back to a ±1%/±0.5% band when no S/R level exists on a side)
    plus Phase 3's negation-window prediction as a max-hold-time fallback
    — a trade force-closes at market if the setup's predicted negation
    window passes before target or stop is hit. Resolved ONCE at open
    time and stored on the row (migration 0005 adds `target_price`/
    `stop_loss_price`/`expiry_at` to `paper_trades`, not in the original
    schema) — never recomputed on close, so it can't silently drift.
47. **Telegram/email alert dispatch is built and mocked-tested, not
    live-tested** — no `TELEGRAM_BOT_TOKEN`/SMTP credentials configured in
    this environment, same posture as Claude/live-Kite before it. Every
    dispatch attempt records `dispatch_status` honestly (`sent` only on
    real success, `failed` otherwise — never faked). `python-telegram-bot`
    v20+ is fully async; `src/alerts/telegram.py` wraps the one call site
    with `asyncio.run()` rather than converting routes to async, keeping
    this codebase's existing synchronous-route convention intact.
48. **The dashboard alert channel has no real destination yet** — no
    frontend exists (that's Phase 7). Writing the `alerts_log` row with
    `dispatch_status="sent"` immediately IS its delivery: once a dashboard
    exists, that table is its data source, not a placeholder standing in
    for a channel that doesn't work yet.
49. **The trade-journal feedback loop ships as logging only.** The actual
    Bayesian pattern/negation weight-update job (docs/CLAUDE.md section 9)
    needs the scheduled `worker` service, which no phase has built yet —
    consistent with every prior phase's stance on the same gap. Explicitly
    flagged as deferred, not silently dropped.
50. **Two real bugs were caught by live end-to-end testing that fully-
    mocked unit tests had missed**, both fixed with regression tests added
    directly against the failure mode (verified by reverting each fix and
    confirming the new test fails, per this repo's standard practice):
    - `Recommendation.id` (`default=uuid.uuid4`) is populated by
      SQLAlchemy at flush time, not object construction — dispatching
      alerts before `db.flush()` left every `AlertLog.recommendation_id`
      `None`, violating `alerts_log`'s NOT NULL constraint at commit.
      Fixed by flushing before dispatch in
      `src/routes/recommendations.py`.
    - Postgres `Numeric` columns come back as `decimal.Decimal`, which
      can't mix with `float` in arithmetic — `compute_pnl_pct`'s
      subtraction crashed on a real paper-trade close. Fixed by casting
      to `float` at the DB-read boundary in `src/routes/paper_trades.py`.

## Phase 7 (UI + Dashboard, Pass 1) — new decisions

Proposed as a two-pass split and confirmed with you before building:

51. **Login is deliberately NOT built this pass** — `docs/ui_wireframes.md`
    includes a Login screen, but no auth backend exists (Phase 5
    specifically avoided building one, seeding a single founder user
    instead). The dashboard loads directly against the API with no auth
    wall — matches this tool's own framing (docs/CLAUDE.md section 10:
    "personal decision-support tool, not a distributed advisory product").
    Login stays deferred to a future pass if real auth is ever wanted.
52. **Pass 1 scope is the 3 highest-value screens**: Dashboard home
    (category tabs + horizon filter + recommendation cards), the
    collapsible reasoning-tree deep-dive, and Paper Trading (open
    positions + Recharts equity curve). Strategy Marketplace UI, backtest
    result view, trade journal UI, watchlist/risk settings UI, and alerts
    settings UI are deferred to a future pass — all already have working
    backend APIs from Phases 4-6, they just don't have a screen yet.
53. **TanStack Query (`@tanstack/react-query`) added for API data
    fetching/caching** — not in docs/CLAUDE.md's stack table (which only
    locks React + TypeScript + Vite + Recharts), but a small, standard,
    well-established addition rather than hand-rolling fetch/loading-state
    plumbing across three screens. Flagged for visibility in the Phase 7
    proposal, not treated as a stack conflict needing separate approval.
54. **Two small backend gaps found while building the frontend, fixed
    inline (not new forks — natural extensions of already-approved
    scope):** `GET /api/v1/recommendations` (list) and
    `GET /api/v1/recommendations/{id}` (detail) didn't exist — only the
    creating `POST` did, and the dashboard needs something to list.
    `POST /api/v1/recommendations/{symbol}`'s response was also missing
    the new recommendation's `id`, and `GET /api/v1/paper-trades` was
    missing `opened_at`/`closed_at`, both needed for the frontend to link
    into the deep-dive view and build a real chronological equity curve.
55. **No browser-automation tool is available in this environment** — every
    other verification method was used (`tsc -b` typecheck, `vite build`
    production build, dev server boot + HTML/module serving confirmed via
    curl, CORS headers confirmed present against the real backend), but
    nobody has visually clicked through the rendered UI yet. Said
    explicitly rather than claimed as done — see docs/CLAUDE.md's own
    working-style rule on this.
56. **`frontend` service added to `docker-compose.yml`** (`node:20-slim`,
    `npm install && npm run dev`, port 5173) — CLAUDE.md's own
    orchestration list already named it as part of the target stack.

## Phase 7 Pass 2a (Strategy Marketplace + Trade Journal UI) — new decisions

57. **Confirmed while scoping Pass 2 (before Pass 2a was approved): the
    Strategy Marketplace and Trade Journal screens needed zero new backend
    work** — every route (`GET/POST /api/v1/strategies`,
    `POST /{id}/backtest`, `POST /fuse`, `GET /{id}/export`,
    `GET/POST /api/v1/journal`) already existed and was complete from
    Phases 5-6. Only `frontend/` changed this pass. This is what
    distinguished Pass 2a from Pass 2b (watchlist/risk/alerts settings —
    still deferred, still needs real backend CRUD work first).
58. **`CumulativePnlChart` extracted from `EquityCurve`** (both under
    `frontend/src/components/`) — the backtest result view needed the same
    cumulative-P&L line chart Paper Trading already had, built from a
    different source (`trade_log` entries vs. closed `PaperTrade` rows).
    Rather than duplicate the Recharts wiring, `EquityCurve` now builds its
    points and delegates to the shared, source-agnostic chart component.
59. **"Log outcome" on the recommendation deep-dive routes to the Trade
    Journal screen with `recommendation_id` pre-filled** — matches
    `docs/ui_wireframes.md`'s own user flow #1 ("expand reasoning tree →
    execute manually → log the outcome later in the trade journal")
    exactly, rather than a floating unlinked journal form.
60. **Video-strategy submission's textarea placeholder explicitly says
    "paste the description/transcript yourself"** — reinforcing #37
    (Phase 5's decision that this app never downloads or transcribes video
    automatically) at the exact point a user might otherwise expect a URL
    alone to be enough.

## Phase 7 Pass 2b (Watchlist/Risk/Alerts Settings) — new decisions

Confirmed while scoping, then built exactly as proposed:

61. **VIX regime now reads the founder's `risk_settings` DB row in
    preference to `src/config.py`'s env-var defaults** — `risk_settings`
    existed in the schema since Phase 1 but had no ORM model, no route,
    and nothing read it; every VIX-regime call site used env defaults
    only. `compute_vix_regime` (`src/market_data/vix.py`) is now a pure
    function taking explicit thresholds; `src/db/risk_settings.py`
    resolves them (DB row if it exists, env fallback otherwise) and all
    three call sites (`/vix`, `/scan`, `/recommendations`) were updated.
    Migration `0006` seeds the founder's row with the exact values the env
    defaults already had, so this ships without silently reclassifying
    today's VIX regime.
62. **Strike-selection rule overrides were NOT built** — confirmed before
    starting: no table exists anywhere for this, and more importantly
    nothing in the confidence-scoring engine accepts per-user overrides at
    all yet (fixed constants). A settings screen for a knob the engine
    can't turn would be misleading, not useful.
63. **Alerts settings ships read-only** — confirmed before starting:
    Telegram/email config stays env-var-only (`.env`, read once at
    startup); the settings screen reports what's configured, it doesn't
    let you change it. Making it live-editable would need a real DB-backed
    config layer `src/alerts/*` reads from, and per-category alert toggles
    (also requested by the wireframe) don't exist anywhere either
    (`dispatch_alerts` always fires every channel) — both judged more
    architecture than a single founder occasionally editing `.env`
    justifies right now.
64. **`_get_founder` was duplicated identically in three route files**
    (strategies, journal, paper_trades) before this pass added a 4th call
    site (`src/db/risk_settings.py`) — extracted to `src/db/founder.py`,
    all four call sites now share one implementation.
65. **Two more real bugs caught by live/careful testing, not just green
    mocked tests:**
    - The `RiskSettings` model's own docstring, explaining the
      execution-mode safety rule, quoted `'live_algo'` as prose — which is
      the exact string pattern `tests/test_no_order_placement.py`'s
      structural audit scans for. A real false positive from writing
      *about* the forbidden term while explaining why it's forbidden;
      reworded to avoid the quoted-literal pattern without softening the
      rule itself.
    - `float(MagicMock())` silently returns `1.0` rather than raising —
      several tests with a fully-auto-mocked DB session were unknowingly
      resolving VIX thresholds as `(1.0, 1.0, 1.0)`, misclassifying every
      realistic VIX value as "extreme." One test (`test_scan.py`) happened
      to assert the regime and caught it; others (`test_recommendations_route.py`)
      didn't assert on it and passed anyway despite exercising nonsense
      values. Fixed by patching `get_vix_thresholds` at the consuming
      route module in every affected test file, rather than trying to mock
      the raw SQLAlchemy chain realistically.
    - Separately, a test-only bug (not a production bug): a fixture set
      `app.dependency_overrides[get_settings]` to a `**kwargs`-signature
      function directly — FastAPI introspects whatever callable sits in
      `dependency_overrides`, and misread the `**kwargs` as a required
      query parameter, breaking every route in that test file with a 422.
      Fixed by wrapping it in a zero-arg lambda, matching every other test
      file's established `_fake_settings()` convention.

## Explicitly not built (matches session's own phasing)

- Live order execution (see #1 — permanent, not phase-gated).
- The actual LSTM negation model, video-transcription pipeline execution,
  and trained pattern-weight learning loop are Phase 3+/4+ per the
  `buildspec.json` phasing — MVP ships their schemas, interfaces, and a
  heuristic fallback, not the trained models themselves.
- Kubernetes/cloud deploy — Docker Compose only, matching the session's
  "start with Docker Compose, K8s for production later."
