import pytest
from pydantic import ValidationError

from lazy_bird.models.llm_model import LLMModel
from lazy_bird.schemas.llm_model import LLMModelIn, LLMModelOut


def test_llm_model_input_requires_hugging_face_path():
    assert LLMModelIn(hf_path="owner/model").model_dump() == {"hf_path": "owner/model"}

    with pytest.raises(ValidationError):
        LLMModelIn()


def test_llm_model_output_reads_model_attributes():
    model = LLMModel(
        id=1,
        name="MiniLM",
        hf_path="owner/model",
        local_path="/models/model",
        dimension=384,
        formats=["safetensors", "ONNX"],
        selected_format="safetensors",
    )

    schema = LLMModelOut.model_validate(model)

    assert schema.model_dump() == {
        "id": 1,
        "name": "MiniLM",
        "hf_path": "owner/model",
        "dimension": 384,
        "formats": ["safetensors", "ONNX"],
        "selected_format": "safetensors",
        "local_path": "/models/model",
        "max_context_length": None,
        "selected_context": None,
    }
