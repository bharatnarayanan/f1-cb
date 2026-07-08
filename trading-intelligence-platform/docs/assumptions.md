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

## Explicitly not built (matches session's own phasing)

- Live order execution (see #1 — permanent, not phase-gated).
- The actual LSTM negation model, video-transcription pipeline execution,
  and trained pattern-weight learning loop are Phase 3+/4+ per the
  `buildspec.json` phasing — MVP ships their schemas, interfaces, and a
  heuristic fallback, not the trained models themselves.
- Kubernetes/cloud deploy — Docker Compose only, matching the session's
  "start with Docker Compose, K8s for production later."
