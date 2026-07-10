-- Postgres schema for pipeline-cost-observatory

CREATE TABLE IF NOT EXISTS teams (
    team_id       SERIAL PRIMARY KEY,
    team_name     TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id        SERIAL PRIMARY KEY,
    source        TEXT NOT NULL,               -- 'airflow' or 'dbt'
    pipeline_name TEXT NOT NULL,                -- dag_id or dbt model name
    team_id       INTEGER REFERENCES teams(team_id),
    executor_type TEXT NOT NULL,                -- e.g. 'databricks', 'fargate', 'airflow_worker'
    started_at    TIMESTAMPTZ NOT NULL,
    ended_at      TIMESTAMPTZ NOT NULL,
    duration_sec  NUMERIC GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (ended_at - started_at))) STORED,
    units_processed NUMERIC,                    -- optional: bytes/rows, used by some pricing rules
    raw_metadata  JSONB,
    inserted_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cost_estimates (
    estimate_id   SERIAL PRIMARY KEY,
    run_id        INTEGER REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    estimated_cost_usd NUMERIC NOT NULL,
    pricing_rule  TEXT NOT NULL,
    is_anomaly    BOOLEAN NOT NULL DEFAULT false,
    anomaly_score NUMERIC,
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline_name ON pipeline_runs(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_cost_estimates_run_id ON cost_estimates(run_id);

-- Seed a couple of teams and sample runs so the dashboard has data on first boot
INSERT INTO teams (team_name) VALUES ('data-platform'), ('analytics'), ('ml-ops') ON CONFLICT DO NOTHING;
