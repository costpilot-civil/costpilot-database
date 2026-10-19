from costpilot_core.models.commodity.commodity import Commodity
from costpilot_core.text.text_builder import TextBuilder
from sentence_transformers import SentenceTransformer

from scripts.test_structured_extraction import read_commodity
from src.embedding.sentence_transformer_embedding import (
    SentenceTransformerEmbedding,
)

MODEL_NAME = "BAAI/bge-m3"
MODEL_VERSION = "default"
MODEL_PATH = "/home/guanlin/projects/costpilot/models/embedding/bge-m3"


def main() -> None:
    record = read_commodity(commodity_id=1)

    commodity = Commodity(
        id=record.id,
        code=record.code,
        description=record.description,
        unit=record.unit,
        category_path=record.group_description or "",
    )

    text = TextBuilder.build_commodity_text(commodity)

    print("Embedding text:")
    print(text)

    print()
    print("Loading embedding model...")

    model = SentenceTransformer(MODEL_PATH)

    embedding_model = SentenceTransformerEmbedding(
        model=model,
        name=MODEL_NAME,
        version=MODEL_VERSION,
    )

    embedding = embedding_model.encode(text)

    print()
    print(f"Model: {embedding_model.name}")
    print(f"Version: {embedding_model.version}")
    print(f"Dimension: {embedding_model.dimension}")
    print(f"Embedding length: {len(embedding)}")
    print(f"First 10 values: {embedding[:10]}")

    assert len(embedding) == embedding_model.dimension
    assert all(isinstance(value, float) for value in embedding)

    print()
    print("Embedding test passed.")


if __name__ == "__main__":
    main()
