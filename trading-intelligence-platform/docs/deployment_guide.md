# Trading Intelligence Platform — Deployment Guide

## Current state

All 8 build phases (Foundation through Production Hardening) are complete,
plus a follow-on pass that added the scheduled `worker` service.
`docker compose up` starts eight services — `api`, `worker`, `timescaledb`,
`redis`, `frontend`, `prometheus`, and `grafana`. `worker` and `api`'s
on-demand `POST /api/v1/recommendations/{symbol}` route share one
implementation (`src/recommendation_pipeline.py`) — `worker` just calls it
on a timer across the whole active watchlist instead of one symbol per
manual request, and additionally dedupes by newest-scanned-bar
(`src/worker/dedup.py`) so it doesn't re-persist a decision about the same
closed candle every tick. `POST /api/v1/scan/*` is still a separate,
narrower on-demand endpoint (pattern/negation/S-R only, no scoring or
alerting) — useful for manually inspecting one symbol without triggering a
full recommendation.

**Read-only reminder**: nothing in this deployment ever configures a Kite
Connect credential with order-placement scope, and no code path anywhere in
`src/` places, modifies, or cancels an order. See `docs/CLAUDE.md` §2.

## Local development

1. Copy the env template and fill in secrets:
   ```
   cp .env.example .env
   ```
   The only two variables you truly need to get started are `SECRET_KEY`
   (`openssl rand -hex 32`) and `DATABASE_URL` (compose sets this for you
   automatically inside containers — you only need it in `.env` for running
   scripts/tests on the host outside Docker). Everything else is optional
   and defaults sanely; see the environment variable table below.

2. Start the full stack:
   ```
   docker compose up
   ```
   - `api` — `http://localhost:8000`. On startup it runs `alembic upgrade
     head` (schema is Alembic-owned — see "Database schema" below), then
     starts uvicorn with `--reload`.
   - `worker` — no exposed HTTP API. Long-running process (`src/worker/main.py`)
     that wakes every `PATTERN_SCAN_INTERVAL_SECONDS` (default 300s),
     scans the active watchlist during real NSE market hours (Mon-Fri
     09:15-15:30 IST — see "Worker service" below), and creates
     recommendations the same way the on-demand route does. Reuses the
     `api` image (`image: trading-intelligence-platform-api:latest` in
     `docker-compose.yml`) rather than its own `build:` — see that file's
     comment if you ever need to know why.
   - `frontend` — `http://localhost:5173`. Vite dev server, hot-reloads on
     changes under `frontend/`.
   - `timescaledb` — `localhost:5432` (user/pass/db all `tip`).
   - `redis` — `localhost:6379`. Also backs the worker's scan dedup
     (`src/worker/dedup.py`).
   - `prometheus` — `http://localhost:9090`. Scrapes both `api:8000/metrics`
     and `worker:9100/metrics` every 15s — see "Worker service" below for
     why the worker needs its own scrape target.
   - `grafana` — `http://localhost:3001`. Login `admin` / `admin` (local-only
     deployment, not exposed publicly — change it if that ever changes). The
     Prometheus datasource and a starter "TIP — API Overview" dashboard are
     auto-provisioned; no manual setup needed.

3. Confirm it's healthy:
   ```
   curl http://localhost:8000/health
   ```
   Should return `{"status": "ok", "database": "ok", "redis": "ok", ...}`.

4. To reset the database entirely (rare — normally use a migration instead):
   ```
   docker compose down -v   # drops timescaledb_data (and prometheus_data/grafana_data)
   docker compose up
   ```

## Database schema — Alembic-owned

`database/schema.sql` is a hand-kept **reference** mirror of the full
current schema, useful for reading, but only `alembic/versions/0001_*.py`
executes it verbatim, against an empty database, as a frozen historical
snapshot — it is never edited again once applied anywhere real. Every
schema change since is its own incremental migration
(`alembic/versions/0002_*.py` … `0007_*.py` and up).

- Apply pending migrations (the `api` service already does this
  automatically on every start):
  ```
  docker compose exec api alembic upgrade head
  ```
- After changing `src/db/models.py`, generate a new migration rather than
  hand-editing an already-applied one:
  ```
  docker compose exec api alembic revision -m "describe the change"
  ```
  then fill in `upgrade()`/`downgrade()` by hand (autogenerate is not
  configured) and mirror the change into `database/schema.sql` so it stays
  an accurate full-state reference.
- Roll back one migration: `docker compose exec api alembic downgrade -1`.

## Sample data vs. live market data

`DATA_MODE` (default `sample`) controls which `MarketDataClient`
implementation `src/market_data/factory.py` wires up:

- **`sample`** (default): `SampleMarketDataClient` generates deterministic-
  ish random-walk candles in-process — no network calls, no Zerodha
  credentials needed. This is what every phase of this project has been
  built and tested against locally.
- **`live`**: real Zerodha Kite Connect calls via `kiteconnect`. Requires
  `KITE_API_KEY`, `KITE_API_SECRET`, and a same-day `KITE_ACCESS_TOKEN`
  (Kite tokens expire daily — there's no way around this, it's how the API
  works). Run the login helper each morning before switching to live mode:
  ```
  python3 scripts/kite_daily_login.py
  ```
  It walks you through the Zerodha login flow in your browser, exchanges
  the resulting `request_token` for today's `access_token`, writes it into
  `.env`, and confirms it works with a single read-only quote lookup. It
  never prints or logs your `api_secret` or `access_token`. Verify
  connectivity any time with `python3 scripts/test_kite_connection.py`.

  **Only ever register the Kite Connect app with read-only market-data
  scope.** If it's ever re-registered with order/write scope for any
  reason, treat that as a stop-the-line event — see `docs/CLAUDE.md` §2.

## Worker service

`worker` replaces manually curling `POST /api/v1/recommendations/{symbol}`
with an automatic scan across the whole active watchlist.

- **Schedule**: wakes every `PATTERN_SCAN_INTERVAL_SECONDS` (default 300s
  — matches a 5-minute candle close). No APScheduler or cron — a plain
  loop, since a bare `while True: sleep(...)` is enough at this scale.
- **Market-hours gate** (`src/worker/market_hours.py`): only scans Mon-Fri
  09:15-15:30 IST. Outside that window it just sleeps and logs nothing —
  check `docker compose logs worker` for a `cycle start` line to confirm
  it's actually scanning versus correctly idle. **No NSE holiday
  calendar** — a holiday still passes this check. In `sample` mode that's
  harmless; in `live` mode a closed-market Kite response just returns too
  few candles, which the existing `MIN_CANDLES_FOR_RECOMMENDATION` guard
  already rejects (no bad recommendation gets created, just a wasted API
  call — see `docs/assumptions.md`).
- **Scope per cycle**: every active watchlist constituent + sector index
  (same set the Settings screen toggles), across all 4 supported
  timeframes (`15m`/`30m`/`1h`/`2h`).
- **Dedup**: Redis-backed (`src/worker/dedup.py`) — a bar already
  evaluated isn't re-evaluated on the next tick. Inspect keys directly if
  you need to debug it:
  ```
  docker compose exec redis redis-cli --scan --pattern "worker:last_scanned:*"
  ```
- **Resilience**: one symbol/timeframe failing (bad data, a DB hiccup)
  is logged and skipped — it never aborts the rest of that cycle's
  watchlist, and a whole-cycle failure never kills the process, just
  waits for the next interval.
- **Manually triggering a cycle outside market hours** (useful for local
  testing): `docker compose exec` starts a *separate* process from the
  worker's own main loop, so this only exercises the DB/Redis/alerts side
  — it won't show up on the worker's own `:9100/metrics` (see below).
  ```
  docker compose exec worker python3 -c "from src.worker.main import run_one_cycle; run_one_cycle()"
  ```
- **Metrics**: the worker is a separate OS process from `api`, and
  `prometheus_client` keeps one in-memory registry per process — even
  though both import the same `Counter`/`Histogram` objects from
  `src/metrics.py`, the worker's increments never reach `api:8000/metrics`.
  It runs its own exporter on port `9100`
  (`prometheus_client.start_http_server` in `src/worker/main.py`), scraped
  as the separate `tip-worker` Prometheus target. Check
  `http://localhost:9090/targets` to confirm both `tip-api` and
  `tip-worker` report `UP`.

## Single-founder auth model

There is no login/JWT system in this codebase — deliberately deferred (see
`docs/assumptions.md`). Every route resolves a single seeded founder user
(`src/db/founder.py`, fixed UUID, seeded by migration `0004`). `SECRET_KEY`
is still required by `src/config.py` (JWT infra exists at the config layer
for when auth is eventually added) but nothing currently signs a token with
it. This is fine for the personal, single-founder scope this tool is built
for (`docs/CLAUDE.md` §10) — it is not a multi-tenant product.

## Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `ENVIRONMENT` | no | `development` | |
| `SECRET_KEY` | yes | — | Generate with `openssl rand -hex 32`. Not currently used to sign anything live (no auth routes exist yet), but required by config validation. |
| `DATABASE_URL` | yes (set by compose for the `api` container) | — | `postgresql+psycopg://tip:tip@timescaledb:5432/tip` inside Docker. |
| `REDIS_URL` | no | `redis://redis:6379/0` | Live tick cache, quote/VIX caching. |
| `DATA_MODE` | no | `sample` | `sample` (default, no credentials needed) or `live` (real Kite Connect). |
| `KITE_API_KEY` / `KITE_API_SECRET` / `KITE_ACCESS_TOKEN` | only if `DATA_MODE=live` | unset | Read-only market-data scope only. See "Sample data vs. live market data" above. |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | no | unset | Recommendation alert channel. Message `@userinfobot` on Telegram to find your chat id. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `ALERT_EMAIL_TO` | no | unset (`SMTP_PORT` defaults `587`) | Optional email alert channel. |
| `ANTHROPIC_API_KEY` | no | unset | Rationale-tree narration + Strategy Marketplace logic extraction ONLY — never a numeric decision (`docs/CLAUDE.md` §3). Without it, `/api/v1/recommendations/*` still computes every score correctly; the `rationale.narrative` field just reads "Narration unavailable — ANTHROPIC_API_KEY not configured." instead of prose. |
| `PATTERN_SCAN_INTERVAL_SECONDS` | no | `300` | Reserved for the future scheduled `worker` service; unused by the current on-demand routes. |
| `VIX_NORMAL_MAX` / `VIX_ELEVATED_MAX` / `VIX_HIGH_MAX` | no | `15.0` / `20.0` / `30.0` | Fallback only — the founder's `risk_settings` DB row (editable via the Settings screen or `PUT /api/v1/settings/risk`) takes precedence once seeded (migration `0006`). |

Risk guardrails beyond VIX thresholds (`suppress_tactical_on_extreme`,
`expiry_day_dampening`, `expiry_weekday`, `max_daily_recommendations`,
`execution_mode`) live entirely in the `risk_settings` DB row, not env
vars — edit them via the Settings screen or `PUT /api/v1/settings/risk`.

## Monitoring

- `GET /metrics` on the `api` service exposes Prometheus-format counters
  and histograms (`src/metrics.py`): HTTP request rate/latency by route,
  recommendations created (by category) and suppressed (by guardrail
  reason — `tactical_extreme_vix` or `daily_cap`), alerts dispatched (by
  channel/status), backtests run, and API errors (by error code).
- Prometheus (`http://localhost:9090`) scrapes it every 15s — check
  **Status → Targets** to confirm `tip-api` reads `UP`.
- Grafana (`http://localhost:3001`, `admin`/`admin`) has the datasource and
  the `TIP — API Overview` dashboard pre-loaded — no manual setup. Both are
  defined as code under `monitoring/` (`prometheus.yml`,
  `grafana/provisioning/`, `grafana/dashboards/tip-overview.json`), so a
  fresh `docker compose up` reproduces the same dashboard every time.
- Both services are local-only, unauthenticated beyond Grafana's default
  login, and never exposed publicly — this is a single-founder local
  deployment, not a hosted product (`docs/CLAUDE.md` §10).

## Running tests

```
docker compose exec api pytest -q
```
All tests run against fakes (mocked DB session, `fakeredis`, mocked market
client) — no live Postgres/Redis/Zerodha connection is required for the
suite itself, only for the container it runs inside. Every phase of this
build additionally required live `curl`-based verification against the
real running stack before being considered done — mocked-green tests alone
have caught real bugs but also missed several (see `docs/assumptions.md`'s
per-phase "bugs caught by live testing" entries); don't treat a green
`pytest` run alone as sufficient sign-off for a change to a scoring, alert,
or guardrail code path.

## Production deployment target

MVP target is a single managed container host (Render, Railway, Fly.io, or
a personal VPS) — not Kubernetes, not a multi-region setup. This is a
personal decision-support tool for one founder.

1. Build and push the `api`, `worker`, and `frontend` images. `api` and
   `worker` share the same `Dockerfile` and image — locally they reuse one
   built image (see "Worker service" above); in production, build it once
   and run it as two separate services/processes with different start
   commands (`uvicorn ...` vs `python -m src.worker.main`). `frontend/`
   needs its own build — `npm run build` then serve the `dist/` output,
   e.g. via nginx.
2. Provision a managed Postgres 15 instance with the TimescaleDB extension
   available. Point `DATABASE_URL` at it and run `alembic upgrade head`
   once before first traffic — don't rely on the `api` container's
   startup command doing it unattended in production without watching the
   first run.
3. Provision a managed Redis instance; point `REDIS_URL` at it.
4. Set the environment variables from the table above as platform secrets
   — never commit real values (`.env` is gitignored). Double-check the
   Kite Connect app is registered with read-only scope before generating
   any access token.
5. If you stand up Prometheus/Grafana in production, put them behind
   platform-level auth or a private network — the local `admin`/`admin`
   default is only safe because `docker-compose.yml` never exposes port
   `3001`/`9090` beyond localhost.
6. Put the frontend static build behind the same domain (nginx or the
   platform's static hosting) with `/api/*` proxied to the `api` service,
   and update the CORS `allow_origins` list in `src/main.py` from
   `http://localhost:5173` to the real frontend origin.

## Compliance-relevant deployment notes

- No customer funds or third-party accounts ever transit this system — it
  is a single-founder decision-support tool. No payment or broker
  order-placement credentials are ever added to this stack, in any
  environment.
- If a Kite Connect app is ever re-registered with write/order scope for
  any reason, treat that as a stop-the-line event requiring a fresh review
  against `docs/CLAUDE.md` §2 before any code touches it.
- The `execution_mode` risk setting is validated server-side
  (`src/routes/settings.py`) against exactly `"paper"`/`"live_manual"` — no
  third "auto-execute" value is ever accepted, on top of the DB enum
  constraint.

## Verifying a deploy

- `GET /health` returns `{"status": "ok", "database": "ok", "redis": "ok", ...}`.
- `GET /metrics` returns Prometheus text format with at least the
  `python_info` and `tip_http_requests_total` series present.
- `docker compose exec api alembic current` shows the latest revision
  applied with no pending migrations (`alembic history` to see them all).
- Fire a real recommendation end to end:
  ```
  curl -X POST "http://localhost:8000/api/v1/recommendations/RELIANCE?exchange=NSE&timeframe=15m"
  ```
  Confirm the response has both `confidence_score` and `risk_score`
  populated (never one without the other — `docs/CLAUDE.md` §6), a
  populated `rationale` reasoning tree, and that `alerts_log` rows were
  written for every channel (`dashboard` always shows `sent`; `telegram`/
  `email` show `sent` only if configured, `failed` otherwise — never
  faked).
- Confirm the worker is alive and correctly gated:
  `docker compose logs worker` should show `worker starting,
  scan_interval_seconds=...`. During real market hours it should show
  `cycle start` / `cycle complete` lines every interval; outside market
  hours it should show neither (silently idle, not crashed — check
  `docker compose ps worker` shows `Up` if the log is quiet and you're
  unsure). `http://localhost:9090/targets` should show both `tip-api` and
  `tip-worker` as `UP`.
- Confirm no order-placement Kite Connect calls exist anywhere in `src/`:
  ```
  docker compose exec api pytest tests/test_no_order_placement.py -q
  ```
  This runs a structural regex audit for actual calls/defs
  (`.place_order(`, `def place_order`, etc.) — comments and docstrings that
  legitimately explain the prohibition (e.g. this very file, or
  `src/market_data/base.py`'s docstring) are expected to mention the words
  and won't trip it; a plain `grep -ri "place_order" src/` will show those
  and isn't a reliable pass/fail check on its own.
