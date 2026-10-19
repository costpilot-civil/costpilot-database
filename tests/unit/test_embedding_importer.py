from __future__ import annotations

import hashlib
from contextlib import nullcontext
from unittest.mock import MagicMock

import pytest

from src.importing.embedding_importer import EmbeddingImporter


def fake_model():
    model = MagicMock()
    model.name = "test-model"
    model.version = "test-v1"
    model.dimension = 3
    model.encode_batch.side_effect = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    return model


def make_importer(monkeypatch, model=None, batch_size=2):
    from src.importing import embedding_importer as module

    catalog = MagicMock()
    embedding = MagicMock()
    embedding.upsert_embedding_model.return_value = 33
    embedding.upsert_commodity_embedding.return_value = 44
    monkeypatch.setattr(module, "CatalogRepository", lambda conn: catalog)
    monkeypatch.setattr(module, "EmbeddingRepository", lambda conn: embedding)
    conn = MagicMock()
    conn.transaction.side_effect = lambda: nullcontext()
    model = model or fake_model()
    return EmbeddingImporter(conn, model, batch_size=batch_size), catalog, embedding, model


def test_single_import_uses_core_text_builder_and_source_hash(monkeypatch, commodity_record):
    importer, _, repository, model = make_importer(monkeypatch)
    assert importer.import_commodity(commodity_record) == 44
    texts = model.encode_batch.call_args.args[0]
    assert len(texts) == 1
    assert "m³" in texts[0]  # Core TextBuilder includes the unit.
    assert "Füll- und Unbewehrte Beton" in texts[0]
    repository.upsert_embedding_model.assert_called_once_with(
        name="test-model", version="test-v1", dimension=3, distance_metric="cosine"
    )
    args = repository.upsert_commodity_embedding.call_args.kwargs
    assert args["commodity_id"] == 1
    assert args["model_id"] == 33
    assert args["embedding"] == [1.0, 0.0, 0.0]
    assert args["source_hash"] == hashlib.sha256(texts[0].encode("utf-8")).hexdigest()


def test_batch_is_chunked_and_keeps_order(monkeypatch, commodity_record):
    from dataclasses import replace

    importer, catalog, repository, model = make_importer(monkeypatch, batch_size=2)
    catalog.read_commodities.return_value = [
        replace(commodity_record, id=i, code=f"C{i}") for i in range(1, 6)
    ]
    assert importer.import_commodities(data_source_id=9) == 5
    assert [len(call.args[0]) for call in model.encode_batch.call_args_list] == [2, 2, 1]
    assert [call.kwargs["commodity_id"] for call in repository.upsert_commodity_embedding.call_args_list] == [1, 2, 3, 4, 5]
    repository.upsert_embedding_model.assert_called_once()


def test_no_commodities_does_not_call_encoder(monkeypatch):
    importer, catalog, _, model = make_importer(monkeypatch)
    catalog.read_commodities.return_value = []
    assert importer.import_commodities(data_source_id=1) == 0
    model.encode_batch.assert_not_called()


def test_invalid_batch_size(monkeypatch):
    with pytest.raises(ValueError, match="batch_size"):
        make_importer(monkeypatch, batch_size=0)


def test_invalid_data_source(monkeypatch):
    importer, catalog, _, _ = make_importer(monkeypatch)
    with pytest.raises(ValueError, match="data_source_id"):
        importer.import_commodities(data_source_id=0)
    catalog.read_commodities.assert_not_called()


def test_mismatched_embedding_count_fails_before_writes(monkeypatch, commodity_record):
    model = fake_model()
    model.encode_batch.return_value = []
    model.encode_batch.side_effect = None
    importer, _, repository, _ = make_importer(monkeypatch, model=model)
    with pytest.raises(ValueError, match="Embedding count"):
        importer.import_commodity(commodity_record)
    repository.upsert_commodity_embedding.assert_not_called()
