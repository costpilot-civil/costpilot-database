from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from psycopg import Connection

from src.importing.models import (
    ParsedArticleData,
    ParsedCommodityGroup,
    ParsedCommodityPrice,
    ParsedEstimatePrice,
)
from src.repositories.catalog_repository import CatalogRepository


@dataclass(frozen=True)
class CatalogImportResult:
    product_groups: int
    commodity_groups: int
    commodities: int
    commodity_prices: int
    estimate_prices: int

    @property
    def total_records(self) -> int:
        return (
            self.product_groups
            + self.commodity_groups
            + self.commodities
            + self.commodity_prices
            + self.estimate_prices
        )


class CatalogImporter:
    def __init__(
        self,
        conn: Connection,
    ) -> None:
        self._conn = conn
        self._repository = CatalogRepository(conn)

    def import_catalog(
        self,
        *,
        data: ParsedArticleData,
        data_source_id: int,
    ) -> CatalogImportResult:
        if data_source_id <= 0:
            raise ValueError("data_source_id must be greater than 0.")

        self._validate_unique_codes(
            data.product_groups,
            entity_name="product group",
        )

        self._validate_unique_codes(
            data.commodity_groups,
            entity_name="commodity group",
        )

        self._validate_unique_codes(
            data.commodities,
            entity_name="commodity",
        )

        with self._conn.transaction():
            product_group_ids = self._import_product_groups(
                data=data,
                data_source_id=data_source_id,
            )

            commodity_group_ids = self._import_commodity_groups(
                data=data,
                data_source_id=data_source_id,
                product_group_ids=product_group_ids,
            )

            (
                commodity_count,
                commodity_price_count,
                estimate_price_count,
            ) = self._import_commodities(
                data=data,
                data_source_id=data_source_id,
                commodity_group_ids=commodity_group_ids,
            )

        return CatalogImportResult(
            product_groups=len(data.product_groups),
            commodity_groups=len(data.commodity_groups),
            commodities=commodity_count,
            commodity_prices=commodity_price_count,
            estimate_prices=estimate_price_count,
        )

    def _import_product_groups(
        self,
        *,
        data: ParsedArticleData,
        data_source_id: int,
    ) -> dict[str, int]:
        product_group_ids: dict[str, int] = {}

        for product_group in data.product_groups:
            product_group_id = self._repository.upsert_product_group(
                data_source_id=data_source_id,
                code=product_group.code,
                name=product_group.name,
            )

            product_group_ids[product_group.code] = product_group_id

        return product_group_ids

    def _import_commodity_groups(
        self,
        *,
        data: ParsedArticleData,
        data_source_id: int,
        product_group_ids: dict[str, int],
    ) -> dict[str, int]:
        groups_by_code = {group.code: group for group in data.commodity_groups}

        commodity_group_ids: dict[str, int] = {}
        visiting: set[str] = set()

        def import_group(code: str) -> int:
            existing_id = commodity_group_ids.get(code)

            if existing_id is not None:
                return existing_id

            group = groups_by_code.get(code)

            if group is None:
                raise ValueError(
                    f"Commodity group '{code}' was referenced "
                    "but does not exist in parsed data."
                )

            if code in visiting:
                raise ValueError(
                    f"Cycle detected in commodity group hierarchy at '{code}'."
                )

            visiting.add(code)

            try:
                parent_id = self._resolve_parent_group_id(
                    group=group,
                    import_group=import_group,
                )

                product_group_id = self._resolve_product_group_id(
                    group=group,
                    product_group_ids=product_group_ids,
                )

                group_id = self._repository.upsert_commodity_group(
                    data_source_id=data_source_id,
                    code=group.code,
                    description=group.description,
                    parent_id=parent_id,
                    source_ref=group.source_ref,
                    cost_code=group.cost_code,
                    unit=group.unit,
                    discount=group.discount,
                    wastage=group.wastage,
                    estimation_factor=(group.estimation_factor),
                    regie_factor=group.regie_factor,
                    addition_1=group.addition_1,
                    addition_2=group.addition_2,
                    addition_3=group.addition_3,
                    addition_4=group.addition_4,
                    remarks=group.remarks,
                    product_group_id=product_group_id,
                    fixed_hours=group.fixed_hours,
                )

                commodity_group_ids[group.code] = group_id

                return group_id

            finally:
                visiting.remove(code)

        for commodity_group in data.commodity_groups:
            import_group(commodity_group.code)

        return commodity_group_ids

    def _import_commodities(
        self,
        *,
        data: ParsedArticleData,
        data_source_id: int,
        commodity_group_ids: dict[str, int],
    ) -> tuple[int, int, int]:
        commodity_count = 0
        commodity_price_count = 0
        estimate_price_count = 0

        for commodity in data.commodities:
            commodity_group_id = commodity_group_ids.get(commodity.commodity_group_code)

            if commodity_group_id is None:
                raise ValueError(
                    f"Commodity '{commodity.code}' "
                    "references unknown commodity group "
                    f"'{commodity.commodity_group_code}'."
                )

            commodity_id = self._repository.upsert_commodity(
                data_source_id=data_source_id,
                code=commodity.code,
                description=commodity.description,
                commodity_group_id=(commodity_group_id),
                source_ref=commodity.source_ref,
                unit=commodity.unit,
                cost_code=commodity.cost_code,
                cost_code_unit=(commodity.cost_code_unit),
                weight=commodity.weight,
                weight_unit=commodity.weight_unit,
                volume=commodity.volume,
                volume_unit=commodity.volume_unit,
                addition_1=commodity.addition_1,
                addition_2=commodity.addition_2,
                addition_3=commodity.addition_3,
                addition_4=commodity.addition_4,
                remarks=commodity.remarks,
                external_price_update=(commodity.external_price_update),
                selected=commodity.selected,
                fixed_hours=commodity.fixed_hours,
                change_date=commodity.change_date,
                change_user=commodity.change_user,
            )

            commodity_count += 1

            commodity_price_count += self._replace_commodity_prices(
                commodity_id=commodity_id,
                prices=commodity.prices,
            )

            estimate_price_count += self._replace_estimate_prices(
                commodity_id=commodity_id,
                prices=commodity.estimate_prices,
            )

        return (
            commodity_count,
            commodity_price_count,
            estimate_price_count,
        )

    def _replace_commodity_prices(
        self,
        *,
        commodity_id: int,
        prices: list[ParsedCommodityPrice],
    ) -> int:
        self._repository.delete_commodity_prices(
            commodity_id=commodity_id,
        )

        for price in prices:
            self._repository.insert_commodity_price(
                commodity_id=commodity_id,
                unit_price=price.unit_price,
                currency=price.currency,
                discount=price.discount,
                freight_costs=price.freight_costs,
                miscellaneous=price.miscellaneous,
                wastage=price.wastage,
                modified_date=price.modified_date,
                modified_user=price.modified_user,
            )

        return len(prices)

    def _replace_estimate_prices(
        self,
        *,
        commodity_id: int,
        prices: list[ParsedEstimatePrice],
    ) -> int:
        self._repository.delete_estimate_prices(
            commodity_id=commodity_id,
        )

        for price in prices:
            self._repository.insert_estimate_price(
                commodity_id=commodity_id,
                price_type=price.price_type,
                factor=price.factor,
                price=price.price,
                currency=price.currency,
                modified_date=price.modified_date,
                modified_user=price.modified_user,
                fixed_price=price.fixed_price,
            )

        return len(prices)

    @staticmethod
    def _resolve_parent_group_id(
        *,
        group: ParsedCommodityGroup,
        import_group: Callable[[str], int],
    ) -> int | None:
        if group.parent_code is None:
            return None

        return import_group(group.parent_code)

    @staticmethod
    def _resolve_product_group_id(
        *,
        group: ParsedCommodityGroup,
        product_group_ids: dict[str, int],
    ) -> int | None:
        if group.product_group_code is None:
            return None

        product_group_id = product_group_ids.get(group.product_group_code)

        if product_group_id is None:
            raise ValueError(
                f"Commodity group '{group.code}' "
                "references unknown product group "
                f"'{group.product_group_code}'."
            )

        return product_group_id

    @staticmethod
    def _validate_unique_codes(
        items: list,
        *,
        entity_name: str,
    ) -> None:
        seen: set[str] = set()

        for item in items:
            if item.code in seen:
                raise ValueError(
                    f"Duplicate {entity_name} code '{item.code}' in parsed catalog."
                )

            seen.add(item.code)
