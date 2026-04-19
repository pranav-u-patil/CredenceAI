-- ── Geopolitical events ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS geo_events (
    id               UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    detected_at      TIMESTAMPTZ DEFAULT now(),
    event_name       TEXT    NOT NULL,
    event_type       TEXT,
    severity         TEXT,
    probability      FLOAT,
    affected_assets  TEXT[],
    projected_impact JSONB,
    polymarket_id    TEXT,
    status           TEXT    DEFAULT 'ACTIVE'
);

-- ── News items ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS news_items (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    published_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    title           TEXT    NOT NULL,
    body            TEXT,
    url             TEXT    UNIQUE,
    source          TEXT,
    symbols         TEXT[],
    sentiment_score FLOAT,
    sentiment_label TEXT,
    entities        JSONB   DEFAULT '[]',
    processed       BOOLEAN DEFAULT FALSE
);
SELECT create_hypertable('news_items','published_at',if_not_exists=>TRUE);
CREATE INDEX IF NOT EXISTS idx_news_time    ON news_items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_symbols ON news_items USING GIN(symbols);

-- ── Social posts ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS social_posts (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    posted_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    platform        TEXT    NOT NULL,
    author          TEXT,
    content         TEXT,
    symbols         TEXT[],
    sentiment_score FLOAT,
    engagement      BIGINT,
    url             TEXT,
    is_insider      BOOLEAN DEFAULT FALSE
);
SELECT create_hypertable('social_posts','posted_at',if_not_exists=>TRUE);
CREATE INDEX IF NOT EXISTS idx_social_symbols ON social_posts USING GIN(symbols);

-- ── Agent memory ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_memory (
    id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name  TEXT    NOT NULL,
    memory_type TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    symbol      TEXT,
    importance  FLOAT   DEFAULT 0.5,
    created_at  TIMESTAMPTZ DEFAULT now(),
    expires_at  TIMESTAMPTZ,
    metadata    JSONB   DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_agent_mem ON agent_memory(agent_name, created_at DESC);

