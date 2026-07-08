# Trading Intelligence Platform — API Routes

Base URL: `/api/v1`. All routes except `/auth/*` require
`Authorization: Bearer <JWT>`. **No route in this API places, modifies, or
cancels a real order — see `docs/CLAUDE.md` §2.** Market-data routes are
read proxies over data the worker already ingested (or, for on-demand
quotes, a live read-only Kite Connect call) — never a write to the broker.

## Auth

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account (founder + optional trusted co-traders in v1.1). |
| POST | `/auth/login` | Exchange credentials for a JWT. |
| POST | `/auth/logout` | Invalidate refresh token. |
| GET | `/auth/me` | Current user profile. |

## Market data (read-only)

| Method | Path | Description |
|---|---|---|
| GET | `/market/candles` | Query params: `symbol`, `timeframe`, `from`, `to`. Returns OHLCV from TimescaleDB (base table or continuous aggregate). |
| GET | `/market/quote/{symbol}` | Latest live quote (on-demand read-only Kite Connect call, cached in Redis). |
| GET | `/market/oi` | Query params: `symbol`, `expiry`. Latest OI/Greeks snapshot per strike. |
| GET | `/market/vix` | Latest India VIX value + current regime (`normal`/`elevated`/`high`/`extreme`). |
| GET | `/market/watchlist` | Configured heavyweight constituents + sector indices. |
| PUT | `/market/watchlist` | Update the watchlist (symbols, weights, active flags). |

## Patterns & levels

| Method | Path | Description |
|---|---|---|
| GET | `/patterns` | Filterable by `symbol`, `timeframe`, `from`/`to`. Recently detected candlestick patterns. |
| GET | `/patterns/{id}/negation` | Negation prediction for a specific detected pattern (predicted window, model version, actual outcome once observed). |
| GET | `/levels/sr` | Filterable by `symbol`, `timeframe`. Current support/resistance levels with hit count + confluence score. |

## Recommendations

| Method | Path | Description |
|---|---|---|
| GET | `/recommendations` | Filterable by `category` (`tactical`\|`impulse`\|`strategic`\|`btst`), `forecast_horizon`, `symbol`, `status`, `date`. The dashboard's main feed. |
| GET | `/recommendations/{id}` | Full recommendation detail including entry/exit/strike and scores. |
| GET | `/recommendations/{id}/rationale` | The full collapsible reasoning tree (structured JSON: macro bias → pattern → negation prediction → heavyweight confirmation → OI → seasonality → final score), Claude-narrated. |
| POST | `/recommendations/{id}/dismiss` | Mark a recommendation as not-of-interest (does not delete — audit trail preserved). |

## Strike selection rules (user-configurable overrides)

| Method | Path | Description |
|---|---|---|
| GET | `/strike-rules` | Current user's strike-selection rule overrides (RSI thresholds, candle-type filters, OI-accumulation thresholds, IV rank). |
| PUT | `/strike-rules` | Update strike-selection rule overrides. |

## Trade journal (feedback loop)

| Method | Path | Description |
|---|---|---|
| GET | `/journal` | List trade-journal entries, filterable by date/outcome/recommendation. |
| POST | `/journal` | Log an outcome against a recommendation. Body: `{ recommendation_id, outcome, realized_pnl_pct, observation }`. Feeds the nightly weight-update job. |
| GET | `/journal/{id}` | Fetch one journal entry. |

## Paper trading

| Method | Path | Description |
|---|---|---|
| GET | `/paper-trades` | List simulated positions (open + closed) for the current user. |
| GET | `/paper-trades/{id}` | Detail of one simulated position, including simulated P&L. |
| POST | `/execution-mode` | Switch between `paper` and `live_manual`. **There is no `live_algo` value — it does not exist as an option.** |
| GET | `/execution-mode` | Current mode for the user. |

## Strategy Marketplace

| Method | Path | Description |
|---|---|---|
| GET | `/strategies` | List strategies (marketplace + the seeded BVWR founder strategy), filterable by `status`, `source_type`. |
| POST | `/strategies` | Submit a new strategy. Body: `{ name, source_type, source_ref?, raw_input? }`. Triggers the Strategy Agent extraction pipeline asynchronously. |
| GET | `/strategies/{id}` | Fetch one strategy, including `canonical_logic` once extracted. |
| PATCH | `/strategies/{id}` | Edit a strategy's canonical logic manually (e.g. correcting a mis-extraction). Appends to `strategy_audit_log`. |
| DELETE | `/strategies/{id}` | Soft-delete/archive a strategy. |
| POST | `/strategies/{id}/backtest` | Run the independent `vectorbt` backtest over a given date range. Always writes a `strategy_backtests` row. |
| GET | `/strategies/{id}/backtests` | List past backtest runs for a strategy. |
| GET | `/strategies/backtests/{run_id}` | Fetch one stored backtest result. |
| POST | `/strategies/fuse` | Body: `{ strategy_ids: [id1, id2], conflict_resolution_notes }`. Creates a fused strategy and independently re-backtests it before marking it usable. |
| GET | `/strategies/{id}/export/pine` | Export the strategy's canonical logic as a Pine Script (for the user to run in their own TradingView account — no live push exists). |
| GET | `/strategies/{id}/export/python` | Export the strategy as a standalone Python backtest function. |

## Alerts

| Method | Path | Description |
|---|---|---|
| GET | `/alerts/settings` | Current Telegram bot linkage, email destination, per-category on/off flags. |
| PUT | `/alerts/settings` | Update alert settings. |
| GET | `/alerts/log` | Dispatch history (`alerts_log`) — channel, status, timestamp per recommendation. |

## Risk guardrails

| Method | Path | Description |
|---|---|---|
| GET | `/risk-settings` | Current user's VIX regime thresholds, expiry-day dampening flag, max daily recommendations. |
| PUT | `/risk-settings` | Update risk guardrail configuration. |

## Dashboard

| Method | Path | Description |
|---|---|---|
| GET | `/dashboard/summary` | Recommendation counts by category, current VIX regime, open paper-trade count, aggregate simulated P&L — the single call the dashboard home screen uses. |

## Seasonality windows

| Method | Path | Description |
|---|---|---|
| GET | `/seasonality-windows` | List configured intraday scan windows. |
| PUT | `/seasonality-windows` | Add/edit/disable scan windows. |

## System

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check (API + DB + Redis connectivity). |
| GET | `/audit-log` | Query the append-only audit log, filterable by `event_type`, date range (founder's own record-keeping). |

## Error shape

```json
{
  "detail": "human-readable message",
  "code": "validation_error | data_source_unavailable | strategy_extraction_failed | tier_limit_exceeded | ..."
}
```

## Rate limiting

Per-user rate limits enforced via Redis on `/strategies/{id}/backtest`,
`/strategies/fuse`, and `/strategies` writes, to bound compute cost from
repeated backtesting. On-demand `/market/quote/{symbol}` calls are also
rate-limited to stay within Zerodha Kite Connect's API usage policy.
