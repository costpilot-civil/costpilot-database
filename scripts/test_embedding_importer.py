import hashlib
import os
from pathlib import Path

import yaml
from costpilot_core.models.commodity.commodity import Commodity
from costpilot_core.text.text_builder import TextBuilder
from pgvector.psycopg import register_vector
from psycopg import Connection
from sentence_transformers import SentenceTransformer

from src.database.connector import DBConnector
from src.embedding.sentence_transformer_embedding import (
    SentenceTransformerEmbedding,
)
from src.importing.embedding_importer import EmbeddingImporter
from src.repositories.catalog_repository import CatalogRepository

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODEL_KEY = "bge-m3"
SOURCE_CODE = "itwo-article-catalog"
COMMODITY_ID = 1


def create_embedding_model() -> SentenceTransformerEmbedding:
    config_path_value = os.environ["MODEL_CONFIG_PATH"]
    config_path = Path(config_path_value).expanduser()

    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    model_config = config["embedding"][MODEL_KEY]

    model_path = Path(model_config["path"]).expanduser()

    if not model_path.is_absolute():
        model_path = config_path.parent / model_path

    if not model_path.is_dir():
        raise FileNotFoundError(f"Model directory not found: {model_path}")

    print(f"Loading model: {model_config['name']}")
    print(f"Model path: {model_path}")

    model = SentenceTransformer(
        str(model_path),
        local_files_only=True,
    )

    return SentenceTransformerEmbedding(
        model=model,
        name=model_config["name"],
        version=model_config["version"],
    )


def read_data_source_id(
    conn: Connection,
) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM data_sources
            WHERE code = %s;
            """,
            (SOURCE_CODE,),
        )

        row = cursor.fetchone()

    if row is None:
        raise ValueError(f"Data source not found: {SOURCE_CODE}")

    return int(row[0])


def build_embedding_text(record) -> str:
    commodity = Commodity(
        id=record.id,
        code=record.code,
        description=record.description,
        unit=record.unit,
        category_path=record.group_description or "",
    )

    return TextBuilder.build_commodity_text(commodity)


def test_single_import(
    conn: Connection,
    importer: EmbeddingImporter,
    record,
    model: SentenceTransformerEmbedding,
) -> None:
    print("\n=== Single Import Test ===")

    embedding_id = importer.import_commodity(record)

    embedding_id_again = importer.import_commodity(record)

    assert embedding_id == embedding_id_again

    text = build_embedding_text(record)

    expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                ce.commodity_id,
                em.name,
                em.version,
                vector_dims(ce.embedding),
                ce.source_hash
            FROM commodity_embeddings AS ce
            JOIN embedding_models AS em
                ON em.id = ce.model_id
            WHERE ce.id = %s;
            """,
            (embedding_id,),
        )

        row = cursor.fetchone()

    assert row is not None
    assert row[0] == record.id
    assert row[1] == model.name
    assert row[2] == model.version
    assert row[3] == model.dimension
    assert row[4] == expected_hash

    print(f"Commodity ID: {record.id}")
    print(f"Embedding ID: {embedding_id}")
    print(f"Dimension: {row[3]}")
    print("Single import test passed.")


def test_batch_import(
    conn: Connection,
    importer: EmbeddingImporter,
    data_source_id: int,
    model: SentenceTransformerEmbedding,
    total: int,
) -> None:
    print("\n=== Batch Import Test ===")

    imported = importer.import_commodities(
        data_source_id=data_source_id,
    )

    assert imported == total

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(*),
                COUNT(*) FILTER (
                    WHERE vector_dims(ce.embedding) != em.dimension
                       OR ce.source_hash IS NULL
                       OR ce.source_hash = ''
                )
            FROM commodity_embeddings AS ce
            JOIN commodities AS c
                ON c.id = ce.commodity_id
            JOIN embedding_models AS em
                ON em.id = ce.model_id
            WHERE c.data_source_id = %s
              AND em.name = %s
              AND em.version = %s;
            """,
            (
                data_source_id,
                model.name,
                model.version,
            ),
        )

        row = cursor.fetchone()

    assert row is not None

    stored_count = int(row[0])
    invalid_count = int(row[1])

    assert stored_count == total
    assert invalid_count == 0

    print(f"Total commodities: {total}")
    print(f"Imported embeddings: {imported}")
    print(f"Stored embeddings: {stored_count}")
    print(f"Invalid embeddings: {invalid_count}")
    print("Batch import test passed.")


def main() -> None:
    embedding_model = create_embedding_model()

    connector = DBConnector()

    with connector.connect() as conn:
        try:
            register_vector(conn)

            data_source_id = read_data_source_id(conn)

            catalog_repository = CatalogRepository(conn)

            commodities = catalog_repository.read_commodities(
                data_source_id=data_source_id,
            )

            if not commodities:
                raise ValueError("No commodities found.")

            record = next(
                (
                    commodity
                    for commodity in commodities
                    if commodity.id == COMMODITY_ID
                ),
                None,
            )

            if record is None:
                raise ValueError(f"Commodity {COMMODITY_ID} not found.")

            importer = EmbeddingImporter(
                conn=conn,
                embedding_model=embedding_model,
                batch_size=16,
            )

            test_single_import(
                conn=conn,
                importer=importer,
                record=record,
                model=embedding_model,
            )

            test_batch_import(
                conn=conn,
                importer=importer,
                data_source_id=data_source_id,
                model=embedding_model,
                total=len(commodities),
            )

            print("\nAll embedding import tests passed.")

        finally:
            conn.rollback()
            print("Transaction rolled back.")


if __name__ == "__main__":
    main()
