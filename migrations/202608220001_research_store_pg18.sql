BEGIN;

DO $$
BEGIN
    IF current_setting('server_version_num')::int < 180000 THEN
        RAISE EXCEPTION 'The shared research store requires PostgreSQL 18 or newer.';
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS research_variables (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    provider text NOT NULL,
    series_id text NOT NULL,
    route text NOT NULL DEFAULT '',
    name text NOT NULL,
    title text NOT NULL,
    description text NOT NULL DEFAULT '',
    frequency text NOT NULL DEFAULT '',
    units text NOT NULL DEFAULT '',
    economic_category text NOT NULL DEFAULT 'other_indicators',
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_research_variables_identity_active
    ON research_variables(provider, series_id, route)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_research_variables_category_updated
    ON research_variables(economic_category, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_variables_metadata
    ON research_variables USING gin(metadata jsonb_path_ops);

CREATE TABLE IF NOT EXISTS series_observations (
    id uuid NOT NULL DEFAULT uuidv7(),
    variable_id uuid NOT NULL REFERENCES research_variables(id) ON DELETE CASCADE,
    observed_at date NOT NULL,
    value double precision,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(id, observed_at),
    UNIQUE(variable_id, observed_at)
) PARTITION BY RANGE(observed_at);

CREATE TABLE IF NOT EXISTS series_observations_default
    PARTITION OF series_observations DEFAULT;
CREATE INDEX IF NOT EXISTS idx_series_observations_variable_date
    ON series_observations(variable_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_series_observations_date_brin
    ON series_observations USING brin(observed_at);

CREATE TABLE IF NOT EXISTS analysis_snapshots (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    snapshot_type text NOT NULL,
    target text NOT NULL,
    as_of_date date NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    deleted_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_lookup
    ON analysis_snapshots(snapshot_type, target, created_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_expiry
    ON analysis_snapshots(expires_at)
    WHERE deleted_at IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'research_variables') THEN
        RAISE EXCEPTION 'Research-store migration verification failed.';
    END IF;
END $$;

COMMIT;
