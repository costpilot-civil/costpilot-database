"""Validate SQL boundaries and parameter passing without a live database."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.repositories.catalog_repository import CatalogRepository
from src.repositories.embedding_repository import EmbeddingRepository
from src.repositories.import_repository import ImportRepository
from src.repositories.search_repository import SearchRepository


def fake_db(*, fetchone=None, fetchall=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    cursor.rowcount = 1
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn, cursor


def test_import_repository_parameterizes_source_upsert():
    conn, cursor = fake_db(fetchone=(101,))
    id_ = ImportRepository(conn).upsert_data_source(
        code="source'with-quote", name="Name", source_type="ITWO_XML", description=None
    )
    assert id_ == 101
    query, params = cursor.execute.call_args.args
    assert "ON CONFLICT (code)" in query
    assert "source'with-quote" not in query
    assert params == ("source'with-quote", "Name", "ITWO_XML", None)


def test_import_repository_logging_status():
    conn, cursor = fake_db(fetchone=(42,))
    repository = ImportRepository(conn)
    assert repository.create_import_log(data_source_id=3, file_name="catalog.xml", file_hash="hash") == 42
    assert "'RUNNING'" in cursor.execute.call_args.args[0]
    repository.mark_import_succeeded(import_log_id=42, records_total=7, records_imported=7)
    assert "'SUCCEEDED'" in cursor.execute.call_args.args[0]
    repository.mark_import_failed(import_log_id=42, error_message="error")
    assert "'FAILED'" in cursor.execute.call_args.args[0]
    cursor.rowcount = 0
    with pytest.raises(RuntimeError, match="not found"):
        repository.mark_import_failed(import_log_id=999, error_message="error")


def test_search_repository_serializes_nested_json_and_uses_upsert():
    conn, cursor = fake_db()
    attributes = {"strength_class": "C8/10", "exposure_class": {"x0": "X0"}}
    SearchRepository(conn).upsert_commodity_search(
        commodity_id=9, material_type="concrete", normalized_unit=None,
        attributes=attributes, search_text="Beton C8/10",
    )
    query, params = cursor.execute.call_args.args
    assert "ON CONFLICT (commodity_id)" in query
    assert "search_vector" not in query  # Generated and indexed automatically by PostgreSQL.
    assert params[0:3] == (9, "concrete", None)
    assert json.loads(params[3]) == attributes
    assert params[4] == "Beton C8/10"


def test_catalog_repository_reads_as_commodity_records():
    row = (12, "Beton", "Description", "m³", "A1", "G100", "Group")
    conn, cursor = fake_db(fetchall=[row])
    records = CatalogRepository(conn).read_commodities(data_source_id=4)
    assert len(records) == 1
    assert records[0].id == 12
    assert records[0].group_description == "Group"
    query, params = cursor.execute.call_args.args
    assert "JOIN commodity_groups" in query
    assert "c.data_source_id = %s" in query
    assert params == (4,)


def test_embedding_repository_registers_new_model():
    conn, cursor = fake_db(fetchone=(19,))
    model_id = EmbeddingRepository(conn).upsert_embedding_model(
        name="BAAI/bge-m3", version="v1", dimension=1024
    )
    assert model_id == 19
    assert "ON CONFLICT" in cursor.execute.call_args.args[0]


def test_embedding_repository_validates_existing_model_metadata():
    conn, cursor = fake_db()
    cursor.fetchone.side_effect = [None, (19, 1024, "cosine")]
    assert EmbeddingRepository(conn).upsert_embedding_model(
        name="BAAI/bge-m3", version="v1", dimension=1024
    ) == 19
    cursor.fetchone.side_effect = [None, (19, 512, "cosine")]
    with pytest.raises(ValueError, match="configuration does not match"):
        EmbeddingRepository(conn).upsert_embedding_model(
            name="BAAI/bge-m3", version="v1", dimension=1024
        )


@pytest.mark.parametrize("values", [[], [[1.0, 2.0]], [float("nan"), 0.0], [float("inf"), 0.0]])
def test_embedding_repository_rejects_bad_vector(values):
    conn, cursor = fake_db(fetchone=(2,))
    with pytest.raises(ValueError):
        EmbeddingRepository(conn).upsert_commodity_embedding(
            commodity_id=1, model_id=2, embedding=values, source_hash="hash"
        )


def test_embedding_repository_checks_dimension_before_insert():
    conn, cursor = fake_db(fetchone=(3,))
    with pytest.raises(ValueError, match="dimension mismatch"):
        EmbeddingRepository(conn).upsert_commodity_embedding(
            commodity_id=1, model_id=2, embedding=[1.0, 2.0], source_hash="hash"
        )
    assert cursor.execute.call_count == 1


def test_embedding_repository_upserts_numpy_float32_vector():
    conn, cursor = fake_db()
    cursor.fetchone.side_effect = [(3,), (123,)]
    embedding_id = EmbeddingRepository(conn).upsert_commodity_embedding(
        commodity_id=1, model_id=2,
        embedding=[0.25, 0.5, 0.75], source_hash="abc"
    )
    assert embedding_id == 123
    _, params = cursor.execute.call_args.args
    assert (params[0], params[1], params[3]) == (1, 2, "abc")
    assert isinstance(params[2], np.ndarray)
    assert params[2].dtype == np.float32
    assert "ON CONFLICT (commodity_id, model_id)" in cursor.execute.call_args.args[0]
