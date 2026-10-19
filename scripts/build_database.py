import argparse
import os
from pathlib import Path

import yaml
from costpilot_core.material.attribute_extractor import AttributeExtractor
from costpilot_core.material.classifier import MaterialClassifier
from costpilot_core.material.config_loader import MaterialConfigLoader
from costpilot_core.material.material_extractor import MaterialExtractor
from costpilot_core.material.registry import MaterialRegistry
from sentence_transformers import SentenceTransformer

from src.database.connector import DBConnector
from src.embedding.sentence_transformer_embedding import (
    SentenceTransformerEmbedding,
)
from src.pipelines.catalog_import_pipeline import CatalogImportPipeline
from src.pipelines.search_index_pipeline import SearchIndexPipeline

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path.resolve()


def create_material_extractor() -> MaterialExtractor:
    config_loader = MaterialConfigLoader()
    templates = config_loader.load_all()

    registry = MaterialRegistry(templates)
    classifier = MaterialClassifier(registry)
    attribute_extractor = AttributeExtractor()

    return MaterialExtractor(
        registry=registry,
        classifier=classifier,
        attribute_extractor=attribute_extractor,
    )


def create_embedding_model(
    model_key: str,
) -> SentenceTransformerEmbedding:
    config_path = resolve_path(os.environ["MODEL_CONFIG_PATH"])

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    model_config = config["embedding"][model_key]

    model_path = Path(model_config["path"]).expanduser()

    if not model_path.is_absolute():
        model_path = config_path.parent / model_path

    model_path = model_path.resolve()

    if not model_path.is_dir():
        raise FileNotFoundError(f"Model directory not found: {model_path}")

    print(f"Loading embedding model: {model_config['name']}")

    model = SentenceTransformer(
        str(model_path),
        local_files_only=True,
    )

    return SentenceTransformerEmbedding(
        model=model,
        name=model_config["name"],
        version=str(model_config["version"]),
    )


def get_data_source_id(
    connector: DBConnector,
    source_code: str,
) -> int:
    with connector.connect() as conn, conn.cursor() as cursor:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CostPilot database.")

    parser.add_argument(
        "stage",
        choices=["all", "catalog", "index"],
        help="Database build stage",
    )

    parser.add_argument(
        "--source-code",
        default="itwo-article-catalog",
    )

    parser.add_argument(
        "--source-name",
        default="iTWO Article Catalog",
    )

    parser.add_argument(
        "--source-type",
        default="ITWO_XML",
    )

    parser.add_argument(
        "--model-key",
        default="bge-m3",
    )

    parser.add_argument(
        "--index-part",
        choices=["all", "search", "embedding"],
        default="all",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    connector = DBConnector()
    data_source_id = None

    # Stage 1: Catalog Import
    if args.stage in ("all", "catalog"):
        file_path = resolve_path(os.environ["CATALOG_XML_PATH"])

        print("=== Catalog Import ===")

        pipeline = CatalogImportPipeline(
            connector=connector,
        )

        result = pipeline.run(
            file_path=file_path,
            source_code=args.source_code,
            source_name=args.source_name,
            source_type=args.source_type,
        )

        data_source_id = result.data_source_id

        print(f"Data source ID: {data_source_id}")
        print(f"Imported records: {result.import_result.total_records}")
        print("Catalog import completed.")

    # Stage 2: Search Index Build
    if args.stage in ("all", "index"):
        if data_source_id is None:
            data_source_id = get_data_source_id(
                connector=connector,
                source_code=args.source_code,
            )

        build_search = args.index_part in ("all", "search")
        build_embeddings = args.index_part in ("all", "embedding")

        print()
        print("=== Search Index Build ===")

        material_extractor = create_material_extractor() if build_search else None

        embedding_model = (
            create_embedding_model(args.model_key) if build_embeddings else None
        )

        pipeline = SearchIndexPipeline(
            connector=connector,
            material_extractor=material_extractor,
            embedding_model=embedding_model,
            batch_size=16,
        )

        result = pipeline.run(
            data_source_id=data_source_id,
            build_search=build_search,
            build_embeddings=build_embeddings,
        )

        print(f"Search records: {result.search_records}")
        print(f"Embedding records: {result.embedding_records}")
        print("Search index build completed.")

    print()
    print("Database build finished successfully.")


if __name__ == "__main__":
    main()
