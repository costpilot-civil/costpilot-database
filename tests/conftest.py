"""Shared, offline-safe fixtures for CostPilot Database tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.models.commodity_record import CommodityRecord
from src.parsers.article_xml_parser import ArticleXmlParser


@pytest.fixture
def commodity_record() -> CommodityRecord:
    return CommodityRecord(
        id=1,
        code="Beton C8/10",
        description="Beton C8/10-X0 Sauberkeitsschicht",
        unit="m³",
        cost_code="62011",
        group_code="6200011",
        group_description="Füll- und Unbewehrte Beton",
    )


@pytest.fixture
def sample_xml(tmp_path: Path) -> Path:
    path = tmp_path / "article.xml"
    path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Project>
  <CommodityGroup>
    <CommodityGroupData>
      <CommodityGroupID>620</CommodityGroupID>
      <CommodityGroupDescription>Rohbau</CommodityGroupDescription>
      <ProductGroup>Rohbau</ProductGroup>
      <CCG Id="62" Desc="Rohbau" />
    </CommodityGroupData>
    <CommodityGroup>
      <CommodityGroupData>
        <CommodityGroupID>6200011</CommodityGroupID>
        <CommodityGroupsHierarchy>620</CommodityGroupsHierarchy>
        <CommodityGroupDescription>Füll- und Unbewehrte Beton</CommodityGroupDescription>
      </CommodityGroupData>
      <Commodity>
        <CommodityData>
          <CommodityID>Beton C8/10</CommodityID>
          <CommodityGroupID>6200011</CommodityGroupID>
          <CommodityDescription>Beton C8/10-X0 Sauberkeitsschicht</CommodityDescription>
          <UoM>m³</UoM>
          <CostCode>62011</CostCode>
          <SelectedCommodity>true</SelectedCommodity>
        </CommodityData>
        <CommodityPrices>
          <CommodityPrice>
            <PrUnit>12.50</PrUnit>
            <CUR>EUR</CUR>
          </CommodityPrice>
        </CommodityPrices>
        <EstimatePrices>
          <EstimatePrice Typ="MATERIAL">
            <Price>13.00</Price>
            <PriceCUR>EUR</PriceCUR>
          </EstimatePrice>
        </EstimatePrices>
      </Commodity>
    </CommodityGroup>
  </CommodityGroup>
</Project>
""",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def sample_catalog(sample_xml: Path):
    return ArticleXmlParser().parse(sample_xml)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: requires explicitly enabled PostgreSQL round-trip tests"
    )
