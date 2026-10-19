from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.importing.search_importer import SearchImporter


def make_importer(monkeypatch, extractor):
    from src.importing import search_importer as module

    catalog = MagicMock()
    search = MagicMock()
    monkeypatch.setattr(module, "CatalogRepository", lambda conn: catalog)
    monkeypatch.setattr(module, "SearchRepository", lambda conn: search)
    conn = MagicMock()
    conn.transaction.side_effect = lambda: nullcontext()
    return SearchImporter(conn, extractor), catalog, search


def test_extract_and_upsert(monkeypatch, commodity_record):
    extractor = MagicMock()
    extractor.extract.return_value = SimpleNamespace(
        material_type="concrete",
        core_attributes={"strength_class": "C8/10"},
        supplementary_attributes={"exposure_class": {"x0": "X0"}},
    )
    importer, _, search = make_importer(monkeypatch, extractor)
    importer.import_commodity(commodity_record)
    text = extractor.extract.call_args.args[0]
    assert "Beton C8/10" in text
    assert "Füll- und Unbewehrte Beton" in text
    assert "m³" not in text  # Search and embedding texts intentionally differ.
    assert search.upsert_commodity_search.call_args.kwargs == {
        "commodity_id": 1,
        "material_type": "concrete",
        "normalized_unit": None,
        "attributes": {"strength_class": "C8/10", "exposure_class": {"x0": "X0"}},
        "search_text": text,
    }


def test_unknown_material_still_writes_search_text(monkeypatch, commodity_record):
    extractor = MagicMock()
    extractor.extract.return_value = None
    importer, _, search = make_importer(monkeypatch, extractor)
    importer.import_commodity(commodity_record)
    kwargs = search.upsert_commodity_search.call_args.kwargs
    assert kwargs["material_type"] is None
    assert kwargs["attributes"] == {}
    assert kwargs["search_text"]


def test_duplicate_attributes_rejected(monkeypatch, commodity_record):
    extractor = MagicMock()
    extractor.extract.return_value = SimpleNamespace(
        material_type="concrete",
        core_attributes={"strength": "C8/10"},
        supplementary_attributes={"strength": "C20/25"},
    )
    importer, _, search = make_importer(monkeypatch, extractor)
    with pytest.raises(ValueError, match="Duplicate material attributes"):
        importer.import_commodity(commodity_record)
    search.upsert_commodity_search.assert_not_called()


def test_batch_reads_from_catalog_and_imports(monkeypatch, commodity_record):
    extractor = MagicMock()
    extractor.extract.return_value = None
    importer, catalog, search = make_importer(monkeypatch, extractor)
    catalog.read_commodities.return_value = [commodity_record, commodity_record]
    assert importer.import_commodities(data_source_id=2) == 2
    catalog.read_commodities.assert_called_once_with(data_source_id=2)
    assert search.upsert_commodity_search.call_count == 2


def test_invalid_source_id(monkeypatch):
    importer, catalog, _ = make_importer(monkeypatch, MagicMock())
    with pytest.raises(ValueError, match="data_source_id"):
        importer.import_commodities(data_source_id=-1)
    catalog.read_commodities.assert_not_called()
