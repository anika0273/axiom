-- Axiom PostgreSQL Schema — reference only, NOT executed directly.
-- The canonical source of truth is backend/migrations/versions/.
-- Run migrations with: docker compose exec backend alembic upgrade head

-- ── Enum types ────────────────────────────────────────────────────────────────

CREATE TYPE experiment_status AS ENUM (
    'draft',
    'running',
    'completed',
    'stopped_early'
);

CREATE TYPE experiment_type AS ENUM (
    'proportion',
    'mean',
    'ratio'
);

CREATE TYPE analysis_type AS ENUM (
    'full',
    'sequential_check',
    'interim'
);

CREATE TYPE metric_type AS ENUM (
    'primary',
    'secondary',
    'guardrail'
);

CREATE TYPE interaction_type AS ENUM (
    'plan',
    'interpretation',
    'report'
);

-- ── experiments ───────────────────────────────────────────────────────────────

CREATE TABLE experiments (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                   TEXT NOT NULL,
    description            TEXT,
    status                 experiment_status NOT NULL,
    experiment_type        experiment_type   NOT NULL,
    hypothesis             TEXT,
    baseline_metric        DOUBLE PRECISION  NOT NULL,
    mde                    DOUBLE PRECISION  NOT NULL,
    alpha                  DOUBLE PRECISION  NOT NULL DEFAULT 0.05,
    power                  DOUBLE PRECISION  NOT NULL DEFAULT 0.80,
    daily_traffic_estimate INTEGER,
    created_at             TIMESTAMPTZ       NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ       NOT NULL DEFAULT now(),
    started_at             TIMESTAMPTZ,
    completed_at           TIMESTAMPTZ,

    CONSTRAINT ck_experiments_completed_after_started
        CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at > started_at)
);

CREATE INDEX ix_experiments_status     ON experiments (status);
CREATE INDEX ix_experiments_created_at ON experiments (created_at);

-- ── experiment_results ────────────────────────────────────────────────────────

CREATE TABLE experiment_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id       UUID          NOT NULL REFERENCES experiments (id) ON DELETE CASCADE,
    analysis_type       analysis_type NOT NULL,
    full_analysis_json  JSONB,
    is_significant      BOOLEAN,
    p_value             DOUBLE PRECISION,
    relative_lift       DOUBLE PRECISION,
    analyzed_at         TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX ix_experiment_results_experiment_id ON experiment_results (experiment_id);

-- ── experiment_metrics ────────────────────────────────────────────────────────

CREATE TABLE experiment_metrics (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID        NOT NULL REFERENCES experiments (id) ON DELETE CASCADE,
    metric_name   TEXT        NOT NULL,
    metric_type   metric_type NOT NULL,
    is_primary    BOOLEAN     NOT NULL DEFAULT false
);

CREATE INDEX ix_experiment_metrics_experiment_id ON experiment_metrics (experiment_id);

-- ── ai_interactions ───────────────────────────────────────────────────────────

CREATE TABLE ai_interactions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id    UUID             REFERENCES experiments (id) ON DELETE CASCADE,
    interaction_type interaction_type NOT NULL,
    user_prompt      TEXT             NOT NULL,
    ai_response      TEXT             NOT NULL,
    tokens_used      INTEGER,
    created_at       TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX ix_ai_interactions_experiment_id ON ai_interactions (experiment_id);
