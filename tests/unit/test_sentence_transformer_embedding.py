from unittest.mock import MagicMock

import numpy as np
import pytest

from src.embedding.sentence_transformer_embedding import SentenceTransformerEmbedding


def make_adapter(batch_size=2, dimension=3):
    model = MagicMock()
    model.get_embedding_dimension.return_value = dimension
    model.encode.side_effect = lambda texts, **kwargs: np.array(
        [[1.0, 0.0, 0.0] for _ in texts], dtype=np.float32
    )
    adapter = SentenceTransformerEmbedding(model=model, name="mock", version="1", batch_size=batch_size)
    return adapter, model


def test_single_and_batch_encode():
    adapter, model = make_adapter()
    assert adapter.name == "mock"
    assert adapter.version == "1"
    assert adapter.dimension == 3
    assert adapter.encode("a") == [1.0, 0.0, 0.0]
    assert adapter.encode_batch(["a", "b"]) == [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
    assert model.encode.call_args.kwargs["normalize_embeddings"] is True
    assert model.encode.call_args.kwargs["batch_size"] == 2


def test_empty_input_skips_inference():
    adapter, model = make_adapter()
    assert adapter.encode_batch([]) == []
    model.encode.assert_not_called()


@pytest.mark.parametrize("batch_size,dimension", [(0, 3), (2, None), (2, 0)])
def test_invalid_config(batch_size, dimension):
    with pytest.raises(ValueError):
        make_adapter(batch_size=batch_size, dimension=dimension)
