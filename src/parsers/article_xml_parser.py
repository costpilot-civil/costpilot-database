import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree.ElementTree import Element

from src.importing.models import (
    ParsedArticleData,
    ParsedCommodity,
    ParsedCommodityGroup,
    ParsedCommodityPrice,
    ParsedEstimatePrice,
    ParsedProductGroup,
)


class ArticleXmlParser:
    def parse(
        self,
        file_path: str | Path,
    ) -> ParsedArticleData:
        path = Path(file_path)

        if not path.is_file():
            raise FileNotFoundError(f"Article XML file not found: {path}")

        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid XML file: {path}") from exc

        root = tree.getroot()

        if root.tag != "Project":
            raise ValueError(
                f"Unexpected root element: '{root.tag}'. Expected 'Project'."
            )

        product_groups: dict[str, ParsedProductGroup] = {}
        commodity_groups: list[ParsedCommodityGroup] = []
        commodities: list[ParsedCommodity] = []

        for group_element in root.findall("CommodityGroup"):
            self._parse_group(
                group_element=group_element,
                parent_code=None,
                inherited_product_group_code=None,
                product_groups=product_groups,
                commodity_groups=commodity_groups,
                commodities=commodities,
            )

        return ParsedArticleData(
            product_groups=list(product_groups.values()),
            commodity_groups=commodity_groups,
            commodities=commodities,
        )

    def _parse_group(
        self,
        *,
        group_element: Element,
        parent_code: str | None,
        inherited_product_group_code: str | None,
        product_groups: dict[str, ParsedProductGroup],
        commodity_groups: list[ParsedCommodityGroup],
        commodities: list[ParsedCommodity],
    ) -> None:
        group_data = group_element.find("CommodityGroupData")

        if group_data is None:
            raise ValueError("CommodityGroup without CommodityGroupData.")

        code = self._required_text(
            group_data,
            "CommodityGroupID",
        )

        declared_parent_code = self._text(
            group_data,
            "CommodityGroupsHierarchy",
        )

        if (
            declared_parent_code is not None
            and parent_code is not None
            and declared_parent_code != parent_code
        ):
            raise ValueError(
                f"Commodity group '{code}' has inconsistent "
                f"parent references: XML hierarchy says "
                f"'{declared_parent_code}', but nesting says "
                f"'{parent_code}'."
            )

        resolved_parent_code = (
            declared_parent_code if declared_parent_code is not None else parent_code
        )

        own_product_group_code = self._register_product_group(
            data_element=group_data,
            product_groups=product_groups,
        )

        product_group_code = own_product_group_code or inherited_product_group_code

        commodity_groups.append(
            ParsedCommodityGroup(
                code=code,
                description=self._text(
                    group_data,
                    "CommodityGroupDescription",
                ),
                parent_code=resolved_parent_code,
                product_group_code=product_group_code,
                source_ref=self._attribute(
                    group_data,
                    "Xref",
                ),
                cost_code=self._text(
                    group_data,
                    "CostCode",
                ),
                unit=self._text(
                    group_data,
                    "UoM",
                ),
                discount=self._decimal(
                    group_data,
                    "Discount",
                ),
                wastage=self._decimal(
                    group_data,
                    "Wastage",
                ),
                estimation_factor=self._decimal(
                    group_data,
                    "EstimationFactor",
                ),
                regie_factor=self._decimal(
                    group_data,
                    "RegieFaktor",
                ),
                addition_1=self._text(
                    group_data,
                    "Addition1",
                ),
                addition_2=self._text(
                    group_data,
                    "Addition2",
                ),
                addition_3=self._text(
                    group_data,
                    "Addition3",
                ),
                addition_4=self._text(
                    group_data,
                    "Addition4",
                ),
                remarks=self._text(
                    group_data,
                    "Remarks",
                ),
                fixed_hours=self._bool(
                    group_data,
                    "FixedHours",
                ),
            )
        )

        for commodity_element in group_element.findall("Commodity"):
            commodity = self._parse_commodity(
                commodity_element=commodity_element,
                current_group_code=code,
                inherited_product_group_code=(product_group_code),
                product_groups=product_groups,
            )

            commodities.append(commodity)

        for child_group in group_element.findall("CommodityGroup"):
            self._parse_group(
                group_element=child_group,
                parent_code=code,
                inherited_product_group_code=(product_group_code),
                product_groups=product_groups,
                commodity_groups=commodity_groups,
                commodities=commodities,
            )

    def _parse_commodity(
        self,
        *,
        commodity_element: Element,
        current_group_code: str,
        inherited_product_group_code: str | None,
        product_groups: dict[str, ParsedProductGroup],
    ) -> ParsedCommodity:
        commodity_data = commodity_element.find("CommodityData")

        if commodity_data is None:
            raise ValueError("Commodity without CommodityData.")

        code = self._required_text(
            commodity_data,
            "CommodityID",
        )

        declared_group_code = self._text(
            commodity_data,
            "CommodityGroupID",
        )

        if (
            declared_group_code is not None
            and declared_group_code != current_group_code
        ):
            raise ValueError(
                f"Commodity '{code}' references commodity "
                f"group '{declared_group_code}', but is nested "
                f"inside group '{current_group_code}'."
            )

        commodity_group_code = declared_group_code or current_group_code

        own_product_group_code = self._register_product_group(
            data_element=commodity_data,
            product_groups=product_groups,
        )

        product_group_code = own_product_group_code or inherited_product_group_code

        return ParsedCommodity(
            code=code,
            description=self._text(
                commodity_data,
                "CommodityDescription",
            ),
            commodity_group_code=commodity_group_code,
            product_group_code=product_group_code,
            source_ref=self._attribute(
                commodity_data,
                "Xref",
            ),
            unit=self._text(
                commodity_data,
                "UoM",
            ),
            cost_code=self._text(
                commodity_data,
                "CostCode",
            ),
            cost_code_unit=self._text(
                commodity_data,
                "CostCodeUoM",
            ),
            weight=self._decimal(
                commodity_data,
                "Weight",
            ),
            weight_unit=self._text(
                commodity_data,
                "WeightUoM",
            ),
            volume=self._decimal(
                commodity_data,
                "Volume",
            ),
            volume_unit=self._text(
                commodity_data,
                "VolumeUoM",
            ),
            addition_1=self._text(
                commodity_data,
                "Addition1",
            ),
            addition_2=self._text(
                commodity_data,
                "Addition2",
            ),
            addition_3=self._text(
                commodity_data,
                "Addition3",
            ),
            addition_4=self._text(
                commodity_data,
                "Addition4",
            ),
            remarks=self._text(
                commodity_data,
                "Remarks",
            ),
            external_price_update=self._bool(
                commodity_data,
                "ExternalPriceUpdate",
            ),
            selected=self._bool(
                commodity_data,
                "SelectedCommodity",
            ),
            fixed_hours=self._bool(
                commodity_data,
                "FixedHours",
            ),
            change_date=self._date(
                commodity_data,
                "ChangeRestDate",
            ),
            change_user=self._text(
                commodity_data,
                "ChangeRestUser",
            ),
            prices=self._parse_commodity_prices(commodity_element),
            estimate_prices=self._parse_estimate_prices(commodity_element),
        )

    def _parse_commodity_prices(
        self,
        commodity_element: Element,
    ) -> list[ParsedCommodityPrice]:
        prices_element = commodity_element.find("CommodityPrices")

        if prices_element is None:
            return []

        prices: list[ParsedCommodityPrice] = []

        for price_element in prices_element.findall("CommodityPrice"):
            prices.append(
                ParsedCommodityPrice(
                    unit_price=self._required_decimal(
                        price_element,
                        "PrUnit",
                    ),
                    currency=self._required_text(
                        price_element,
                        "CUR",
                    ),
                    discount=self._decimal(
                        price_element,
                        "Discount",
                    ),
                    freight_costs=self._decimal(
                        price_element,
                        "FreightCosts",
                    ),
                    miscellaneous=self._decimal(
                        price_element,
                        "Miscellaneous",
                    ),
                    wastage=self._decimal(
                        price_element,
                        "Wastage",
                    ),
                    modified_date=self._date(
                        price_element,
                        "DateOfLastModification",
                    ),
                    modified_user=self._text(
                        price_element,
                        "UserOfLastModification",
                    ),
                )
            )

        return prices

    def _parse_estimate_prices(
        self,
        commodity_element: Element,
    ) -> list[ParsedEstimatePrice]:
        prices_element = commodity_element.find("EstimatePrices")

        if prices_element is None:
            return []

        prices: list[ParsedEstimatePrice] = []

        for price_element in prices_element.findall("EstimatePrice"):
            price_type = self._attribute(
                price_element,
                "Typ",
            )

            if price_type is None:
                raise ValueError("EstimatePrice is missing required 'Typ' attribute.")

            prices.append(
                ParsedEstimatePrice(
                    price_type=price_type,
                    factor=self._decimal(
                        price_element,
                        "Factor",
                    ),
                    price=self._required_decimal(
                        price_element,
                        "Price",
                    ),
                    currency=self._required_text(
                        price_element,
                        "PriceCUR",
                    ),
                    modified_date=self._date(
                        price_element,
                        "DateOfPriceModification",
                    ),
                    modified_user=self._text(
                        price_element,
                        "UserOfPriceModification",
                    ),
                    fixed_price=self._bool(
                        price_element,
                        "FixedPriceFlag",
                    ),
                )
            )

        return prices

    def _register_product_group(
        self,
        *,
        data_element: Element,
        product_groups: dict[str, ParsedProductGroup],
    ) -> str | None:
        product_group_name = self._text(
            data_element,
            "ProductGroup",
        )

        ccg_element = data_element.find("CCG")

        if ccg_element is None:
            if product_group_name is not None:
                raise ValueError(
                    "ProductGroup exists but corresponding CCG element is missing."
                )

            return None

        product_group_code = self._attribute(
            ccg_element,
            "Id",
        )

        ccg_description = self._attribute(
            ccg_element,
            "Desc",
        )

        if product_group_code is None:
            if product_group_name is not None or ccg_description is not None:
                raise ValueError("CCG element is missing required 'Id' attribute.")

            return None

        name = product_group_name or ccg_description or product_group_code

        existing = product_groups.get(product_group_code)

        if existing is not None:
            if existing.name != name:
                raise ValueError(
                    f"Product group '{product_group_code}' "
                    f"has conflicting names: "
                    f"'{existing.name}' and '{name}'."
                )

            return product_group_code

        product_groups[product_group_code] = ParsedProductGroup(
            code=product_group_code,
            name=name,
        )

        return product_group_code

    @classmethod
    def _required_text(
        cls,
        element: Element,
        tag: str,
    ) -> str:
        value = cls._text(element, tag)

        if value is None:
            raise ValueError(f"Missing required XML value '{tag}'.")

        return value

    @staticmethod
    def _text(
        element: Element,
        tag: str,
    ) -> str | None:
        child = element.find(tag)

        if child is None or child.text is None:
            return None

        value = child.text.strip()

        return value or None

    @staticmethod
    def _attribute(
        element: Element,
        name: str,
    ) -> str | None:
        value = element.get(name)

        if value is None:
            return None

        value = value.strip()

        return value or None

    @classmethod
    def _decimal(
        cls,
        element: Element,
        tag: str,
    ) -> Decimal | None:
        value = cls._text(element, tag)

        if value is None:
            return None

        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid decimal value for '{tag}': '{value}'.") from exc

    @classmethod
    def _required_decimal(
        cls,
        element: Element,
        tag: str,
    ) -> Decimal:
        value = cls._decimal(element, tag)

        if value is None:
            raise ValueError(f"Missing required decimal value '{tag}'.")

        return value

    @classmethod
    def _date(
        cls,
        element: Element,
        tag: str,
    ) -> date | None:
        value = cls._text(element, tag)

        if value is None:
            return None

        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"Invalid date value for '{tag}': '{value}'.") from exc

    @classmethod
    def _bool(
        cls,
        element: Element,
        tag: str,
    ) -> bool | None:
        value = cls._text(element, tag)

        if value is None:
            return None

        normalized = value.lower()

        if normalized in {"true", "1"}:
            return True

        if normalized in {"false", "0"}:
            return False

        raise ValueError(f"Invalid boolean value for '{tag}': '{value}'.")
