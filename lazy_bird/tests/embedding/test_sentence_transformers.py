from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
