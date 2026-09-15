from unittest.mock import MagicMock, patch
from lazy_bird.embedding.engines import detect_device
from lazy_bird.embedding.engines import sentence_transformers


def test_detect_device_falls_back_to_cpu():
    with patch("torch.cuda.is_available", return_value=False), patch("torch.backends.mps.is_available", return_value=False):
        assert detect_device() == "cpu"


def test_sentence_transformers_embeds_chunk_content():
    encoded = MagicMock(); encoded.tolist.return_value = [[0.1, 0.2]]
    model = MagicMock(); model.encode.return_value = encoded
    settings = sentence_transformers.EngineSettings(model_path="/models/model", device="cpu")
    with patch("sentence_transformers.SentenceTransformer", return_value=model):
        vectors = sentence_transformers.embed([{"content": "hello"}], 512, 4, settings)
    assert vectors == [[0.1, 0.2]]
    model.encode.assert_called_once_with(["hello"], batch_size=4, convert_to_numpy=True, show_progress_bar=False)


def test_sentence_transformers_rejects_unknown_settings():
    assert sentence_transformers.validate_kwargs({"unknown": True}) == ["unknown"]
