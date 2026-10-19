"""CLI wiring without loading real models or connecting to PostgreSQL."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from scripts import build_database as cli


def test_cli_requires_stage(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build_database"])
    with pytest.raises(SystemExit):
        cli.parse_args()


@pytest.mark.parametrize("stage", ["all", "catalog", "index"])
def test_cli_accepts_stages(monkeypatch, stage):
    monkeypatch.setattr(sys, "argv", ["build_database", stage])
    assert cli.parse_args().stage == stage


def test_relative_paths_are_based_on_project_root(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    assert (
        cli.resolve_path("config/models.yml")
        == (tmp_path / "config/models.yml").resolve()
    )


def test_model_yaml_is_used_without_real_model_load(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    model_dir = tmp_path / "models" / "bge-m3"
    model_dir.mkdir(parents=True)
    (config_dir / "models.yml").write_text(
        "embedding:\n  bge-m3:\n    name: BAAI/bge-m3\n    version: v1\n    path: ../models/bge-m3\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("MODEL_CONFIG_PATH", "./config/models.yml")
    sentence_transformer = MagicMock()
    monkeypatch.setattr(cli, "SentenceTransformer", sentence_transformer)
    adapter = MagicMock()
    monkeypatch.setattr(cli, "SentenceTransformerEmbedding", adapter)
    cli.create_embedding_model("bge-m3")
    sentence_transformer.assert_called_once_with(
        str(model_dir.resolve()), local_files_only=True
    )
    adapter.assert_called_once_with(
        model=sentence_transformer.return_value, name="BAAI/bge-m3", version="v1"
    )


def test_catalog_stage_only_does_not_load_models(monkeypatch, tmp_path):
    file_path = tmp_path / "catalog.xml"
    file_path.write_text("<Project />", encoding="utf-8")
    monkeypatch.setenv("CATALOG_XML_PATH", str(file_path))
    monkeypatch.setattr(sys, "argv", ["build_database", "catalog"])
    monkeypatch.setattr(cli, "DBConnector", MagicMock())
    mock_catalog = MagicMock()
    mock_catalog.return_value.run.return_value = SimpleNamespace(
        data_source_id=3, import_result=SimpleNamespace(total_records=1)
    )
    monkeypatch.setattr(cli, "CatalogImportPipeline", mock_catalog)
    mock_index = MagicMock()
    monkeypatch.setattr(cli, "SearchIndexPipeline", mock_index)
    cli.main()
    mock_catalog.return_value.run.assert_called_once()
    mock_index.assert_not_called()


def test_index_search_only_does_not_load_embedding(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["build_database", "index", "--index-part", "search"]
    )
    connector = MagicMock()
    monkeypatch.setattr(cli, "DBConnector", lambda: connector)
    monkeypatch.setattr(cli, "get_data_source_id", lambda **kwargs: 7)
    monkeypatch.setattr(cli, "create_material_extractor", MagicMock())
    load_embedding = MagicMock()
    monkeypatch.setattr(cli, "create_embedding_model", load_embedding)
    mock_index = MagicMock()
    mock_index.return_value.run.return_value = SimpleNamespace(
        search_records=1, embedding_records=None
    )
    monkeypatch.setattr(cli, "SearchIndexPipeline", mock_index)
    cli.main()
    load_embedding.assert_not_called()
    mock_index.return_value.run.assert_called_once_with(
        data_source_id=7, build_search=True, build_embeddings=False
    )
