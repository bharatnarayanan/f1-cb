# Trading Intelligence Platform — Deployment Guide

## Current state of this scaffold

This directory is F1's reconstructed handoff artifact for the Trading
Intelligence Platform: `docs/buildspec.json` + `docs/CLAUDE.md` plus a
starter skeleton (`src/main.py`, `src/config.py`, `database/schema.sql`,
`docker-compose.yml`). The `worker` (pattern/negation/scoring pipeline) and
`frontend` services described in `docs/architecture.md` are not implemented
yet — that's CB's build phase, driven by `build_prompt` in
`docs/buildspec.json`.

**Read-only reminder**: nothing in this deployment ever configures a Kite
Connect credential with order-placement scope. Only read-only market-data
API access is required.

## Local development

1. Copy env template and fill in secrets:
   ```
   cp .env.example .env
   ```
   Required: `SECRET_KEY`, `KITE_API_KEY`, `KITE_ACCESS_TOKEN` (read-only
   scope). Optional: `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY` (rationale
   narration + Strategy Marketplace extraction).

2. Start TimescaleDB + Redis + API:
   ```
   docker compose up
   ```
   Postgres auto-applies `database/schema.sql` on first boot (via
   `docker-entrypoint-initdb.d`), which also enables the `timescaledb`
   extension and creates the continuous aggregates. API becomes available
   at `http://localhost:8000` — check `GET /health`.

3. To reset the database (schema changes during development):
   ```
   docker compose down -v   # drops the timescaledb_data volume
   docker compose up
   ```

## Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `SECRET_KEY` | yes | — | JWT signing secret. Generate with `openssl rand -hex 32`. |
| `DATABASE_URL` | yes (set by compose) | — | `postgresql+psycopg://user:pass@host:5432/db` |
| `REDIS_URL` | no | `redis://redis:6379/0` | Live tick cache, rate limiting, alert dedup. |
| `KITE_API_KEY` | yes | — | Zerodha Kite Connect app key. **Request read-only market-data scope only — never order-management scope.** |
| `KITE_ACCESS_TOKEN` | yes | — | Daily Kite Connect access token (regenerate per Zerodha's token lifecycle). |
| `TELEGRAM_BOT_TOKEN` | no | unset | For dispatching recommendation alerts. |
| `ANTHROPIC_API_KEY` | no | unset | Used only for rationale-tree narration and Strategy Marketplace logic extraction — see `docs/CLAUDE.md` §3. Without it, recommendations still compute scores but the reasoning tree falls back to the raw structured factors (no prose narration). |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | no | unset | Optional email alert channel. |
| `PATTERN_SCAN_INTERVAL_SECONDS` | no | `300` | Worker cadence for pattern/recommendation evaluation (matches 5m candle close). |

## Production deployment target

MVP target is a single managed container host (Render, Railway, Fly.io, or
a personal VPS) — not Kubernetes. Steps once the `worker` and `frontend`
exist:

1. Build and push the `api` and `worker` images (same Dockerfile, different
   `command`).
2. Provision a managed Postgres 15 instance with the TimescaleDB extension
   available; run `database/schema.sql` against it before first deploy.
3. Provision a managed Redis instance.
4. Set the environment variables above as platform secrets — never commit
   real values (`.env` is gitignored). **Double-check the Kite Connect app
   is registered with read-only scope before generating the access token.**
5. Point the `worker` service's scheduler at the same `DATABASE_URL` /
   `REDIS_URL` as `api` — they must share state.
6. Put the frontend static build behind the same domain (nginx or the
   platform's static hosting) with `/api/*` proxied to the `api` service.

## Compliance-relevant deployment notes

- No customer funds or third-party accounts ever transit this system — it
  is a single-founder (or small trusted circle in v1.1) decision-support
  tool. No payment/broker order credentials are ever added to this stack.
- If a Kite Connect app is ever re-registered with write/order scope for
  any reason, treat that as a stop-the-line event requiring a fresh review
  against `docs/CLAUDE.md` §2 before any code touches it.

## Verifying a deploy

- `GET /health` returns `{"status": "ok"}`.
- `docker compose logs timescaledb` shows `01-schema.sql` applied with no
  errors on a fresh volume, and the `timescaledb` extension is active.
- Once the worker exists: confirm a pattern detected on live data produces
  a recommendation with confidence/risk/conviction scores and a populated
  reasoning tree, and that a Telegram alert fires if configured (see the
  smoke flow in `docs/buildspec.json` → `build_prompt`).
- Confirm no order-placement Kite Connect calls exist anywhere in `src/`
  (`grep -ri "place_order\|modify_order\|cancel_order" src/` should return
  nothing).
