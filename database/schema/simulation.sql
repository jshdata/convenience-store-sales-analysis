-- Replay state only. Existing sales/content tables are never modified.
CREATE SCHEMA IF NOT EXISTS simulation;
CREATE TABLE IF NOT EXISTS simulation.runs (
    id UUID PRIMARY KEY,
    owner_id TEXT NOT NULL,
    start_day DATE NOT NULL,
    end_day DATE NOT NULL,
    store_scope TEXT NOT NULL CHECK (store_scope IN ('ALL', 'CU', 'GS25', 'seven')),
    channel_id TEXT NOT NULL,
    thresholds JSONB NOT NULL,
    next_day DATE NOT NULL,
    last_day DATE,
    processed_days INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('ready', 'processing', 'completed', 'attention')),
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (start_day <= end_day)
);
CREATE INDEX IF NOT EXISTS simulation_runs_owner_idx ON simulation.runs (owner_id, created_at DESC);
CREATE TABLE IF NOT EXISTS simulation.events (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES simulation.runs(id),
    sale_day DATE NOT NULL,
    store_type TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('high', 'low')),
    amount BIGINT NOT NULL,
    deviation DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('sending', 'sent', 'unknown')),
    slack_ts TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, sale_day, store_type)
);
