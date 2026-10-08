import weakref
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lazy_bird.embedding.engines import detect_device
from lazy_bird.embedding.engines import sentence_transformers


def test_detect_device_falls_back_to_cpu():
    with patch("torch.cuda.is_available", return_value=False), patch("torch.backends.mps.is_available", return_value=False):
        assert detect_device() == "cpu"


def test_sentence_transformers_encodes_texts_with_the_model_and_batch_size():
    encoded = MagicMock()
    encoded.tolist.return_value = [[0.1, 0.2]]
    encoder = MagicMock()
    encoder.encode.return_value = encoded
    settings = sentence_transformers.EngineSettings(model_id=1, device="cpu", batch_size=4)
    model = SimpleNamespace(local_path="/models/minilm", selected_format="safetensors")
    sentence_transformers._load.cache_clear()

    with patch("sentence_transformers.SentenceTransformer", return_value=encoder) as factory:
        vectors = sentence_transformers.embed(["hello"], settings, model)

    assert vectors == [[0.1, 0.2]]
    factory.assert_called_once_with("/models/minilm", device="cpu", backend="torch", model_kwargs={})
    encoder.encode.assert_called_once_with(["hello"], batch_size=4, convert_to_numpy=True, show_progress_bar=False)
    sentence_transformers._load.cache_clear()


def test_onnx_models_use_the_onnx_backend():
    encoder = MagicMock()
    encoder.encode.return_value = MagicMock(tolist=lambda: [[1.0]])
    settings = sentence_transformers.EngineSettings(model_id=1, device="cpu")
    model = SimpleNamespace(local_path="/models/minilm", selected_format="ONNX")
    sentence_transformers._load.cache_clear()

    with patch("sentence_transformers.SentenceTransformer", return_value=encoder) as factory:
        sentence_transformers.embed(["hello"], settings, model)

    assert factory.call_args.kwargs["backend"] == "onnx"
    sentence_transformers._load.cache_clear()


class FakeEncoder:
    def __init__(self, fail=False):
        self.fail = fail

    def encode(self, texts, **kwargs):
        if self.fail:
            raise RuntimeError("out of memory")
        return MagicMock(tolist=lambda: [[1.0] for _ in texts])


def embed_with(encoder, unloading):
    """Embed one text with ``encoder`` as the loaded model; return how many times it was loaded."""
    loads = []

    def factory(*args, **kwargs):
        loads.append(args)
        return encoder

    settings = sentence_transformers.EngineSettings(model_id=1, device="cpu", unloading=unloading)
    model = SimpleNamespace(local_path="/models/minilm", selected_format="safetensors")
    with patch("sentence_transformers.SentenceTransformer", new=factory):
        sentence_transformers.embed(["hello"], settings, model)
    return len(loads)


def test_model_is_released_after_embedding_when_unloading():
    encoder = FakeEncoder()
    reference = weakref.ref(encoder)
    sentence_transformers._load.cache_clear()

    embed_with(encoder, unloading=True)
    del encoder

    assert reference() is None
    assert sentence_transformers._load.cache_info().currsize == 0


def test_model_stays_loaded_between_calls_without_unloading():
    encoder = FakeEncoder()
    sentence_transformers._load.cache_clear()

    first = embed_with(encoder, unloading=False)
    second = embed_with(encoder, unloading=False)

    assert (first, second) == (1, 0)
    assert sentence_transformers._load.cache_info().currsize == 1
    sentence_transformers._load.cache_clear()


def test_model_is_released_even_when_embedding_fails():
    encoder = FakeEncoder(fail=True)
    reference = weakref.ref(encoder)
    sentence_transformers._load.cache_clear()

    with pytest.raises(RuntimeError, match="out of memory"):
        embed_with(encoder, unloading=True)
    del encoder

    assert reference() is None
    assert sentence_transformers._load.cache_info().currsize == 0
