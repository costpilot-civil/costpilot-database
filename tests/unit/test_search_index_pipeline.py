from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import MagicMock

import pytest

from src.pipelines.search_index_pipeline import SearchIndexPipeline


def setup_pipeline(monkeypatch, search=True, embedding=True):
    from src.pipelines import search_index_pipeline as module

    search_importer = MagicMock()
    search_importer.import_commodities.return_value = 3
    embedding_importer = MagicMock()
    embedding_importer.import_commodities.return_value = 4
    search_factory = MagicMock(return_value=search_importer)
    embedding_factory = MagicMock(return_value=embedding_importer)
    register = MagicMock()
    monkeypatch.setattr(module, "SearchImporter", search_factory)
    monkeypatch.setattr(module, "EmbeddingImporter", embedding_factory)
    monkeypatch.setattr(module, "register_vector", register)
    connector = MagicMock()
    connector.connect.side_effect = lambda: nullcontext(MagicMock())
    extractor = MagicMock() if search else None
    model = MagicMock() if embedding else None
    pipeline = SearchIndexPipeline(connector, material_extractor=extractor, embedding_model=model, batch_size=8)
    return pipeline, connector, search_factory, embedding_factory, register


def test_full_index_runs_both(monkeypatch):
    pipeline, connector, search_factory, embedding_factory, register = setup_pipeline(monkeypatch)
    result = pipeline.run(data_source_id=5)
    assert (result.search_records, result.embedding_records) == (3, 4)
    assert connector.connect.call_count == 2
    search_factory.return_value.import_commodities.assert_called_once_with(data_source_id=5)
    embedding_factory.return_value.import_commodities.assert_called_once_with(data_source_id=5)
    assert embedding_factory.call_args.kwargs["batch_size"] == 8
    register.assert_called_once()


def test_search_only_does_not_load_pgvector(monkeypatch):
    pipeline, connector, _, embedding_factory, register = setup_pipeline(monkeypatch, embedding=False)
    result = pipeline.run(data_source_id=5, build_embeddings=False)
    assert result.search_records == 3 and result.embedding_records is None
    assert connector.connect.call_count == 1
    embedding_factory.assert_not_called()
    register.assert_not_called()


def test_embedding_only_does_not_create_search_importer(monkeypatch):
    pipeline, connector, search_factory, _, register = setup_pipeline(monkeypatch, search=False)
    result = pipeline.run(data_source_id=5, build_search=False)
    assert result.search_records is None and result.embedding_records == 4
    assert connector.connect.call_count == 1
    search_factory.assert_not_called()
    register.assert_called_once()


def test_validates_flags_and_missing_dependencies(monkeypatch):
    pipeline, connector, _, _, _ = setup_pipeline(monkeypatch, search=False, embedding=False)
    with pytest.raises(ValueError, match="data_source_id"):
        pipeline.run(data_source_id=0)
    with pytest.raises(ValueError, match="No indexing task"):
        pipeline.run(data_source_id=1, build_search=False, build_embeddings=False)
    with pytest.raises(ValueError, match="MaterialExtractor is required"):
        pipeline.run(data_source_id=1, build_embeddings=False)
    with pytest.raises(ValueError, match="EmbeddingModel is required"):
        pipeline.run(data_source_id=1, build_search=False)
    connector.connect.assert_not_called()


def test_rejects_invalid_batch_size(monkeypatch):
    with pytest.raises(ValueError, match="batch_size"):
        SearchIndexPipeline(MagicMock(), batch_size=0)
