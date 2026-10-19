from __future__ import annotations

import hashlib
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.pipelines.catalog_import_pipeline import CatalogImportPipeline


def setup_pipeline(monkeypatch):
    from src.pipelines import catalog_import_pipeline as module

    repository = MagicMock()
    repository.upsert_data_source.return_value = 8
    repository.create_import_log.return_value = 9
    parser = MagicMock()
    parser.parse.return_value = SimpleNamespace(product_groups=[], commodity_groups=[], commodities=[])
    importer = MagicMock()
    importer.import_catalog.return_value = SimpleNamespace(total_records=5)
    monkeypatch.setattr(module, "ImportRepository", lambda conn: repository)
    monkeypatch.setattr(module, "ArticleXmlParser", lambda: parser)
    monkeypatch.setattr(module, "CatalogImporter", lambda conn: importer)
    connector = MagicMock()
    connector.connect.side_effect = lambda: nullcontext(MagicMock())
    return CatalogImportPipeline(connector), repository, parser, importer


def run(pipeline, file_path):
    return pipeline.run(
        file_path=file_path,
        source_code="test-catalog",
        source_name="Test catalog",
        source_type="ITWO_XML",
    )


def test_success_records_sha256_and_returns_ids(monkeypatch, sample_xml):
    pipeline, repository, parser, importer = setup_pipeline(monkeypatch)
    result = run(pipeline, sample_xml)
    assert result.data_source_id == 8
    assert result.import_log_id == 9
    assert result.import_result.total_records == 5
    assert repository.create_import_log.call_args.kwargs["file_hash"] == hashlib.sha256(sample_xml.read_bytes()).hexdigest()
    parser.parse.assert_called_once_with(sample_xml)
    importer.import_catalog.assert_called_once_with(data=parser.parse.return_value, data_source_id=8)
    repository.mark_import_succeeded.assert_called_once_with(
        import_log_id=9, records_total=5, records_imported=5
    )
    repository.mark_import_failed.assert_not_called()


def test_parser_failure_is_logged_and_re_raised(monkeypatch, sample_xml):
    pipeline, repository, parser, importer = setup_pipeline(monkeypatch)
    parser.parse.side_effect = ValueError("Bad XML")
    with pytest.raises(ValueError, match="Bad XML"):
        run(pipeline, sample_xml)
    repository.mark_import_failed.assert_called_once_with(import_log_id=9, error_message="Bad XML")
    repository.mark_import_succeeded.assert_not_called()
    importer.import_catalog.assert_not_called()


def test_importer_failure_is_logged(monkeypatch, sample_xml):
    pipeline, repository, _, importer = setup_pipeline(monkeypatch)
    importer.import_catalog.side_effect = RuntimeError("write failed")
    with pytest.raises(RuntimeError, match="write failed"):
        run(pipeline, sample_xml)
    repository.mark_import_failed.assert_called_once_with(import_log_id=9, error_message="write failed")


def test_missing_file_creates_no_import_log(monkeypatch, tmp_path):
    pipeline, repository, _, _ = setup_pipeline(monkeypatch)
    with pytest.raises(FileNotFoundError):
        run(pipeline, tmp_path / "missing.xml")
    repository.create_import_log.assert_not_called()
