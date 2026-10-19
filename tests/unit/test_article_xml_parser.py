from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.parsers.article_xml_parser import ArticleXmlParser


def test_parse_nested_catalog_with_prices(sample_catalog):
    data = sample_catalog
    assert [(x.code, x.name) for x in data.product_groups] == [("62", "Rohbau")]
    assert len(data.commodity_groups) == 2
    assert data.commodity_groups[0].parent_code is None
    assert data.commodity_groups[1].parent_code == "620"
    assert data.commodity_groups[1].product_group_code == "62"
    assert len(data.commodities) == 1
    commodity = data.commodities[0]
    assert commodity.code == "Beton C8/10"
    assert commodity.commodity_group_code == "6200011"
    assert commodity.selected is True
    assert commodity.unit == "m³"
    assert commodity.prices[0].unit_price == Decimal("12.50")
    assert commodity.estimate_prices[0].price == Decimal("13.00")
    assert commodity.estimate_prices[0].price_type == "MATERIAL"


@pytest.mark.parametrize(
    ("xml", "message"),
    [
        ("<Bad />", "Unexpected root"),
        ("<Project><CommodityGroup /></Project>", "without CommodityGroupData"),
        (
            "<Project><CommodityGroup><CommodityGroupData>"
            "<CommodityGroupDescription>X</CommodityGroupDescription>"
            "</CommodityGroupData></CommodityGroup></Project>",
            "Missing required XML value 'CommodityGroupID'",
        ),
        (
            "<Project><CommodityGroup><CommodityGroupData>"
            "<CommodityGroupID>G</CommodityGroupID>"
            "</CommodityGroupData><Commodity><CommodityData>"
            "<CommodityID>C</CommodityID><CommodityGroupID>OTHER</CommodityGroupID>"
            "</CommodityData></Commodity></CommodityGroup></Project>",
            "references commodity group",
        ),
    ],
)
def test_parser_rejects_invalid_structure(tmp_path: Path, xml: str, message: str):
    path = tmp_path / "invalid.xml"
    path.write_text(xml, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        ArticleXmlParser().parse(path)


def test_parser_rejects_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ArticleXmlParser().parse(tmp_path / "missing.xml")


def test_parser_rejects_malformed_xml(tmp_path: Path):
    path = tmp_path / "broken.xml"
    path.write_text("<Project>", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid XML"):
        ArticleXmlParser().parse(path)


@pytest.mark.parametrize("raw,expected", [("true", True), ("0", False), ("FALSE", False)])
def test_boolean_helper(raw: str, expected: bool):
    import xml.etree.ElementTree as ET

    element = ET.fromstring(f"<node><Flag>{raw}</Flag></node>")
    assert ArticleXmlParser._bool(element, "Flag") is expected


def test_invalid_boolean_decimal_date():
    import xml.etree.ElementTree as ET

    element = ET.fromstring("<node><Flag>maybe</Flag><Price>NaN?</Price><When>yesterday</When></node>")
    with pytest.raises(ValueError, match="Invalid boolean"):
        ArticleXmlParser._bool(element, "Flag")
    with pytest.raises(ValueError, match="Invalid decimal"):
        ArticleXmlParser._decimal(element, "Price")
    with pytest.raises(ValueError, match="Invalid date"):
        ArticleXmlParser._date(element, "When")
    assert ArticleXmlParser._date(ET.fromstring("<node><When>2026-10-19</When></node>"), "When") == date(2026, 10, 19)
