from lazy_bird.models.selected_model_embeding import SelectedModelEmbeding


def test_selected_model_embeding_table_shape():
    table = SelectedModelEmbeding.__table__

    assert table.name == "selectedmodelembeding"
    assert list(table.columns.keys()) == ["id", "llm_model_id", "batch"]
    assert table.c.id.primary_key is True
    assert table.c.id.default.arg == 1
    assert table.c.llm_model_id.nullable is False


def test_selected_model_embeding_instance_keeps_selected_model_id():
    record = SelectedModelEmbeding(id=1, llm_model_id=7)

    assert record.id == 1
    assert record.llm_model_id == 7
