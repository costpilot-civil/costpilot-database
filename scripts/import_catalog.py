import hashlib
from pathlib import Path

from src.database.connector import DBConnector
from src.importing.catalog_importer import CatalogImporter
from src.parsers.article_xml_parser import ArticleXmlParser
from src.repositories.import_repository import ImportRepository


def calculate_file_hash(
    file_path: Path,
) -> str:
    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def create_import_log(
    *,
    connector: DBConnector,
    source_code: str,
    source_name: str,
    source_type: str,
    file_path: Path,
    file_hash: str,
) -> tuple[int, int]:
    with connector.connect() as conn:
        repository = ImportRepository(conn)

        data_source_id = repository.upsert_data_source(
            code=source_code,
            name=source_name,
            source_type=source_type,
            description=None,
        )

        import_log_id = repository.create_import_log(
            data_source_id=data_source_id,
            file_name=file_path.name,
            file_hash=file_hash,
        )

    return data_source_id, import_log_id


def mark_import_succeeded(
    *,
    connector: DBConnector,
    import_log_id: int,
    records_total: int,
    records_imported: int,
) -> None:
    with connector.connect() as conn:
        repository = ImportRepository(conn)

        repository.mark_import_succeeded(
            import_log_id=import_log_id,
            records_total=records_total,
            records_imported=records_imported,
        )


def mark_import_failed(
    *,
    connector: DBConnector,
    import_log_id: int,
    error_message: str,
) -> None:
    with connector.connect() as conn:
        repository = ImportRepository(conn)

        repository.mark_import_failed(
            import_log_id=import_log_id,
            error_message=error_message,
        )


def import_catalog(
    *,
    file_path: Path,
    source_code: str,
    source_name: str,
    source_type: str,
) -> None:
    if not file_path.is_file():
        raise FileNotFoundError(f"Catalog file not found: {file_path}")

    connector = DBConnector()

    file_hash = calculate_file_hash(file_path)

    data_source_id, import_log_id = create_import_log(
        connector=connector,
        source_code=source_code,
        source_name=source_name,
        source_type=source_type,
        file_path=file_path,
        file_hash=file_hash,
    )

    print(f"Data source ID: {data_source_id}")
    print(f"Import log ID: {import_log_id}")
    print(f"File hash: {file_hash}")

    try:
        parser = ArticleXmlParser()
        data = parser.parse(file_path)

        print()
        print("Parsed catalog:")
        print(f"  Product groups: {len(data.product_groups)}")
        print(f"  Commodity groups: {len(data.commodity_groups)}")
        print(f"  Commodities: {len(data.commodities)}")

        with connector.connect() as conn:
            importer = CatalogImporter(conn)

            result = importer.import_catalog(
                data=data,
                data_source_id=data_source_id,
            )

        mark_import_succeeded(
            connector=connector,
            import_log_id=import_log_id,
            records_total=result.total_records,
            records_imported=result.total_records,
        )

    except Exception as exc:
        mark_import_failed(
            connector=connector,
            import_log_id=import_log_id,
            error_message=str(exc),
        )

        raise

    print()
    print("Import succeeded.")
    print(f"  Product groups: {result.product_groups}")
    print(f"  Commodity groups: {result.commodity_groups}")
    print(f"  Commodities: {result.commodities}")
    print(f"  Commodity prices: {result.commodity_prices}")
    print(f"  Estimate prices: {result.estimate_prices}")
    print(f"  Total records: {result.total_records}")


# def parse_args() -> argparse.Namespace:
#     parser = argparse.ArgumentParser(description="Import an iTWO article catalog.")

#     parser.add_argument(
#         "file",
#         type=Path,
#         defalut="data/imports/Artikel.xml",
#         help="Path to Artikel.xml",
#     )

#     parser.add_argument(
#         "--source-code",
#         default="itwo-article-catalog",
#     )

#     parser.add_argument(
#         "--source-name",
#         default="iTWO Article Catalog",
#     )

#     parser.add_argument(
#         "--source-type",
#         default="ITWO_XML",
#     )

#     return parser.parse_args()


def main() -> None:
    file_path = Path("data/imports/Artikel_extended_434_commodities.xml")
    source_code = "itwo-article-catalog"
    source_name = "iTWO Article Catalog"
    source_type = "ITWO_XML"

    import_catalog(
        file_path=file_path,
        source_code=source_code,
        source_name=source_name,
        source_type=source_type,
    )


if __name__ == "__main__":
    main()
