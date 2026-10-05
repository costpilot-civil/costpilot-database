-- CostPilot Database Schema - v1
-- PostgreSQL + pgvector
--
-- Scope:
--   1. Project registry
--   2. Shared material / price catalog
--   3. Structured + keyword search projection
--   4. Multi-model vector embeddings
--   5. Optional import metadata

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Projects
-- ============================================================

CREATE TABLE projects (
    id BIGSERIAL PRIMARY KEY,

    name TEXT NOT NULL,
    project_number TEXT,
    client TEXT,
    location TEXT,
    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_project_number
    ON projects(project_number);


-- ============================================================
-- Data Sources / Import Metadata
-- ============================================================

CREATE TABLE data_sources (
    id BIGSERIAL PRIMARY KEY,

    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE import_logs (
    id BIGSERIAL PRIMARY KEY,

    data_source_id BIGINT NOT NULL
        REFERENCES data_sources(id)
        ON DELETE RESTRICT,

    status TEXT NOT NULL,
    records_total INTEGER,
    records_imported INTEGER,
    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_import_logs_data_source_id
    ON import_logs(data_source_id);


-- ============================================================
-- Product Groups
-- ============================================================

CREATE TABLE product_groups (
    id BIGSERIAL PRIMARY KEY,

    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- Commodity Groups
-- Recursive category tree
-- ============================================================

CREATE TABLE commodity_groups (
    id BIGSERIAL PRIMARY KEY,

    code TEXT NOT NULL UNIQUE,
    description TEXT,

    parent_id BIGINT
        REFERENCES commodity_groups(id)
        ON DELETE RESTRICT,

    source_ref TEXT,
    cost_code TEXT,
    unit TEXT,

    discount NUMERIC(12, 4),
    wastage NUMERIC(12, 4),
    estimation_factor NUMERIC(12, 4),
    regie_factor NUMERIC(12, 4),

    addition_1 TEXT,
    addition_2 TEXT,
    addition_3 TEXT,
    addition_4 TEXT,

    remarks TEXT,

    product_group_id BIGINT
        REFERENCES product_groups(id)
        ON DELETE SET NULL,

    fixed_hours BOOLEAN,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_commodity_groups_parent_id
    ON commodity_groups(parent_id);

CREATE INDEX idx_commodity_groups_product_group_id
    ON commodity_groups(product_group_id);


-- ============================================================
-- Commodities
-- Actual materials / resources used for matching
-- ============================================================

CREATE TABLE commodities (
    id BIGSERIAL PRIMARY KEY,

    code TEXT NOT NULL UNIQUE,
    description TEXT,

    commodity_group_id BIGINT NOT NULL
        REFERENCES commodity_groups(id)
        ON DELETE RESTRICT,

    product_group_id BIGINT
        REFERENCES product_groups(id)
        ON DELETE SET NULL,

    source_ref TEXT,

    unit TEXT,

    cost_code TEXT,
    cost_code_unit TEXT,

    weight NUMERIC(16, 4),
    weight_unit TEXT,

    volume NUMERIC(16, 4),
    volume_unit TEXT,

    addition_1 TEXT,
    addition_2 TEXT,
    addition_3 TEXT,
    addition_4 TEXT,

    remarks TEXT,

    external_price_update BOOLEAN,
    selected BOOLEAN,
    fixed_hours BOOLEAN,

    change_date DATE,
    change_user TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_commodities_group_id
    ON commodities(commodity_group_id);

CREATE INDEX idx_commodities_product_group_id
    ON commodities(product_group_id);

CREATE INDEX idx_commodities_unit
    ON commodities(unit);

CREATE INDEX idx_commodities_cost_code
    ON commodities(cost_code);


-- ============================================================
-- Commodity Prices
-- One commodity may have multiple price records
-- ============================================================

CREATE TABLE commodity_prices (
    id BIGSERIAL PRIMARY KEY,

    commodity_id BIGINT NOT NULL
        REFERENCES commodities(id)
        ON DELETE CASCADE,

    unit_price NUMERIC(16, 4) NOT NULL,
    currency TEXT NOT NULL,

    discount NUMERIC(16, 4),
    freight_costs NUMERIC(16, 4),
    miscellaneous NUMERIC(16, 4),
    wastage NUMERIC(16, 4),

    modified_date DATE,
    modified_user TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_commodity_prices_commodity_id
    ON commodity_prices(commodity_id);


-- ============================================================
-- Estimate Prices
-- ============================================================

CREATE TABLE estimate_prices (
    id BIGSERIAL PRIMARY KEY,

    commodity_id BIGINT NOT NULL
        REFERENCES commodities(id)
        ON DELETE CASCADE,

    price_type TEXT NOT NULL,

    factor NUMERIC(16, 4),
    price NUMERIC(16, 4) NOT NULL,
    currency TEXT NOT NULL,

    modified_date DATE,
    modified_user TEXT,

    fixed_price BOOLEAN,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_estimate_prices_commodity_id
    ON estimate_prices(commodity_id);

CREATE INDEX idx_estimate_prices_price_type
    ON estimate_prices(price_type);


-- ============================================================
-- Search Projection
--
-- One search record per commodity.
--
-- attributes:
--   Structured material properties, e.g.
--   {
--     "strength_class": "C30/37",
--     "exposure_classes": ["XC3", "XF1", "XA2"]
--   }
--
-- search_text:
--   Canonical text prepared for keyword retrieval.
--
-- search_vector:
--   PostgreSQL full-text representation of search_text.
--   The "simple" configuration is used as a neutral baseline for
--   technical terms, product codes and engineering notation.
-- ============================================================

CREATE TABLE commodity_search (
    commodity_id BIGINT PRIMARY KEY
        REFERENCES commodities(id)
        ON DELETE CASCADE,

    material_type TEXT,
    normalized_unit TEXT,

    attributes JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(attributes) = 'object'),

    search_text TEXT NOT NULL DEFAULT '',

    search_vector TSVECTOR
        GENERATED ALWAYS AS (
            to_tsvector('simple', COALESCE(search_text, ''))
        ) STORED,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_commodity_search_material_type
    ON commodity_search(material_type);

CREATE INDEX idx_commodity_search_normalized_unit
    ON commodity_search(normalized_unit);

CREATE INDEX idx_commodity_search_attributes
    ON commodity_search
    USING GIN (attributes);

CREATE INDEX idx_commodity_search_vector
    ON commodity_search
    USING GIN (search_vector);


-- ============================================================
-- Embedding Models
--
-- Embeddings are stored separately from commodity_search so a
-- commodity can have vectors generated by multiple models.
-- ============================================================

CREATE TABLE embedding_models (
    id BIGSERIAL PRIMARY KEY,

    name TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'default',

    dimension INTEGER NOT NULL
        CHECK (dimension > 0),

    distance_metric TEXT NOT NULL DEFAULT 'cosine',
    is_active BOOLEAN NOT NULL DEFAULT FALSE,

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (name, version)
);


-- ============================================================
-- Commodity Embeddings
--
-- VECTOR intentionally has no fixed dimension here because
-- different embedding models may use different dimensions.
--
-- Model-specific ANN indexes (e.g. HNSW) should be added later
-- for the active model(s), since vectors with different dimensions
-- cannot share one dimension-specific ANN index.
-- ============================================================

CREATE TABLE commodity_embeddings (
    id BIGSERIAL PRIMARY KEY,

    commodity_id BIGINT NOT NULL
        REFERENCES commodities(id)
        ON DELETE CASCADE,

    model_id BIGINT NOT NULL
        REFERENCES embedding_models(id)
        ON DELETE RESTRICT,

    embedding VECTOR NOT NULL,

    source_hash TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (commodity_id, model_id)
);

CREATE INDEX idx_commodity_embeddings_commodity_id
    ON commodity_embeddings(commodity_id);

CREATE INDEX idx_commodity_embeddings_model_id
    ON commodity_embeddings(model_id);

COMMIT;
