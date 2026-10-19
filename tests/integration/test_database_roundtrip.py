"""Opt-in PostgreSQL tests; every write stays inside one rolled-back transaction.

Run only against an explicitly configured test database:
COSTPILOT_TEST_DATABASE=1 uv run --env-file .env pytest -m integration

The fixture intentionally does not use DBConnector: its context manager commits on
successful exit. We manage psycopg.Connection directly and always roll it back.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def db_conn():
    if os.getenv("COSTPILOT_TEST_DATABASE") != "1":
        pytest.skip(
            "Set COSTPILOT_TEST_DATABASE=1 to enable PostgreSQL integration tests"
        )

    required = (
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    )
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        pytest.skip(f"PostgreSQL environment is incomplete: {missing}")

    import psycopg
    from pgvector.psycopg import register_vector

    conn = psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        autocommit=False,
    )
    try:
        register_vector(conn)
        conn.execute(
            "SELECT 1"
        )  # Establish an outer transaction before importer savepoints.
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def imported_catalog(db_conn, sample_catalog):
    from src.importing.catalog_importer import CatalogImporter
    from src.repositories.import_repository import ImportRepository

    code = f"pytest-{uuid.uuid4().hex}"
    repository = ImportRepository(db_conn)
    source_id = repository.upsert_data_source(
        code=code, name="CostPilot pytest", source_type="TEST_XML", description=None
    )
    result = CatalogImporter(db_conn).import_catalog(
        data=sample_catalog, data_source_id=source_id
    )
    assert result.commodities == 1
    return source_id


def test_catalog_is_idempotent_and_prices_not_duplicated(
    db_conn, imported_catalog, sample_catalog
):
    from src.importing.catalog_importer import CatalogImporter
    from src.repositories.catalog_repository import CatalogRepository

    source_id = imported_catalog
    first = CatalogRepository(db_conn).read_commodities(data_source_id=source_id)
    assert len(first) == 1
    result = CatalogImporter(db_conn).import_catalog(
        data=sample_catalog, data_source_id=source_id
    )
    second = CatalogRepository(db_conn).read_commodities(data_source_id=source_id)
    assert result.total_records == 6
    assert [row.id for row in first] == [row.id for row in second]

    with db_conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM commodity_prices WHERE commodity_id = %s",
            (first[0].id,),
        )
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            "SELECT COUNT(*) FROM estimate_prices WHERE commodity_id = %s",
            (first[0].id,),
        )
        assert cursor.fetchone()[0] == 1


def test_search_and_embedding_roundtrip_with_generated_tsvector(
    db_conn, imported_catalog
):
    from src.importing.embedding_importer import EmbeddingImporter
    from src.importing.search_importer import SearchImporter
    from src.repositories.catalog_repository import CatalogRepository

    source_id = imported_catalog
    commodity = CatalogRepository(db_conn).read_commodities(data_source_id=source_id)[0]
    extractor = MagicMock()
    extractor.extract.return_value = SimpleNamespace(
        material_type="concrete",
        core_attributes={"strength_class": "C8/10"},
        supplementary_attributes={"exposure_class": {"x0": "X0"}},
    )
    assert (
        SearchImporter(db_conn, extractor).import_commodities(data_source_id=source_id)
        == 1
    )

    fake_model = MagicMock()
    fake_model.name = f"pytest-model-{uuid.uuid4().hex}"
    fake_model.version = "v1"
    fake_model.dimension = 3
    fake_model.encode_batch.side_effect = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    importer = EmbeddingImporter(db_conn, fake_model, batch_size=2)
    assert importer.import_commodities(data_source_id=source_id) == 1
    assert importer.import_commodities(data_source_id=source_id) == 1

    with db_conn.cursor() as cursor:
        cursor.execute(
            "SELECT material_type, attributes, search_text, search_vector::text "
            "FROM commodity_search WHERE commodity_id = %s",
            (commodity.id,),
        )
        material_type, attributes, search_text, search_vector = cursor.fetchone()
        assert material_type == "concrete"
        assert attributes["strength_class"] == "C8/10"
        assert "C8/10" in search_text
        assert "beton" in search_vector.lower()

        cursor.execute(
            "SELECT vector_dims(embedding), source_hash, COUNT(*) OVER () "
            "FROM commodity_embeddings WHERE commodity_id = %s",
            (commodity.id,),
        )
        dimensions, stored_hash, count = cursor.fetchone()
        assert dimensions == 3
        assert len(stored_hash) == len(hashlib.sha256().hexdigest())
        assert count == 1


def test_repository_rejects_incompatible_model_and_invalid_vectors(db_conn):
    from src.repositories.embedding_repository import EmbeddingRepository

    repo = EmbeddingRepository(db_conn)
    name = f"pytest-model-{uuid.uuid4().hex}"
    model_id = repo.upsert_embedding_model(name=name, version="v1", dimension=3)
    assert repo.upsert_embedding_model(name=name, version="v1", dimension=3) == model_id
    with pytest.raises(ValueError, match="configuration does not match"):
        repo.upsert_embedding_model(name=name, version="v1", dimension=4)
    with pytest.raises(ValueError, match="dimension mismatch"):
        repo.upsert_commodity_embedding(
            commodity_id=1, model_id=model_id, embedding=[1.0, 2.0], source_hash="abc"
        )
    with pytest.raises(ValueError, match="non-finite"):
        repo.upsert_commodity_embedding(
            commodity_id=1,
            model_id=model_id,
            embedding=[float("nan"), 0.0, 0.0],
            source_hash="abc",
        )
