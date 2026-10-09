from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lazy_bird.cross_encoder.engines import sentence_transformers
from lazy_bird.embedding import engines

MODEL = SimpleNamespace(local_path="/models/reranker", selected_format="safetensors")


def settings(**changes):
    return sentence_transformers.EngineSettings(model_id=1, device="cpu", **changes)


class FakeScorer:
    """Scores a pair with the length of its document and records each ``predict`` call."""

    def __init__(self):
        self.calls = []

    def predict(self, pairs, **kwargs):
        self.calls.append((list(pairs), kwargs))
        return MagicMock(tolist=lambda: [float(len(document)) for _, document in pairs])


def test_the_engine_declares_that_it_runs_a_model_locally():
    assert sentence_transformers.local is True


def test_load_builds_the_cross_encoder_on_the_chosen_device():
    scorer = MagicMock()

    with patch("sentence_transformers.CrossEncoder", return_value=scorer) as factory:
        loaded = sentence_transformers.load(settings(), MODEL)

    assert loaded is scorer
    factory.assert_called_once_with("/models/reranker", device="cpu", backend="torch")


def test_onnx_models_use_the_onnx_backend():
    onnx = SimpleNamespace(local_path="/models/reranker", selected_format="ONNX")

    with patch("sentence_transformers.CrossEncoder") as factory:
        sentence_transformers.load(settings(), onnx)

    assert factory.call_args.kwargs["backend"] == "onnx"


def test_presets_that_differ_only_by_batch_size_share_the_loaded_model():
    assert sentence_transformers.load_key(settings(batch_size=2), MODEL) == sentence_transformers.load_key(settings(batch_size=64), MODEL)


def test_pairs_are_scored_with_the_query_and_batch_size():
    scorer = FakeScorer()

    scores = sentence_transformers.rerank(scorer, "query", ["a", "abc"], settings(batch_size=4), MODEL)

    assert scores == [1.0, 3.0]
    assert scorer.calls == [([("query", "a"), ("query", "abc")], {"batch_size": 4, "convert_to_numpy": True, "show_progress_bar": False})]


def test_cache_optimization_scores_batch_by_batch_and_clears_the_caches_after_each():
    scorer = FakeScorer()
    cleared = []

    with patch.object(sentence_transformers, "release_memory", side_effect=lambda: cleared.append(len(scorer.calls))):
        scores = sentence_transformers.rerank(scorer, "q", ["a", "bb", "ccc"], settings(batch_size=2, cache_optimization=True), MODEL)

    assert scores == [1.0, 2.0, 3.0]
    assert [[document for _, document in pairs] for pairs, _ in scorer.calls] == [["a", "bb"], ["ccc"]]
    assert cleared == [1, 2]


def test_cache_optimization_runs_the_scorer_in_inference_mode():
    import torch

    states = []
    scorer = FakeScorer()
    scorer.predict = lambda pairs, **kwargs: states.append(torch.is_inference_mode_enabled()) or MagicMock(tolist=lambda: [0.0])

    sentence_transformers.rerank(scorer, "q", ["a"], settings(cache_optimization=True), MODEL)
    sentence_transformers.rerank(scorer, "q", ["a"], settings(cache_optimization=False), MODEL)

    assert states == [True, False]


def test_unload_moves_the_weights_off_the_gpu_and_clears_the_caches():
    scorer = MagicMock()

    with patch.object(engines, "release_memory") as release:
        sentence_transformers.unload(scorer)

    scorer.to.assert_called_once_with("cpu")
    release.assert_called_once()
