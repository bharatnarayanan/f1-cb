# CLAUDE.md — Trading Intelligence Platform (TIP) Operating File

## 1. What This Is

TIP is a **personal decision-support tool** for NIFTY 50 / BANKNIFTY F&O day
trading. It ingests live/historical market data, detects multi-timeframe
candlestick patterns, predicts when those patterns will be negated, cross-
checks against heavyweight-constituent and sector behavior, and produces
scored, explained trade recommendations — the founder still places every
trade manually. Version: `1.0.0-mvp`.

This file governs how you (Claude) work on this repo. Read it fully before
writing code. When in doubt, prefer the constraints here over your own
defaults.

## 2. The One Thing You Must Never Forget

**This system NEVER places, modifies, or cancels a real order. There is no
order-placement code path in this codebase — not behind a flag, not as a
disabled stub, not as a "future" TODO.** Two execution modes exist:

- **Paper-trade**: simulated fills against real or historical data, for
  practicing a rule set risk-free.
- **Live-manual**: the system recommends; the founder executes the trade
  themselves, manually, in Zerodha's own app.

Concretely:

- **NEVER** call, wrap, or scaffold `place_order`, `modify_order`,
  `cancel_order`, or any Zerodha Kite Connect order-management endpoint.
- **NEVER** request or store a Kite Connect API key/access token with
  trading (order) scope — read-only market-data scope only.
- **NEVER** add a "live-algo" or "auto-execute" mode, even gated behind a
  setting a user could enable. If a future request asks for this, **stop
  and flag it** rather than implementing it — it needs an explicit,
  separate compliance decision that hasn't been made.
- **NEVER** frame a recommendation's UI copy as an instruction to execute
  ("Buy now") rather than as information ("Setup: NIFTY 21500 CE, entry
  ~245, confidence 78%"). This is a judgment/decision-support tool.

If a requested change threatens this boundary, **stop and flag it** rather
than implementing silently.

## 3. Security & Data Integrity Non-Negotiables

- Market data ingestion is **read-only**: historical candles, live quotes,
  WebSocket ticks, OI/Greeks, India VIX, index/constituent quotes via
  Zerodha Kite Connect. No write-scope Kite calls exist anywhere.
- **Never fire a recommendation on stale, missing, or partial data.** On a
  data-source outage: retry per policy, log the failure, and skip that
  evaluation cycle rather than emit a recommendation built on bad inputs. A
  missed setup is acceptable; a false one is not.
- The negation model, confidence score, risk score, and conviction score
  are all **deterministic computations over structured data** — the LLM
  (Claude) is used only to *narrate* the reasoning tree and to *extract*
  strategy logic from Strategy Marketplace submissions. It must never be
  the thing deciding a numeric score, an entry/exit price, or a strike.
- Passwords are bcrypt-hashed, never stored or logged in plaintext. JWTs
  signed with a secret from env/config, never hardcoded.
- The audit log (`audit_log`, `alerts_log`, `strategy_audit_log`) is
  append-only — no UPDATE/DELETE paths in application code.
- Never log secrets, API keys, or access tokens at info level.

## 4. Tech Stack (do not deviate without asking)

| Layer | Choice |
|---|---|
| Backend | Python 3.11 + FastAPI |
| DB | TimescaleDB (PostgreSQL 15 extension), SQLAlchemy + Alembic |
| Cache/coord | Redis |
| Pattern detection | TA-Lib + pandas-ta |
| Negation model | MVP: heuristic/statistical (avg candles-to-negate per pattern x timeframe x VIX regime). v1.1+: PyTorch LSTM — do not build this early; ship the heuristic first |
| Strategy Marketplace backtest | `vectorbt` — do NOT build a backtest engine from scratch |
| Market data | Zerodha Kite Connect, **read-only scope only** |
| LLM | Claude (Anthropic) — rationale narration + strategy-logic extraction ONLY, never numeric decisions |
| Frontend | React + TypeScript (Vite), Recharts |
| Auth | Email/password, JWT, bcrypt |
| Alerts | `python-telegram-bot`, SMTP email, in-app dashboard. Pine Script export for TradingView (no live push — no such public API exists) |
| Orchestration | Docker Compose: `api`, `worker`, `timescaledb`, `redis`, `frontend` |

## 5. Scope Discipline

### In scope (MVP) — build these

1. Multi-timeframe candlestick pattern detection across the watchlist
2. Candle-negation heuristic model + confidence/risk/conviction scoring
3. Support/resistance engine (multi-timeframe pivot + hit-frequency)
4. Heavyweight/sector correlation scoring
5. Intraday seasonality + impulse-move detection (fixed scan windows)
6. Four recommendation categories: Tactical, Impulse, Strategic, BTST
7. AI reasoning tree per recommendation
8. User-configurable strike-selection rules
9. Trade-journal feedback loop -> Bayesian weight-update job
10. Paper-trading simulator + explicit Paper/Live-manual switch
11. Strategy Marketplace: ingestion, extraction, independent backtest,
    fusion, Pine Script/Python export (seeded with the founder's BVWR rule)
12. Telegram + dashboard + email alerts
13. Risk guardrails (VIX regime thresholds, expiry dampening, liquidity flags)

### Explicitly OUT of scope — do NOT build (flag if asked)

- **Any order-placement path** (see §2 — permanent, not phase-gated)
- Real-money paper trading — all P&L in Paper mode is simulated
- Public multi-tenant SaaS: freemium tiers, billing, public signup
- Pushing alerts directly into a user's TradingView account
- A trained LSTM negation model before the heuristic ships and trade-journal
  data exists to train on
- Broker API key vault for anyone else's credentials (single founder
  account in MVP)

If a task drifts into v2/out-of-scope territory, say so and confirm before
proceeding.

## 6. Data Reliability Rules

- Normalize all timestamps to IST market hours; handle indicator lookback
  windows and NaN warm-up periods explicitly — don't score a pattern until
  enough bars exist.
- Zerodha Kite Connect is a third-party API — wrap it behind an
  abstraction (`src/market_data/`) so retries, rate-limit backoff, and any
  future secondary data source can be added without touching callers.
- Backtests (Strategy Marketplace) must document assumptions (slippage,
  commissions, no look-ahead bias). Don't present idealized fills as
  reality — this applies equally to the founder's own strategies and to
  ingested marketplace strategies.
- Every recommendation must carry BOTH a confidence score and a risk
  score — never present confidence alone as if risk were zero.

## 7. Data Model (core tables — audit everything)

See `database/schema.sql` for full DDL. Key tables:

- `candles` (hypertable) — OHLCV per symbol/timeframe
- `oi_snapshots` (hypertable) — OI/Greeks per symbol/strike/expiry
- `india_vix_snapshots` (hypertable)
- `patterns_detected`, `negation_predictions`, `sr_levels`
- `recommendations` — category, entry/exit/strike, confidence/risk/conviction, rationale (JSONB)
- `trade_journal` — feedback loop input
- `strategies`, `strategy_backtests`, `strategy_fusion` — Strategy Marketplace
- `paper_trades` — simulated fills only
- `alerts_log`, `audit_log` — append-only

## 8. Definition of Done

A change is done only when:

1. It satisfies the relevant acceptance criteria (see `docs/buildspec.json`
   → `acceptance_criteria`) with tests.
2. No order-placement code path was introduced (§2).
3. Confidence AND risk score are both present on any new recommendation
   surface.
4. Reasoning-tree data is populated for any new recommendation-producing
   logic — never a bare score with no explanation.
5. Audit records are written for any state-changing event (recommendation
   fired, backtest run, strategy change, trade-journal entry).
6. `docker compose up` still starts all five services and the dashboard is
   reachable.
7. New deps checked for license compatibility (see `docs/buildspec.json` →
   `references.similar_repos` for known-good licenses).

## 9. Working Style

- Prefer wrapping proven libraries (TA-Lib, pandas-ta, vectorbt) over
  reinventing pattern detection or backtesting math.
- Keep the Zerodha market-data layer behind an interface.
- Small, testable modules; the pattern engine, negation model, and
  confidence-scoring engine get the heaviest test coverage — they're the
  core value of the product.
- When you hit an open question (see `docs/assumptions.md`), the pragmatic
  MVP default has already been chosen and documented — don't re-derive it,
  but do flag if new information contradicts it.

## 10. Compliance Reminders

- This is a personal/decision-support tool, not a distributed advisory
  product — recommendations are informational, and the founder is the one
  executing every trade manually.
- Respect Zerodha Kite Connect's API terms of service (rate limits, no data
  redistribution beyond personal use).
- The append-only audit log exists for the founder's own record-keeping and
  post-mortem analysis, not as a regulatory requirement in v1 — keep it
  anyway, since every acceptance criterion depends on it being reliable.

---
*When a request conflicts with §2 (no order placement), §3 (security/data
integrity), or §5 (scope), stop and flag before implementing.*
