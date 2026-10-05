from datetime import date
from decimal import Decimal

from psycopg import Connection


class CatalogRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def insert_product_group(
        self,
        *,
        data_source_id: int,
        code: str,
        name: str,
    ) -> int:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO product_groups (
                    data_source_id,
                    code,
                    name
                )
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (
                    data_source_id,
                    code,
                    name,
                ),
            )

            row = cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to insert product group.")

        return int(row[0])

    def insert_commodity_group(
        self,
        *,
        data_source_id: int,
        code: str,
        description: str | None,
        parent_id: int | None,
        source_ref: str | None,
        cost_code: str | None,
        unit: str | None,
        discount: Decimal | None,
        wastage: Decimal | None,
        estimation_factor: Decimal | None,
        regie_factor: Decimal | None,
        addition_1: str | None,
        addition_2: str | None,
        addition_3: str | None,
        addition_4: str | None,
        remarks: str | None,
        product_group_id: int | None,
        fixed_hours: bool | None,
    ) -> int:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO commodity_groups (
                    data_source_id,
                    code,
                    description,
                    parent_id,
                    source_ref,
                    cost_code,
                    unit,
                    discount,
                    wastage,
                    estimation_factor,
                    regie_factor,
                    addition_1,
                    addition_2,
                    addition_3,
                    addition_4,
                    remarks,
                    product_group_id,
                    fixed_hours
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                RETURNING id;
                """,
                (
                    data_source_id,
                    code,
                    description,
                    parent_id,
                    source_ref,
                    cost_code,
                    unit,
                    discount,
                    wastage,
                    estimation_factor,
                    regie_factor,
                    addition_1,
                    addition_2,
                    addition_3,
                    addition_4,
                    remarks,
                    product_group_id,
                    fixed_hours,
                ),
            )

            row = cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to insert commodity group.")

        return int(row[0])

    def insert_commodity(
        self,
        *,
        data_source_id: int,
        code: str,
        description: str | None,
        commodity_group_id: int,
        source_ref: str | None,
        unit: str | None,
        cost_code: str | None,
        cost_code_unit: str | None,
        weight: Decimal | None,
        weight_unit: str | None,
        volume: Decimal | None,
        volume_unit: str | None,
        addition_1: str | None,
        addition_2: str | None,
        addition_3: str | None,
        addition_4: str | None,
        remarks: str | None,
        external_price_update: bool | None,
        selected: bool | None,
        fixed_hours: bool | None,
        change_date: date | None,
        change_user: str | None,
    ) -> int:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO commodities (
                    data_source_id,
                    code,
                    description,
                    commodity_group_id,
                    source_ref,
                    unit,
                    cost_code,
                    cost_code_unit,
                    weight,
                    weight_unit,
                    volume,
                    volume_unit,
                    addition_1,
                    addition_2,
                    addition_3,
                    addition_4,
                    remarks,
                    external_price_update,
                    selected,
                    fixed_hours,
                    change_date,
                    change_user
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING id;
                """,
                (
                    data_source_id,
                    code,
                    description,
                    commodity_group_id,
                    source_ref,
                    unit,
                    cost_code,
                    cost_code_unit,
                    weight,
                    weight_unit,
                    volume,
                    volume_unit,
                    addition_1,
                    addition_2,
                    addition_3,
                    addition_4,
                    remarks,
                    external_price_update,
                    selected,
                    fixed_hours,
                    change_date,
                    change_user,
                ),
            )

            row = cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to insert commodity.")

        return int(row[0])

    def insert_commodity_price(
        self,
        *,
        commodity_id: int,
        unit_price: Decimal,
        currency: str,
        discount: Decimal | None,
        freight_costs: Decimal | None,
        miscellaneous: Decimal | None,
        wastage: Decimal | None,
        modified_date: date | None,
        modified_user: str | None,
    ) -> int:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO commodity_prices (
                    commodity_id,
                    unit_price,
                    currency,
                    discount,
                    freight_costs,
                    miscellaneous,
                    wastage,
                    modified_date,
                    modified_user
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING id;
                """,
                (
                    commodity_id,
                    unit_price,
                    currency,
                    discount,
                    freight_costs,
                    miscellaneous,
                    wastage,
                    modified_date,
                    modified_user,
                ),
            )

            row = cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to insert commodity price.")

        return int(row[0])

    def insert_estimate_price(
        self,
        *,
        commodity_id: int,
        price_type: str,
        factor: Decimal | None,
        price: Decimal,
        currency: str,
        modified_date: date | None,
        modified_user: str | None,
        fixed_price: bool | None,
    ) -> int:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO estimate_prices (
                    commodity_id,
                    price_type,
                    factor,
                    price,
                    currency,
                    modified_date,
                    modified_user,
                    fixed_price
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING id;
                """,
                (
                    commodity_id,
                    price_type,
                    factor,
                    price,
                    currency,
                    modified_date,
                    modified_user,
                    fixed_price,
                ),
            )

            row = cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to insert estimate price.")

        return int(row[0])
