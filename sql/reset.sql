-- CostPilot Database Reset
-- Drops all CostPilot tables.
-- Run schema.sql afterwards to recreate the database structure.

BEGIN;

DROP TABLE IF EXISTS import_logs CASCADE;
DROP TABLE IF EXISTS data_sources CASCADE;

DROP TABLE IF EXISTS commodity_embeddings CASCADE;
DROP TABLE IF EXISTS embedding_models CASCADE;

DROP TABLE IF EXISTS commodity_search CASCADE;

DROP TABLE IF EXISTS estimate_prices CASCADE;
DROP TABLE IF EXISTS commodity_prices CASCADE;

DROP TABLE IF EXISTS commodities CASCADE;
DROP TABLE IF EXISTS commodity_groups CASCADE;
DROP TABLE IF EXISTS product_groups CASCADE;

DROP TABLE IF EXISTS projects CASCADE;

COMMIT;