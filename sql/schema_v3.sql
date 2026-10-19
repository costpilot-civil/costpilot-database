-- CostPilot Database Schema - v3

-- PostgreSQL + pgvector

--

-- Goals:

--   1. Shared material / price catalog with explicit data-source ownership

--   2. Import metadata suitable for repeatable ingestion

--   3. Structured + keyword search projection

--   4. Multi-model vector embeddings

--   5. Project / Tender persistence

--   6. Final material-match persistence

--

-- Notes:

--   - Catalog business codes are unique per data source, not globally.

--   - commodity_prices and estimate_prices remain separate because they

--     represent different source concepts and have different attributes.

--   - Search rows and embeddings are derived data and may be rebuilt.

--   - match_results stores only the current/final decision per Tender item.

--     Top-K candidates / match history can be added later as separate tables.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================

-- Shared updated_at trigger

-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()

RETURNS TRIGGER

LANGUAGE plpgsql

AS $$

BEGIN

    NEW.updated_at = NOW();

    RETURN NEW;

END;

$$;

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

-- Data Sources

--

-- A data source represents the logical origin/owner of imported

-- catalog data, e.g. one supplier catalog.

--

-- "code" is the stable application-facing identifier.

-- "name" is display text and therefore is not used as the key.

-- ============================================================

CREATE TABLE data_sources (

    id BIGSERIAL PRIMARY KEY,

    code TEXT NOT NULL UNIQUE,

    name TEXT NOT NULL,

    source_type TEXT NOT NULL,

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

-- ============================================================

-- Import Logs

--

-- One row represents one import attempt.

-- file_hash can be used by the application to detect repeated

-- imports without forbidding an intentional re-import.

-- ============================================================

CREATE TABLE import_logs (

    id BIGSERIAL PRIMARY KEY,

    data_source_id BIGINT NOT NULL

        REFERENCES data_sources(id)

        ON DELETE RESTRICT,

    file_name TEXT,

    file_hash TEXT,

    status TEXT NOT NULL

        CHECK (status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')),

    records_total INTEGER

        CHECK (records_total IS NULL OR records_total >= 0),

    records_imported INTEGER

        CHECK (records_imported IS NULL OR records_imported >= 0),

    error_message TEXT,

    started_at TIMESTAMPTZ,

    finished_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (

        records_total IS NULL

        OR records_imported IS NULL

        OR records_imported <= records_total

    ),

    CHECK (

        finished_at IS NULL

        OR started_at IS NULL

        OR finished_at >= started_at

    )

);

CREATE INDEX idx_import_logs_data_source_id

    ON import_logs(data_source_id);

CREATE INDEX idx_import_logs_source_file_hash

    ON import_logs(data_source_id, file_hash);

-- ============================================================

-- Product Groups

--

-- Business codes are only required to be unique inside one

-- data source. The (id, data_source_id) unique constraint exists

-- so child tables can enforce same-source relationships with

-- composite foreign keys.

-- ============================================================

CREATE TABLE product_groups (

    id BIGSERIAL PRIMARY KEY,

    data_source_id BIGINT NOT NULL

        REFERENCES data_sources(id)

        ON DELETE RESTRICT,

    code TEXT NOT NULL,

    name TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_product_groups_source_code

        UNIQUE (data_source_id, code),

    CONSTRAINT uq_product_groups_id_source

        UNIQUE (id, data_source_id)

);

CREATE INDEX idx_product_groups_data_source_id

    ON product_groups(data_source_id);

-- ============================================================

-- Commodity Groups

-- Recursive category tree

--

-- data_source_id is stored explicitly because:

--   - commodity-group codes are source-local business identifiers

--   - direct source filtering is common during imports

--   - composite FKs prevent cross-source hierarchy mistakes

-- ============================================================

CREATE TABLE commodity_groups (

    id BIGSERIAL PRIMARY KEY,

    data_source_id BIGINT NOT NULL

        REFERENCES data_sources(id)

        ON DELETE RESTRICT,

    code TEXT NOT NULL,

    description TEXT,

    parent_id BIGINT,

    product_group_id BIGINT,

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

    fixed_hours BOOLEAN,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_commodity_groups_source_code

        UNIQUE (data_source_id, code),

    CONSTRAINT uq_commodity_groups_id_source

        UNIQUE (id, data_source_id),

    CONSTRAINT fk_commodity_groups_parent_same_source

        FOREIGN KEY (parent_id, data_source_id)

        REFERENCES commodity_groups(id, data_source_id)

        ON DELETE RESTRICT,

    CONSTRAINT fk_commodity_groups_product_group_same_source

        FOREIGN KEY (product_group_id, data_source_id)

        REFERENCES product_groups(id, data_source_id)

        ON DELETE RESTRICT

);

CREATE INDEX idx_commodity_groups_data_source_id

    ON commodity_groups(data_source_id);

CREATE INDEX idx_commodity_groups_parent_id

    ON commodity_groups(parent_id);

CREATE INDEX idx_commodity_groups_product_group_id

    ON commodity_groups(product_group_id);

-- ============================================================

-- Commodities

-- Actual materials / resources used for matching

--

-- product_group_id is intentionally not duplicated here.

-- The catalog hierarchy is:

--     product_group -> commodity_group tree -> commodity

-- Keeping one authoritative relationship avoids inconsistent

-- product-group assignments.

-- ============================================================

CREATE TABLE commodities (

    id BIGSERIAL PRIMARY KEY,

    data_source_id BIGINT NOT NULL

        REFERENCES data_sources(id)

        ON DELETE RESTRICT,

    code TEXT NOT NULL,

    description TEXT,

    commodity_group_id BIGINT NOT NULL,

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

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_commodities_source_code

        UNIQUE (data_source_id, code),

    CONSTRAINT uq_commodities_id_source

        UNIQUE (id, data_source_id),

    CONSTRAINT fk_commodities_group_same_source

        FOREIGN KEY (commodity_group_id, data_source_id)

        REFERENCES commodity_groups(id, data_source_id)

        ON DELETE RESTRICT

);

CREATE INDEX idx_commodities_data_source_id

    ON commodities(data_source_id);

CREATE INDEX idx_commodities_group_id

    ON commodities(commodity_group_id);

CREATE INDEX idx_commodities_unit

    ON commodities(unit);

CREATE INDEX idx_commodities_cost_code

    ON commodities(cost_code);

-- ============================================================

-- Commodity Prices

--

-- Kept separate from estimate_prices because the source model

-- contains different fields and semantics for the two concepts.

-- ============================================================

CREATE TABLE commodity_prices (

    id BIGSERIAL PRIMARY KEY,

    commodity_id BIGINT NOT NULL

        REFERENCES commodities(id)

        ON DELETE CASCADE,

    unit_price NUMERIC(16, 4) NOT NULL

        CHECK (unit_price >= 0),

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

    price NUMERIC(16, 4) NOT NULL

        CHECK (price >= 0),

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

-- One derived search row per commodity.

--

-- attributes:

--   Structured material properties, e.g.

--   {

--     "strength_class": "C30/37",

--     "exposure_classes": ["XC3", "XF1", "XA2"]

--   }

--

-- search_text:

--   Canonical text prepared for sparse/keyword retrieval.

--

-- search_vector:

--   Automatically generated from search_text. Application code

--   must not maintain it separately.

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

-- Multiple versions of one model name are supported.

-- ============================================================

CREATE TABLE embedding_models (

    id BIGSERIAL PRIMARY KEY,

    name TEXT NOT NULL,

    version TEXT NOT NULL DEFAULT 'default',

    dimension INTEGER NOT NULL

        CHECK (dimension > 0),

    distance_metric TEXT NOT NULL DEFAULT 'cosine'

        CHECK (distance_metric IN ('cosine', 'l2', 'inner_product')),

    is_active BOOLEAN NOT NULL DEFAULT FALSE,

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_embedding_models_name_version

        UNIQUE (name, version)

);

-- ============================================================

-- Commodity Embeddings

--

-- VECTOR intentionally has no fixed dimension because different

-- models may use different dimensions.

--

-- The application must validate vector length against

-- embedding_models.dimension before insert/update.

--

-- Add model-specific partial HNSW indexes later for models that

-- are actually used in production retrieval.

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

    CONSTRAINT uq_commodity_embeddings_commodity_model

        UNIQUE (commodity_id, model_id)

);

CREATE INDEX idx_commodity_embeddings_commodity_id

    ON commodity_embeddings(commodity_id);

CREATE INDEX idx_commodity_embeddings_model_id

    ON commodity_embeddings(model_id);

-- ============================================================
-- Tender Documents
--
-- One project can own multiple imported Tender documents.
-- Source GAEB/XML is parsed by Core; the original file need not be kept.
-- Backend owns file metadata, project relationships, and status.
-- ============================================================

CREATE TABLE tender_documents (
    id BIGSERIAL PRIMARY KEY,

    project_id BIGINT NOT NULL
        REFERENCES projects(id)
        ON DELETE CASCADE,

    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    storage_path TEXT,
    file_hash TEXT,

    status TEXT NOT NULL DEFAULT 'UPLOADED'
        CHECK (status IN ('UPLOADED', 'PARSING', 'PARSED', 'FAILED')),

    parsed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tender_documents_project_id
    ON tender_documents(project_id);

CREATE INDEX idx_tender_documents_status
    ON tender_documents(status);

CREATE INDEX idx_tender_documents_project_file_hash
    ON tender_documents(project_id, file_hash);

-- ============================================================
-- Tender Categories
--
-- GAEB BoQCtgy nodes form a recursive category tree.
-- (parent_id, tender_document_id) enforces same-document parenting.
-- sort_order preserves original sibling order across categories/items.
-- ============================================================

CREATE TABLE tender_categories (
    id BIGSERIAL PRIMARY KEY,

    tender_document_id BIGINT NOT NULL
        REFERENCES tender_documents(id)
        ON DELETE CASCADE,

    parent_id BIGINT,
    oz TEXT NOT NULL,
    number_part TEXT NOT NULL,
    name TEXT NOT NULL,

    level INTEGER NOT NULL CHECK (level >= 0),
    sort_order INTEGER NOT NULL CHECK (sort_order >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_tender_categories_id_document
        UNIQUE (id, tender_document_id),

    CONSTRAINT fk_tender_categories_parent_same_document
        FOREIGN KEY (parent_id, tender_document_id)
        REFERENCES tender_categories(id, tender_document_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_tender_categories_document_parent
    ON tender_categories(tender_document_id, parent_id, sort_order);

CREATE INDEX idx_tender_categories_document_oz
    ON tender_categories(tender_document_id, oz);

-- ============================================================
-- Tender Items
--
-- Only GAEB Item nodes are stored here and participate in Matching.
-- Category hierarchy is held in tender_categories, not in this table.
-- category_id is nullable for items directly under the root Tender.
-- sort_order preserves sibling ordering relative to categories.
-- ============================================================

CREATE TABLE tender_items (
    id BIGSERIAL PRIMARY KEY,

    tender_document_id BIGINT NOT NULL
        REFERENCES tender_documents(id)
        ON DELETE CASCADE,

    category_id BIGINT,

    oz TEXT NOT NULL,
    number_part TEXT NOT NULL,
    short_text TEXT NOT NULL DEFAULT '',
    long_text TEXT NOT NULL DEFAULT '',

    quantity NUMERIC(18, 4)
        CHECK (quantity IS NULL OR quantity >= 0),
    unit TEXT,

    level INTEGER NOT NULL CHECK (level >= 0),
    sort_order INTEGER NOT NULL CHECK (sort_order >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_tender_items_id_document
        UNIQUE (id, tender_document_id),

    CONSTRAINT fk_tender_items_category_same_document
        FOREIGN KEY (category_id, tender_document_id)
        REFERENCES tender_categories(id, tender_document_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_tender_items_document_category
    ON tender_items(tender_document_id, category_id, sort_order);

CREATE INDEX idx_tender_items_document_oz
    ON tender_items(tender_document_id, oz);

-- ============================================================
-- Match Results
--
-- One current/final match result per Tender item.
-- Top-K candidate lists and match history are not stored here.
-- A result targets a commodity, not a price entry.
-- position_id keeps the existing API/Matching naming for now.
-- ============================================================

CREATE TABLE match_results (
    id BIGSERIAL PRIMARY KEY,

    position_id BIGINT NOT NULL UNIQUE
        REFERENCES tender_items(id)
        ON DELETE CASCADE,

    commodity_id BIGINT
        REFERENCES commodities(id)
        ON DELETE RESTRICT,

    status TEXT NOT NULL
        CHECK (status IN (
            'AUTO_MATCHED',
            'MANUAL_MATCHED',
            'REVIEW_REQUIRED',
            'UNMATCHED'
        )),

    score NUMERIC(8, 6)
        CHECK (score IS NULL OR (score >= 0 AND score <= 1)),

    match_type TEXT
        CHECK (match_type IS NULL OR match_type IN ('AUTO', 'MANUAL')),

    note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_match_results_status_commodity
        CHECK (
            (status = 'UNMATCHED' AND commodity_id IS NULL)
            OR
            (status IN (
                'AUTO_MATCHED',
                'MANUAL_MATCHED',
                'REVIEW_REQUIRED'
            ) AND commodity_id IS NOT NULL)
        )
);

CREATE INDEX idx_match_results_commodity_id
    ON match_results(commodity_id);

CREATE INDEX idx_match_results_status
    ON match_results(status);

-- ============================================================

-- updated_at triggers

-- ============================================================

CREATE TRIGGER trg_projects_updated_at

BEFORE UPDATE ON projects

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_data_sources_updated_at

BEFORE UPDATE ON data_sources

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_import_logs_updated_at

BEFORE UPDATE ON import_logs

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_product_groups_updated_at

BEFORE UPDATE ON product_groups

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_commodity_groups_updated_at

BEFORE UPDATE ON commodity_groups

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_commodities_updated_at

BEFORE UPDATE ON commodities

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_commodity_prices_updated_at

BEFORE UPDATE ON commodity_prices

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_estimate_prices_updated_at

BEFORE UPDATE ON estimate_prices

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_commodity_search_updated_at

BEFORE UPDATE ON commodity_search

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_embedding_models_updated_at

BEFORE UPDATE ON embedding_models

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_commodity_embeddings_updated_at

BEFORE UPDATE ON commodity_embeddings

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_tender_documents_updated_at

BEFORE UPDATE ON tender_documents

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_tender_categories_updated_at
BEFORE UPDATE ON tender_categories
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_tender_items_updated_at

BEFORE UPDATE ON tender_items

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_match_results_updated_at

BEFORE UPDATE ON match_results

FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
