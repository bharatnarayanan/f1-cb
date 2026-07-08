# Trading Intelligence Platform (TIP)

A personal decision-support tool for NIFTY 50 / BANKNIFTY F&O day trading.
It ingests **read-only** Zerodha market data, detects multi-timeframe
candlestick patterns, predicts when those patterns will be negated,
cross-checks against heavyweight-constituent and sector behavior, and
produces scored, explained trade recommendations. Full scope, non-goals,
and rationale live in `docs/buildspec.json`; operating rules for anyone
(human or Claude Code) writing code here live in `docs/CLAUDE.md`.

> Read-only market data. No order placement. No real-money execution path
> exists in this system — recommendations are informational; every trade
> is placed manually by the founder in their own Zerodha app.

## What this is

This is the handoff artifact produced by an F1 (idea refinery) Discovery +
Prompt Architect session (`docs/f1_session_output.md`), reconstructed into
a full spec package plus a starter code skeleton. It is the input to CB
(Core Builder), not a finished product — see "Status" below. Where the
session left details unresolved, `docs/assumptions.md` lists every
technical decision made to fill the gap, for founder review.

## Project structure

```
docs/
  f1_session_output.md    # the raw F1 session transcript this spec is derived from
  assumptions.md            # every gap-filling decision made, for founder review
  buildspec.json             # the F1 -> CB contract: problem, solution, tech, UI, acceptance criteria, build_prompt
  CLAUDE.md                   # operating file: hard boundaries (no order placement), fixed stack, conventions
  architecture.md               # system design + component responsibilities
  deployment_guide.md             # local dev + production deployment steps
  api_routes.md                    # REST API surface (40+ routes)
  ui_wireframes.md                  # key screens + user flows (ASCII wireframes)
  strategy_schema.json               # JSON Schema for the Strategy Marketplace's canonical rule format
database/
  schema.sql                          # canonical TimescaleDB/PostgreSQL schema
src/
  main.py                              # FastAPI entrypoint (API service)
  config.py                             # environment-driven settings
docker-compose.yml                       # api + timescaledb + redis for local dev
CLAUDE.md                                 # copy of docs/CLAUDE.md at project root, for tools that read it there
```

## Status

Implemented: `docs/*`, `database/schema.sql`, `src/main.py` + `src/config.py`
(a running `/health` endpoint), `docker-compose.yml` for local TimescaleDB +
Redis + API.

Not yet implemented (see `docs/buildspec.json` → `build_prompt` for the
full scope): the pattern-detection/negation/scoring pipeline (the
`worker` service), the Strategy Marketplace ingestion/backtest pipeline,
all business routes in `docs/api_routes.md`, and the frontend. This is
expected — CB (Phase 3+ of the F1/CB pipeline) is what turns this spec into
that code.

## Quickstart

```
docker compose up
curl http://localhost:8000/health
```

See `docs/deployment_guide.md` for environment variables (including
read-only Zerodha Kite Connect credentials) and production deployment
notes.

## Key constraints (read before extending)

- **No order-placement code path exists anywhere in this repo, and none
  should ever be added without a separate, explicit compliance decision.**
  See `docs/CLAUDE.md` §2. Execution modes are `paper` (simulated) and
  `live_manual` (recommend only) — there is no `live_algo` mode.
- Fixed stack: Python 3.11 + FastAPI, TimescaleDB (PostgreSQL 15), Redis,
  React/Vite frontend, TA-Lib + pandas-ta for patterns, `vectorbt` for
  Strategy Marketplace backtests, Claude for rationale narration and
  strategy-logic extraction only (never numeric decisions). Do not
  substitute libraries — see `docs/CLAUDE.md` §4.
- Every recommendation, backtest run, and trade-journal entry writes an
  immutable audit row (`database/schema.sql`: `recommendations`,
  `strategy_backtests`, `trade_journal`, `alerts_log`, `audit_log`).
