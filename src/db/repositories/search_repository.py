import json

from psycopg import Connection


class SearchRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def upsert_commodity_search(
        self,
        *,
        commodity_id: int,
        material_type: str | None,
        normalized_unit: str | None,
        attributes: dict[str, object],
        search_text: str,
    ) -> None:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO commodity_search (
                    commodity_id,
                    material_type,
                    normalized_unit,
                    attributes,
                    search_text
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s::jsonb,
                    %s
                )
                ON CONFLICT (commodity_id)
                DO UPDATE SET
                    material_type = EXCLUDED.material_type,
                    normalized_unit = EXCLUDED.normalized_unit,
                    attributes = EXCLUDED.attributes,
                    search_text = EXCLUDED.search_text;
                """,
                (
                    commodity_id,
                    material_type,
                    normalized_unit,
                    json.dumps(attributes),
                    search_text,
                ),
            )
