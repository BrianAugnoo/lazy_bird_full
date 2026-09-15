from lazy_bird.models.llm_model import LLMModel


def test_llm_model_table_shape():
    table = LLMModel.__table__

    assert table.name == "llmmodel"
    assert list(table.columns.keys()) == [
        "id",
        "name",
        "hf_path",
        "local_path",
        "dimension",
        "max_context_length",
        "selected_context",
        "formats",
        "selected_format",
    ]
    assert table.c.id.primary_key is True
    assert all(
        not column.nullable
        for column in table.columns
        if column.name not in {"id", "max_context_length", "selected_context", "selected_format"}
    )


def test_llm_model_instance_keeps_model_metadata():
    record = LLMModel(
        name="MiniLM",
        hf_path="owner/model",
        local_path="/models/model",
        dimension=384,
        formats=["safetensors", "ONNX"],
        selected_format="safetensors",
    )

    assert record.id is None
    assert record.dimension == 384
    assert record.selected_format == "safetensors"
