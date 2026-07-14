-- Trading Intelligence Platform — TimescaleDB schema (PostgreSQL 15 + TimescaleDB extension)
-- Mirrors docs/buildspec.json -> tech.database and docs/architecture.md.
--
-- Reference only past migration 0001: this file documents the CURRENT full
-- desired schema, hand-kept in sync with every migration, but only
-- alembic/versions/0001_initial_schema.py executes it verbatim (against a
-- truly fresh database). Every migration after 0001 carries its own DDL —
-- see alembic/versions/0002_multi_timeframe_aggregates.py's docstring for
-- why 0001 itself must not be edited again once applied.
--
-- READ-ONLY MARKET DATA BOUNDARY: nothing in this schema models an order,
-- a fill against a real broker, or a funded position. `paper_trades` is
-- explicitly simulated only. See docs/CLAUDE.md section 2.

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TYPE recommendation_category AS ENUM ('tactical', 'impulse', 'strategic', 'btst');
CREATE TYPE recommendation_action AS ENUM ('BUY_CE', 'BUY_PE', 'SELL_CE', 'SELL_PE', 'NO_TRADE');
CREATE TYPE execution_mode AS ENUM ('paper', 'live_manual');
CREATE TYPE dispatch_status AS ENUM ('pending', 'sent', 'failed');
CREATE TYPE vix_regime AS ENUM ('normal', 'elevated', 'high', 'extreme');
CREATE TYPE strategy_source_type AS ENUM ('video', 'text', 'pseudocode', 'pine_script', 'user_rule');
CREATE TYPE strategy_status AS ENUM ('ingested', 'extracted', 'backtested', 'usable', 'rejected');

CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               TEXT NOT NULL UNIQUE,
    hashed_password     TEXT NOT NULL,
    display_name        TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-user risk guardrail configuration (docs/assumptions.md #7).
CREATE TABLE risk_settings (
    user_id                     UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    vix_normal_max              NUMERIC(5, 2) NOT NULL DEFAULT 15.00,
    vix_elevated_max            NUMERIC(5, 2) NOT NULL DEFAULT 20.00,
    vix_high_max                NUMERIC(5, 2) NOT NULL DEFAULT 30.00,
    suppress_tactical_on_extreme BOOLEAN NOT NULL DEFAULT TRUE,
    expiry_day_dampening        BOOLEAN NOT NULL DEFAULT TRUE,
    -- Founder-editable, not a hardcoded fact — NSE's weekly expiry weekday
    -- has changed before. 1 = Tuesday (Python date.weekday(): Mon=0..Sun=6).
    -- Added in migration 0007 (Phase 8).
    expiry_weekday               INTEGER NOT NULL DEFAULT 1,
    max_daily_recommendations   INTEGER NOT NULL DEFAULT 20,
    execution_mode              execution_mode NOT NULL DEFAULT 'paper',
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Configurable heavyweight/sector watchlist (docs/assumptions.md #6).
CREATE TABLE watchlist_constituents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol              TEXT NOT NULL UNIQUE,
    display_name        TEXT NOT NULL,
    index_weight_pct    NUMERIC(5, 2),
    sector              TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE sector_indices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol              TEXT NOT NULL UNIQUE,      -- e.g. NIFTY BANK, NIFTY IT
    display_name        TEXT NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

-- Fixed (but editable) intraday seasonality scan windows (docs/assumptions.md #9).
CREATE TABLE seasonality_windows (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label               TEXT NOT NULL,             -- e.g. "EU open proxy"
    window_start        TIME NOT NULL,
    window_end          TIME NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO seasonality_windows (label, window_start, window_end) VALUES
    ('10:00 scan',        '10:00', '10:15'),
    ('11:00 scan',        '11:00', '11:15'),
    ('EU open proxy',     '12:30', '12:45'),
    ('13:30 scan',        '13:30', '13:45'),
    ('14:00 scan',        '14:00', '14:15'),
    ('Accumulation scan', '14:30', '15:00');

-- ── Time-series hypertables ─────────────────────────────────────────────

-- Base OHLCV candles (5m primary ingestion granularity). Higher timeframes
-- (10m/15m/30m/1h/2h/3h/1d) are TimescaleDB continuous aggregates over this
-- table, not separately-written rows.
CREATE TABLE candles (
    symbol              TEXT NOT NULL,
    timeframe           TEXT NOT NULL DEFAULT '5m',
    ts                  TIMESTAMPTZ NOT NULL,
    open                NUMERIC(12, 2) NOT NULL,
    high                NUMERIC(12, 2) NOT NULL,
    low                 NUMERIC(12, 2) NOT NULL,
    close               NUMERIC(12, 2) NOT NULL,
    volume              BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, timeframe, ts)
);
SELECT create_hypertable('candles', 'ts', if_not_exists => TRUE);
CREATE INDEX idx_candles_symbol_ts ON candles (symbol, ts DESC);

-- WITH NO DATA: TimescaleDB refuses an initial WITH DATA materialization
-- inside a transaction block (which Alembic always runs migrations in), and
-- there's no candle data to backfill yet anyway. The worker pipeline
-- (later phase) adds a refresh policy once ingestion is live.
CREATE MATERIALIZED VIEW candles_15m
WITH (timescaledb.continuous) AS
SELECT symbol,
       time_bucket('15 minutes', ts) AS bucket,
       first(open, ts)  AS open,
       max(high)        AS high,
       min(low)         AS low,
       last(close, ts)  AS close,
       sum(volume)      AS volume
FROM candles
WHERE timeframe = '5m'
GROUP BY symbol, bucket
WITH NO DATA;

CREATE MATERIALIZED VIEW candles_1h
WITH (timescaledb.continuous) AS
SELECT symbol,
       time_bucket('1 hour', ts) AS bucket,
       first(open, ts)  AS open,
       max(high)        AS high,
       min(low)         AS low,
       last(close, ts)  AS close,
       sum(volume)      AS volume
FROM candles
WHERE timeframe = '5m'
GROUP BY symbol, bucket
WITH NO DATA;

-- 10m/30m/2h/3h added in migration 0002 (F3.3, multi-timeframe aggregation)
-- — same shape as candles_15m/candles_1h above.
CREATE MATERIALIZED VIEW candles_10m
WITH (timescaledb.continuous) AS
SELECT symbol,
       time_bucket('10 minutes', ts) AS bucket,
       first(open, ts)  AS open,
       max(high)        AS high,
       min(low)         AS low,
       last(close, ts)  AS close,
       sum(volume)      AS volume
FROM candles
WHERE timeframe = '5m'
GROUP BY symbol, bucket
WITH NO DATA;

CREATE MATERIALIZED VIEW candles_30m
WITH (timescaledb.continuous) AS
SELECT symbol,
       time_bucket('30 minutes', ts) AS bucket,
       first(open, ts)  AS open,
       max(high)        AS high,
       min(low)         AS low,
       last(close, ts)  AS close,
       sum(volume)      AS volume
FROM candles
WHERE timeframe = '5m'
GROUP BY symbol, bucket
WITH NO DATA;

CREATE MATERIALIZED VIEW candles_2h
WITH (timescaledb.continuous) AS
SELECT symbol,
       time_bucket('2 hours', ts) AS bucket,
       first(open, ts)  AS open,
       max(high)        AS high,
       min(low)         AS low,
       last(close, ts)  AS close,
       sum(volume)      AS volume
FROM candles
WHERE timeframe = '5m'
GROUP BY symbol, bucket
WITH NO DATA;

CREATE MATERIALIZED VIEW candles_3h
WITH (timescaledb.continuous) AS
SELECT symbol,
       time_bucket('3 hours', ts) AS bucket,
       first(open, ts)  AS open,
       max(high)        AS high,
       min(low)         AS low,
       last(close, ts)  AS close,
       sum(volume)      AS volume
FROM candles
WHERE timeframe = '5m'
GROUP BY symbol, bucket
WITH NO DATA;

-- Refresh policies (all six views) — applied by migration 0002, not by
-- this file (add_continuous_aggregate_policy isn't idempotent-safe to
-- re-run, so it's not part of the fresh-install path 0001 executes).
-- SELECT add_continuous_aggregate_policy('candles_10m', start_offset => INTERVAL '1 day',   end_offset => INTERVAL '10 minutes', schedule_interval => INTERVAL '10 minutes');
-- SELECT add_continuous_aggregate_policy('candles_15m', start_offset => INTERVAL '1 day',   end_offset => INTERVAL '15 minutes', schedule_interval => INTERVAL '15 minutes');
-- SELECT add_continuous_aggregate_policy('candles_30m', start_offset => INTERVAL '2 days',  end_offset => INTERVAL '30 minutes', schedule_interval => INTERVAL '30 minutes');
-- SELECT add_continuous_aggregate_policy('candles_1h',  start_offset => INTERVAL '3 days',  end_offset => INTERVAL '1 hour',     schedule_interval => INTERVAL '1 hour');
-- SELECT add_continuous_aggregate_policy('candles_2h',  start_offset => INTERVAL '5 days',  end_offset => INTERVAL '2 hours',    schedule_interval => INTERVAL '2 hours');
-- SELECT add_continuous_aggregate_policy('candles_3h',  start_offset => INTERVAL '7 days',  end_offset => INTERVAL '3 hours',    schedule_interval => INTERVAL '3 hours');

-- Open interest / Greeks snapshots per strike.
CREATE TABLE oi_snapshots (
    symbol              TEXT NOT NULL,     -- e.g. NIFTY
    expiry              DATE NOT NULL,
    strike              NUMERIC(10, 2) NOT NULL,
    option_type         TEXT NOT NULL CHECK (option_type IN ('CE', 'PE')),
    ts                  TIMESTAMPTZ NOT NULL,
    oi                  BIGINT NOT NULL,
    oi_change           BIGINT NOT NULL DEFAULT 0,
    iv                  NUMERIC(6, 2),
    delta               NUMERIC(5, 4),
    ltp                 NUMERIC(12, 2),
    PRIMARY KEY (symbol, expiry, strike, option_type, ts)
);
SELECT create_hypertable('oi_snapshots', 'ts', if_not_exists => TRUE);
CREATE INDEX idx_oi_symbol_expiry_ts ON oi_snapshots (symbol, expiry, ts DESC);

CREATE TABLE india_vix_snapshots (
    ts                  TIMESTAMPTZ NOT NULL PRIMARY KEY,
    value               NUMERIC(6, 2) NOT NULL,
    regime              vix_regime NOT NULL
);
SELECT create_hypertable('india_vix_snapshots', 'ts', if_not_exists => TRUE);

-- ── Pattern / negation / levels ─────────────────────────────────────────

CREATE TABLE patterns_detected (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol              TEXT NOT NULL,
    timeframe           TEXT NOT NULL,
    pattern_type        TEXT NOT NULL,      -- engulfing | three_inside | three_outside | harami | doji | pin_bar
    direction           TEXT NOT NULL CHECK (direction IN ('bullish', 'bearish')),
    bar_ts              TIMESTAMPTZ NOT NULL,
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_patterns_symbol_tf_bar ON patterns_detected (symbol, timeframe, bar_ts DESC);

CREATE TABLE negation_predictions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id              UUID NOT NULL REFERENCES patterns_detected(id) ON DELETE CASCADE,
    model_version           TEXT NOT NULL DEFAULT 'heuristic-v1',   -- swap to lstm-v1 in v1.1 without migration
    predicted_candles       NUMERIC(6, 2) NOT NULL,
    predicted_window_start  TIMESTAMPTZ NOT NULL,
    predicted_window_end    TIMESTAMPTZ NOT NULL,
    vix_regime_at_prediction vix_regime NOT NULL,
    actual_negation_ts      TIMESTAMPTZ,     -- filled in retroactively once observed
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_negation_pattern_id ON negation_predictions (pattern_id);

CREATE TABLE sr_levels (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol              TEXT NOT NULL,
    timeframe           TEXT NOT NULL,
    level_price         NUMERIC(12, 2) NOT NULL,
    level_type          TEXT NOT NULL CHECK (level_type IN ('support', 'resistance')),
    hit_count           INTEGER NOT NULL DEFAULT 1,
    confluence_score    NUMERIC(4, 3) NOT NULL DEFAULT 0,  -- cross-timeframe confluence, 0-1
    last_hit_ts         TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sr_symbol_tf ON sr_levels (symbol, timeframe);

-- ── Recommendations ─────────────────────────────────────────────────────

CREATE TABLE recommendations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category            recommendation_category NOT NULL,
    symbol              TEXT NOT NULL,
    strike              NUMERIC(10, 2),         -- null for Strategic (direction-only) recs
    option_type         TEXT CHECK (option_type IN ('CE', 'PE')),
    action              recommendation_action NOT NULL,
    entry_price         NUMERIC(12, 2),
    stop_loss           NUMERIC(12, 2),
    target_price        NUMERIC(12, 2),
    forecast_horizon    TEXT,                    -- '15m' | '30m' | '1h' | '2h' | '2-5d' for Strategic
    confidence_score    NUMERIC(5, 2) NOT NULL,  -- 0-100, weighted formula per docs/buildspec.json
    risk_score          NUMERIC(5, 2) NOT NULL,  -- 0-100
    conviction_score    NUMERIC(5, 2) NOT NULL,  -- 0-100
    rationale           JSONB NOT NULL,          -- structured reasoning tree, Claude-narrated
    vix_regime_at_creation vix_regime NOT NULL,
    is_expiry_day        BOOLEAN NOT NULL DEFAULT FALSE,
    status               TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'negated', 'expired', 'closed')),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_recommendations_category_created ON recommendations (category, created_at DESC);
CREATE INDEX idx_recommendations_symbol ON recommendations (symbol);

-- Feedback loop: manual trade-outcome logging (docs/architecture.md step 11).
CREATE TABLE trade_journal (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id   UUID REFERENCES recommendations(id) ON DELETE SET NULL,
    user_id             UUID NOT NULL REFERENCES users(id),
    outcome             TEXT NOT NULL CHECK (outcome IN ('win', 'loss', 'breakeven', 'not_taken')),
    realized_pnl_pct    NUMERIC(6, 2),
    observation         TEXT,
    logged_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_trade_journal_recommendation ON trade_journal (recommendation_id);

-- Simulated fills ONLY. No real order, no real money — see docs/CLAUDE.md section 2.
CREATE TABLE paper_trades (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id   UUID NOT NULL REFERENCES recommendations(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id),
    simulated_entry_price NUMERIC(12, 2) NOT NULL,
    simulated_exit_price  NUMERIC(12, 2),
    simulated_pnl_pct     NUMERIC(6, 2),
    status                TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    -- target_price/stop_loss_price/expiry_at added in migration 0005 (F6.1)
    -- — locked in at open time, see that migration's docstring.
    target_price          NUMERIC(12, 2),
    stop_loss_price       NUMERIC(12, 2),
    expiry_at             TIMESTAMPTZ,
    opened_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at            TIMESTAMPTZ
);
CREATE INDEX idx_paper_trades_user ON paper_trades (user_id, status);

-- ── Strategy Marketplace ─────────────────────────────────────────────────

CREATE TABLE strategies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    source_type         strategy_source_type NOT NULL,
    source_ref          TEXT,               -- video URL, or null for text/pseudocode entered inline
    raw_input           TEXT,               -- free text, pseudocode, or Pine Script as submitted
    canonical_logic     JSONB,              -- extracted structured rule set (see docs/strategy_schema.json)
    status              strategy_status NOT NULL DEFAULT 'ingested',
    created_by          UUID NOT NULL REFERENCES users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_strategies_status ON strategies (status);

CREATE TABLE strategy_backtests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id         UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    date_from           DATE NOT NULL,
    date_to             DATE NOT NULL,
    win_rate_pct        NUMERIC(6, 2),
    sharpe_ratio        NUMERIC(10, 4),
    max_drawdown_pct    NUMERIC(6, 2),
    total_return_pct    NUMERIC(10, 2),
    confidence_score    NUMERIC(5, 2),      -- 0-100, independent-backtest-derived
    trade_log           JSONB NOT NULL DEFAULT '[]',
    run_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_strategy_backtests_strategy ON strategy_backtests (strategy_id);

-- Fusion: combining two strategies' rule sets into one, independently re-backtested.
CREATE TABLE strategy_fusion (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_strategy_ids UUID[] NOT NULL,
    resolved_logic      JSONB NOT NULL,     -- merged rule set + conflict-resolution notes
    fused_strategy_id   UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Immutable change trail for strategy edits (compliance/traceability pattern).
CREATE TABLE strategy_audit_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id         UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    changed_by          UUID NOT NULL REFERENCES users(id),
    diff                JSONB NOT NULL,
    changed_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Alerts & audit ───────────────────────────────────────────────────────

CREATE TABLE alerts_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id   UUID NOT NULL REFERENCES recommendations(id) ON DELETE CASCADE,
    channel             TEXT NOT NULL CHECK (channel IN ('telegram', 'email', 'dashboard')),
    dispatch_status     dispatch_status NOT NULL DEFAULT 'pending',
    sent_at             TIMESTAMPTZ
);
CREATE INDEX idx_alerts_recommendation ON alerts_log (recommendation_id);

-- Generic append-only audit trail for every state-changing event
-- (docs/CLAUDE.md section 3 — no UPDATE/DELETE paths in application code).
CREATE TABLE audit_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type          TEXT NOT NULL,      -- recommendation_created | backtest_run | journal_entry | ...
    entity_id           UUID,
    payload             JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_log_event_type ON audit_log (event_type, created_at DESC);
