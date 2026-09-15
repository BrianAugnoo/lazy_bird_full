import lazy_bird.crud.llm_model as llm_model_crud
import lazy_bird.crud.selected_model_embeding as selected_model_crud
from lazy_bird.schemas.llm_model import LLMModelIn
from lazy_bird.schemas.selected_model_embeding import SelectedModelEmbedingIn

from tests.conftest import MODEL_INPUT, MODEL_OUTPUT


def test_create_downloads_extracts_and_persists_model(crud_database, fake_model_services):
    record = llm_model_crud.create(LLMModelIn(**MODEL_INPUT))

    assert record.model_dump() == {
        **MODEL_OUTPUT,
        "id": 1,
        "max_context_length": None,
        "selected_context": None,
    }
    assert llm_model_crud.find(1) == record


def test_create_passes_downloaded_path_to_extractor(crud_database, monkeypatch):
    calls = []
    monkeypatch.setattr(llm_model_crud, "download_model", lambda hf_path: "/models/downloaded")

    def fake_extract(local_path):
        calls.append(local_path)
        return {"name": "model", "dimension": 128, "formats": ["safetensors"]}

    monkeypatch.setattr(llm_model_crud, "extract", fake_extract)

    llm_model_crud.create(LLMModelIn(hf_path="owner/model"))

    assert calls == ["/models/downloaded"]


def test_find_returns_none_for_unknown_id(crud_database):
    assert llm_model_crud.find(404) is None


def test_get_all_returns_every_model(crud_database, fake_model_services):
    llm_model_crud.create(LLMModelIn(hf_path="owner/first"))
    llm_model_crud.create(LLMModelIn(hf_path="owner/second"))

    records = llm_model_crud.get_all()

    assert [record.hf_path for record in records] == ["owner/first", "owner/second"]


def test_delete_all_removes_models_and_selected_model(crud_database, fake_model_services):
    model = llm_model_crud.create(LLMModelIn(**MODEL_INPUT))
    selected_model_crud.upsert(SelectedModelEmbedingIn(llm_model_id=model.id))

    llm_model_crud.delete_all()

    assert llm_model_crud.get_all() == []
    assert selected_model_crud.get().llm_model_id is None
