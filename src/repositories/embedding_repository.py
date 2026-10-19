import numpy as np
from numpy.typing import ArrayLike
from psycopg import Connection


class EmbeddingRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def upsert_embedding_model(
        self,
        *,
        name: str,
        version: str,
        dimension: int,
        distance_metric: str = "cosine",
    ) -> int:
        if dimension <= 0:
            raise ValueError("Embedding dimension must be positive.")

        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO embedding_models (
                    name,
                    version,
                    dimension,
                    distance_metric
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name, version) DO NOTHING
                RETURNING id;
                """,
                (name, version, dimension, distance_metric),
            )

            row = cursor.fetchone()

            if row is not None:
                return int(row[0])

            cursor.execute(
                """
                SELECT id, dimension, distance_metric
                FROM embedding_models
                WHERE name = %s AND version = %s;
                """,
                (name, version),
            )

            row = cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to resolve embedding model.")

        model_id, existing_dimension, existing_metric = row

        if existing_dimension != dimension or existing_metric != distance_metric:
            raise ValueError("Existing embedding model configuration does not match.")

        return int(model_id)

    def upsert_commodity_embedding(
        self,
        *,
        commodity_id: int,
        model_id: int,
        embedding: ArrayLike,
        source_hash: str,
    ) -> int:
        vector = np.asarray(embedding, dtype=np.float32)

        if vector.ndim != 1 or vector.size == 0:
            raise ValueError("Embedding must be a non-empty 1D vector.")

        if not np.isfinite(vector).all():
            raise ValueError("Embedding contains non-finite values.")

        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT dimension
                FROM embedding_models
                WHERE id = %s;
                """,
                (model_id,),
            )

            row = cursor.fetchone()

            if row is None:
                raise ValueError(f"Embedding model {model_id} not found.")

            if vector.size != row[0]:
                raise ValueError(
                    f"Embedding dimension mismatch: "
                    f"expected {row[0]}, got {vector.size}."
                )

            cursor.execute(
                """
                INSERT INTO commodity_embeddings (
                    commodity_id,
                    model_id,
                    embedding,
                    source_hash
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (commodity_id, model_id)
                DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    source_hash = EXCLUDED.source_hash
                RETURNING id;
                """,
                (
                    commodity_id,
                    model_id,
                    vector,
                    source_hash,
                ),
            )

            result = cursor.fetchone()

        if result is None:
            raise RuntimeError("Failed to upsert commodity embedding.")

        return int(result[0])
