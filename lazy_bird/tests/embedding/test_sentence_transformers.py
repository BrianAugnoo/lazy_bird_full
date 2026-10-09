from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lazy_bird.embedding import engines
from lazy_bird.embedding.engines import detect_device, release_model, sentence_transformers

MODEL = SimpleNamespace(local_path="/models/minilm", selected_format="safetensors")


def settings(**changes):
    return sentence_transformers.EngineSettings(model_id=1, device="cpu", **changes)


class FakeEncoder:
    """Encodes every text as ``[len(text)]`` and records each ``encode`` call."""

    def __init__(self):
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append((list(texts), kwargs))
        return MagicMock(tolist=lambda: [[float(len(text))] for text in texts])


def test_detect_device_falls_back_to_cpu():
    with patch("torch.cuda.is_available", return_value=False), patch("torch.backends.mps.is_available", return_value=False):
        assert detect_device() == "cpu"


def test_the_engine_declares_that_it_runs_a_model_locally():
    assert sentence_transformers.local is True


def test_load_builds_the_model_on_the_chosen_device():
    encoder = MagicMock()

    with patch("sentence_transformers.SentenceTransformer", return_value=encoder) as factory:
        loaded = sentence_transformers.load(settings(), MODEL)

    assert loaded is encoder
    factory.assert_called_once_with("/models/minilm", device="cpu", backend="torch", model_kwargs={})


def test_onnx_models_use_the_onnx_backend():
    onnx = SimpleNamespace(local_path="/models/minilm", selected_format="ONNX")

    with patch("sentence_transformers.SentenceTransformer") as factory:
        sentence_transformers.load(settings(), onnx)

    assert factory.call_args.kwargs["backend"] == "onnx"


def test_presets_that_differ_only_by_batch_size_share_the_loaded_model():
    assert sentence_transformers.load_key(settings(batch_size=2), MODEL) == sentence_transformers.load_key(settings(batch_size=64), MODEL)
    assert sentence_transformers.load_key(settings(), MODEL) != sentence_transformers.load_key(settings(), SimpleNamespace(local_path="/models/other", selected_format="safetensors"))


def test_embed_encodes_all_texts_in_one_call_with_the_batch_size():
    encoder = FakeEncoder()

    vectors = sentence_transformers.embed(encoder, ["a", "bcd"], settings(batch_size=4), MODEL)

    assert vectors == [[1.0], [3.0]]
    assert encoder.calls == [(["a", "bcd"], {"batch_size": 4, "convert_to_numpy": True, "show_progress_bar": False})]


def test_cache_optimization_encodes_batch_by_batch_and_clears_the_caches_after_each():
    encoder = FakeEncoder()
    cleared = []

    with patch.object(sentence_transformers, "release_memory", side_effect=lambda: cleared.append(len(encoder.calls))):
        vectors = sentence_transformers.embed(encoder, ["a", "bb", "ccc", "dddd", "eeeee"], settings(batch_size=2, cache_optimization=True), MODEL)

    assert vectors == [[1.0], [2.0], [3.0], [4.0], [5.0]]  # same vectors, same order
    assert [texts for texts, _ in encoder.calls] == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]
    assert cleared == [1, 2, 3]  # cleared right after every batch


def test_cache_optimization_runs_the_encoder_in_inference_mode():
    states = []
    encoder = FakeEncoder()
    encoder.encode = lambda texts, **kwargs: states.append(__import__("torch").is_inference_mode_enabled()) or MagicMock(tolist=lambda: [[0.0]])

    sentence_transformers.embed(encoder, ["a"], settings(cache_optimization=True), MODEL)
    sentence_transformers.embed(encoder, ["a"], settings(cache_optimization=False), MODEL)

    assert states == [True, False]


def test_unload_moves_the_weights_off_the_gpu_and_clears_the_caches():
    encoder = MagicMock()

    with patch.object(engines, "release_memory") as release:
        sentence_transformers.unload(encoder)

    encoder.to.assert_called_once_with("cpu")
    release.assert_called_once()


def test_releasing_a_model_without_a_device_still_clears_the_caches():
    encoder = MagicMock()
    encoder.to.side_effect = NotImplementedError("onnx")

    with patch.object(engines, "release_memory") as release:
        release_model(encoder)

    release.assert_called_once()
