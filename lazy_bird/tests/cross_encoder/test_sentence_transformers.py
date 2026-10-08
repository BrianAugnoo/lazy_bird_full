import weakref
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lazy_bird.cross_encoder.engines import sentence_transformers

MODEL = SimpleNamespace(local_path="/models/reranker", selected_format="safetensors")


class FakeScorer:
    def __init__(self, fail=False):
        self.fail = fail
        self.pairs = None

    def predict(self, pairs, **kwargs):
        if self.fail:
            raise RuntimeError("out of memory")
        self.pairs, self.kwargs = pairs, kwargs
        return MagicMock(tolist=lambda: [float(len(document)) for _, document in pairs])


def rerank_with(scorer, unloading=True, model=MODEL, **settings):
    """Rerank two documents with ``scorer`` as the loaded model; return how many times it was loaded."""
    loads = []

    def factory(*args, **kwargs):
        loads.append(kwargs)
        return scorer

    parsed = sentence_transformers.EngineSettings(model_id=1, device="cpu", unloading=unloading, **settings)
    with patch("sentence_transformers.CrossEncoder", new=factory):
        scores = sentence_transformers.rerank("query", ["a", "abc"], parsed, model)
    return scores, loads


def test_pairs_are_scored_with_the_query_and_batch_size():
    scorer = FakeScorer()
    sentence_transformers._load.cache_clear()

    scores, loads = rerank_with(scorer, batch_size=4)

    assert scores == [1.0, 3.0]
    assert scorer.pairs == [("query", "a"), ("query", "abc")]
    assert scorer.kwargs == {"batch_size": 4, "convert_to_numpy": True, "show_progress_bar": False}
    assert loads == [{"device": "cpu", "backend": "torch"}]


def test_onnx_models_use_the_onnx_backend():
    sentence_transformers._load.cache_clear()

    _, loads = rerank_with(FakeScorer(), model=SimpleNamespace(local_path="/models/reranker", selected_format="ONNX"))

    assert loads[0]["backend"] == "onnx"


def test_model_is_released_after_scoring_when_unloading():
    scorer = FakeScorer()
    reference = weakref.ref(scorer)
    sentence_transformers._load.cache_clear()

    rerank_with(scorer, unloading=True)
    del scorer

    assert reference() is None
    assert sentence_transformers._load.cache_info().currsize == 0


def test_model_stays_loaded_between_calls_without_unloading():
    scorer = FakeScorer()
    sentence_transformers._load.cache_clear()

    _, first = rerank_with(scorer, unloading=False)
    _, second = rerank_with(scorer, unloading=False)

    assert (len(first), len(second)) == (1, 0)
    assert sentence_transformers._load.cache_info().currsize == 1
    sentence_transformers._load.cache_clear()


def test_model_is_released_even_when_scoring_fails():
    scorer = FakeScorer(fail=True)
    reference = weakref.ref(scorer)
    sentence_transformers._load.cache_clear()

    with pytest.raises(RuntimeError, match="out of memory"):
        rerank_with(scorer, unloading=True)
    del scorer

    assert reference() is None
    assert sentence_transformers._load.cache_info().currsize == 0
