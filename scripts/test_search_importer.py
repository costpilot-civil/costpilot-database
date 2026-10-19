from scripts.test_structured_extraction import (
    create_material_extractor,
)
from src.database.connector import DBConnector
from src.importing.search_importer import SearchImporter

SOURCE_CODE = "itwo-article-catalog"


def read_data_source_id(
    conn,
    source_code: str,
) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM data_sources
            WHERE code = %s;
            """,
            (source_code,),
        )

        row = cursor.fetchone()

    if row is None:
        raise ValueError(f"Data source not found: {source_code}")

    return int(row[0])


def count_commodities(
    conn,
    data_source_id: int,
) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM commodities
            WHERE data_source_id = %s;
            """,
            (data_source_id,),
        )

        row = cursor.fetchone()

    assert row is not None
    return int(row[0])


def count_search_records(
    conn,
    data_source_id: int,
) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM commodity_search AS cs
            JOIN commodities AS c
                ON c.id = cs.commodity_id
            WHERE c.data_source_id = %s;
            """,
            (data_source_id,),
        )

        row = cursor.fetchone()

    assert row is not None
    return int(row[0])


def main() -> None:
    connector = DBConnector()
    extractor = create_material_extractor()

    with connector.connect() as conn:
        try:
            data_source_id = read_data_source_id(
                conn,
                SOURCE_CODE,
            )

            total = count_commodities(conn, data_source_id)

            assert total > 0

            importer = SearchImporter(
                conn=conn,
                extractor=extractor,
            )

            print(f"Total commodities: {total}")

            # First import
            imported = importer.import_commodities(
                data_source_id=data_source_id,
            )

            search_count = count_search_records(
                conn,
                data_source_id,
            )

            assert imported == total
            assert search_count == total

            print(f"First import: {imported}")

            # Repeat import
            imported_again = importer.import_commodities(
                data_source_id=data_source_id,
            )

            search_count_again = count_search_records(
                conn,
                data_source_id,
            )

            assert imported_again == total
            assert search_count_again == total

            print(f"Second import: {imported_again}")

            # Verify search data
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM commodity_search AS cs
                    JOIN commodities AS c
                        ON c.id = cs.commodity_id
                    WHERE c.data_source_id = %s
                      AND (
                          cs.search_text = ''
                          OR cs.search_vector IS NULL
                      );
                    """,
                    (data_source_id,),
                )

                row = cursor.fetchone()

            assert row is not None
            assert row[0] == 0

            print("Search data verification passed.")

        finally:
            conn.rollback()
            print("Transaction rolled back.")

    print("Batch import test passed.")


if __name__ == "__main__":
    main()
