import hashlib
from dataclasses import dataclass
from pathlib import Path

from src.database.connector import DBConnector
from src.importing.catalog_importer import (
    CatalogImporter,
    CatalogImportResult,
)
from src.parsers.article_xml_parser import ArticleXmlParser
from src.repositories.import_repository import ImportRepository


@dataclass(frozen=True)
class CatalogPipelineResult:
    data_source_id: int
    import_log_id: int
    import_result: CatalogImportResult


class CatalogImportPipeline:
    def __init__(
        self,
        connector: DBConnector,
    ) -> None:
        self._connector = connector

    def run(
        self,
        *,
        file_path: Path,
        source_code: str,
        source_name: str,
        source_type: str,
    ) -> CatalogPipelineResult:
        if not file_path.is_file():
            raise FileNotFoundError(f"Catalog file not found: {file_path}")

        file_hash = self._calculate_file_hash(file_path)

        # Create import log
        with self._connector.connect() as conn:
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

        try:
            # Parse XML
            parser = ArticleXmlParser()
            data = parser.parse(file_path)

            # Import catalog
            with self._connector.connect() as conn:
                importer = CatalogImporter(conn)

                result = importer.import_catalog(
                    data=data,
                    data_source_id=data_source_id,
                )

            # Mark succeeded
            with self._connector.connect() as conn:
                repository = ImportRepository(conn)

                repository.mark_import_succeeded(
                    import_log_id=import_log_id,
                    records_total=result.total_records,
                    records_imported=result.total_records,
                )

        except Exception as exc:
            with self._connector.connect() as conn:
                repository = ImportRepository(conn)

                repository.mark_import_failed(
                    import_log_id=import_log_id,
                    error_message=str(exc),
                )

            raise

        return CatalogPipelineResult(
            data_source_id=data_source_id,
            import_log_id=import_log_id,
            import_result=result,
        )

    @staticmethod
    def _calculate_file_hash(
        file_path: Path,
    ) -> str:
        digest = hashlib.sha256()

        with file_path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)

        return digest.hexdigest()
