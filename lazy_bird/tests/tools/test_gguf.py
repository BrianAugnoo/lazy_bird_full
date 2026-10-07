import pytest

from lazy_bird.tools import gguf
from tests.tools.gguf_factory import write_gguf

METADATA = {
    "general.architecture": "llama",
    "general.name": "Tiny Llama",
    "general.file_type": 15,
    "llama.context_length": 4096,
    "llama.embedding_length": 2048,
}


def test_metadata_is_read_and_large_arrays_are_skipped(tmp_path):
    path = write_gguf(tmp_path / "tiny.gguf", METADATA, vocabulary=1000)

    metadata = gguf.read_metadata(path)

    assert metadata["general.name"] == "Tiny Llama"
    assert "tokenizer.ggml.tokens" not in metadata


def test_summary_gives_what_lazy_bird_needs(tmp_path):
    assert gguf.summary(write_gguf(tmp_path / "tiny.gguf", METADATA)) == {
        "name": "Tiny Llama",
        "architecture": "llama",
        "context_length": 4096,
        "embedding_length": 2048,
        "quantization": "Q4_K_M",
    }


@pytest.mark.parametrize(
    ("name", "expected"),
    [("model-Q8_0.gguf", "Q8_0"), ("qwen3-0.6b.IQ4_XS.gguf", "IQ4_XS"), ("model-f16.gguf", "F16"), ("model.gguf", None)],
)
def test_quantization_falls_back_to_the_file_name(name, expected):
    assert gguf.quantization(name) == expected


def test_other_files_are_rejected(tmp_path):
    (tmp_path / "fake.gguf").write_bytes(b"not a gguf file")

    with pytest.raises(gguf.GGUFError):
        gguf.read_metadata(tmp_path / "fake.gguf")
