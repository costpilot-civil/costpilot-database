from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from src.importing.catalog_importer import CatalogImporter


def make_importer(monkeypatch):
    from src.importing import catalog_importer as module

    repo = MagicMock()
    repo.upsert_product_group.return_value = 10
    repo.upsert_commodity_group.side_effect = [20, 21]
    repo.upsert_commodity.return_value = 30
    monkeypatch.setattr(module, "CatalogRepository", lambda conn: repo)
    conn = MagicMock()
    conn.transaction.side_effect = lambda: nullcontext()
    return CatalogImporter(conn), repo, conn


def test_catalog_import_orders_groups_and_replaces_prices(monkeypatch, sample_catalog):
    importer, repo, conn = make_importer(monkeypatch)
    result = importer.import_catalog(data=sample_catalog, data_source_id=7)

    assert (result.product_groups, result.commodity_groups, result.commodities) == (1, 2, 1)
    assert (result.commodity_prices, result.estimate_prices, result.total_records) == (1, 1, 6)
    groups = repo.upsert_commodity_group.call_args_list
    assert groups[0].kwargs["code"] == "620"
    assert groups[1].kwargs["code"] == "6200011"
    assert groups[1].kwargs["parent_id"] == 20
    assert groups[1].kwargs["product_group_id"] == 10
    assert repo.upsert_commodity.call_args.kwargs["commodity_group_id"] == 21
    repo.delete_commodity_prices.assert_called_once_with(commodity_id=30)
    repo.delete_estimate_prices.assert_called_once_with(commodity_id=30)
    assert repo.insert_commodity_price.call_count == 1
    assert repo.insert_estimate_price.call_count == 1
    conn.transaction.assert_called_once()


def test_catalog_upsert_is_repeatable(monkeypatch, sample_catalog):
    importer, repo, _ = make_importer(monkeypatch)
    importer.import_catalog(data=sample_catalog, data_source_id=7)
    repo.upsert_commodity_group.side_effect = [20, 21]
    importer.import_catalog(data=sample_catalog, data_source_id=7)
    assert repo.upsert_commodity.call_count == 2
    assert repo.delete_commodity_prices.call_count == 2


def test_rejects_invalid_source_id(monkeypatch, sample_catalog):
    importer, repo, _ = make_importer(monkeypatch)
    with pytest.raises(ValueError, match="data_source_id"):
        importer.import_catalog(data=sample_catalog, data_source_id=0)
    repo.upsert_commodity.assert_not_called()


def test_rejects_duplicate_commodity_code(monkeypatch, sample_catalog):
    importer, repo, _ = make_importer(monkeypatch)
    sample_catalog.commodities.append(replace(sample_catalog.commodities[0]))
    with pytest.raises(ValueError, match="Duplicate commodity code"):
        importer.import_catalog(data=sample_catalog, data_source_id=7)
    repo.upsert_product_group.assert_not_called()


def test_rejects_cycle_in_group_hierarchy(monkeypatch, sample_catalog):
    importer, _, _ = make_importer(monkeypatch)
    sample_catalog.commodity_groups[0].parent_code = "6200011"
    with pytest.raises(ValueError, match="Cycle detected"):
        importer.import_catalog(data=sample_catalog, data_source_id=7)


def test_rejects_missing_parent_group(monkeypatch, sample_catalog):
    importer, _, _ = make_importer(monkeypatch)
    sample_catalog.commodity_groups[1].parent_code = "NOT_FOUND"
    with pytest.raises(ValueError, match="does not exist"):
        importer.import_catalog(data=sample_catalog, data_source_id=7)


def test_rejects_unknown_commodity_group(monkeypatch, sample_catalog):
    importer, _, _ = make_importer(monkeypatch)
    sample_catalog.commodities[0].commodity_group_code = "MISSING"
    with pytest.raises(ValueError, match="references unknown commodity group"):
        importer.import_catalog(data=sample_catalog, data_source_id=7)
