from dataclasses import dataclass

from costpilot_core.embedding.embedding_model import EmbeddingModel
from costpilot_core.material.material_extractor import MaterialExtractor
from pgvector.psycopg import register_vector

from src.database.connector import DBConnector
from src.importing.embedding_importer import EmbeddingImporter
from src.importing.search_importer import SearchImporter


@dataclass(frozen=True)
class SearchIndexResult:
    search_records: int | None
    embedding_records: int | None


class SearchIndexPipeline:
    def __init__(
        self,
        connector: DBConnector,
        *,
        material_extractor: MaterialExtractor | None = None,
        embedding_model: EmbeddingModel | None = None,
        batch_size: int = 16,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0.")

        self._connector = connector
        self._material_extractor = material_extractor
        self._embedding_model = embedding_model
        self._batch_size = batch_size

    def run(
        self,
        *,
        data_source_id: int,
        build_search: bool = True,
        build_embeddings: bool = True,
    ) -> SearchIndexResult:
        if data_source_id <= 0:
            raise ValueError("data_source_id must be greater than 0.")

        if not build_search and not build_embeddings:
            raise ValueError("No indexing task selected.")

        if build_search and self._material_extractor is None:
            raise ValueError("MaterialExtractor is required.")

        if build_embeddings and self._embedding_model is None:
            raise ValueError("EmbeddingModel is required.")

        search_records = None
        embedding_records = None

        # Build structured search data
        if build_search:
            extractor = self._material_extractor
            assert extractor is not None

            with self._connector.connect() as conn:
                importer = SearchImporter(
                    conn=conn,
                    extractor=extractor,
                )

                search_records = importer.import_commodities(
                    data_source_id=data_source_id,
                )

        # Build embeddings
        if build_embeddings:
            embedding_model = self._embedding_model
            assert embedding_model is not None

            with self._connector.connect() as conn:
                register_vector(conn)

                importer = EmbeddingImporter(
                    conn=conn,
                    embedding_model=embedding_model,
                    batch_size=self._batch_size,
                )

                embedding_records = importer.import_commodities(
                    data_source_id=data_source_id,
                )

        return SearchIndexResult(
            search_records=search_records,
            embedding_records=embedding_records,
        )
