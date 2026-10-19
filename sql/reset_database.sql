
-- CostPilot Database Reset
-- WARNING: Deletes all application data.
-- Keeps schema, indexes, constraints and extensions.

BEGIN;

TRUNCATE TABLE
    match_results,
    lv_positions,
    lv_documents,
    projects,
    commodity_embeddings,
    embedding_models,
    commodity_search,
    commodity_prices,
    estimate_prices,
    commodities,
    commodity_groups,
    product_groups,
    import_logs,
    data_sources
RESTART IDENTITY;

COMMIT;
