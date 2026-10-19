import hashlib
from collections.abc import Sequence

from costpilot_core.embedding.embedding_model import EmbeddingModel
from costpilot_core.models.commodity.commodity import Commodity
from costpilot_core.text.text_builder import TextBuilder
from psycopg import Connection

from src.models.commodity_record import CommodityRecord
from src.repositories.catalog_repository import CatalogRepository
from src.repositories.embedding_repository import EmbeddingRepository


class EmbeddingImporter:
    def __init__(
        self,
        conn: Connection,
        embedding_model: EmbeddingModel,
        batch_size: int = 16,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0.")

        self._conn = conn
        self._embedding_model = embedding_model
        self._batch_size = batch_size

        self._catalog_repository = CatalogRepository(conn)
        self._embedding_repository = EmbeddingRepository(conn)

    def import_commodity(
        self,
        commodity: CommodityRecord,
    ) -> int:
        with self._conn.transaction():
            model_id = self._register_model()
            embedding_ids = self._import_batch(
                commodities=[commodity],
                model_id=model_id,
            )

        return embedding_ids[0]

    def import_commodities(
        self,
        *,
        data_source_id: int,
    ) -> int:
        if data_source_id <= 0:
            raise ValueError("data_source_id must be greater than 0.")

        with self._conn.transaction():
            commodities = self._catalog_repository.read_commodities(
                data_source_id=data_source_id,
            )

            model_id = self._register_model()

            for start in range(0, len(commodities), self._batch_size):
                batch = commodities[start : start + self._batch_size]

                self._import_batch(
                    commodities=batch,
                    model_id=model_id,
                )

        return len(commodities)

    def _register_model(self) -> int:
        return self._embedding_repository.upsert_embedding_model(
            name=self._embedding_model.name,
            version=self._embedding_model.version,
            dimension=self._embedding_model.dimension,
            distance_metric="cosine",
        )

    def _import_batch(
        self,
        *,
        commodities: Sequence[CommodityRecord],
        model_id: int,
    ) -> list[int]:
        if not commodities:
            return []

        texts = [self._build_text(commodity) for commodity in commodities]

        embeddings = self._embedding_model.encode_batch(texts)

        if len(embeddings) != len(commodities):
            raise ValueError("Embedding count does not match commodity count.")

        embedding_ids = []

        for commodity, text, embedding in zip(
            commodities,
            texts,
            embeddings,
            strict=True,
        ):
            source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

            embedding_id = self._embedding_repository.upsert_commodity_embedding(
                commodity_id=commodity.id,
                model_id=model_id,
                embedding=embedding,
                source_hash=source_hash,
            )

            embedding_ids.append(embedding_id)

        return embedding_ids

    @staticmethod
    def _build_text(
        record: CommodityRecord,
    ) -> str:
        commodity = Commodity(
            id=record.id,
            code=record.code,
            description=record.description,
            unit=record.unit,
            category_path=record.group_description or "",
        )

        return TextBuilder.build_commodity_text(commodity)
