import sys
import textwrap
import uuid
from pathlib import Path

import pytest

from lazy_bird.crud.engine import EngineFamily
from lazy_bird.embedding import embed_texts, vector_space
from lazy_bird.errors import ConflictError, InvalidSettingsError, NotFoundError, UnavailableError
from lazy_bird.extension.discovery import load_failures
from lazy_bird.models.embedding_engine import EmbeddingEngine, PresetEmbedding
from lazy_bird.models.llm_model import LLMModel
from lazy_bird.schemas.embedding_engine import PresetEmbeddingOut

ENGINES = {
    "good": '''
        from pydantic import BaseModel, ConfigDict
        name = "good"
        formats = ["safetensors"]
        class EngineSettings(BaseModel):
            model_id: int
            size: int = 2
            model_config = ConfigDict(extra="forbid")
        fields = {"model_id": {"default_field": True, "content": "default.basic.reference", "args": {"endpoint": "/models/"}}}
        def embed(texts, settings, model):
            return [[float(len(text))] * settings.size for text in texts]
    ''',
    "plain": '''
        from pydantic import BaseModel
        name = "plain"
        class EngineSettings(BaseModel):
            label: str
        def embed(texts, settings, model):
            return [[1.0] for _ in texts]
        def vector_space(settings):
            return f"plain:{settings.label}"
    ''',
    "broken": '''
        from pydantic import BaseModel
        name = "broken"
        class EngineSettings(BaseModel):
            value: int = 1
    ''',
    "bad_fields": '''
        from pydantic import BaseModel
        name = "bad-fields"
        class EngineSettings(BaseModel):
            value: int = 1
        fields = {"missing": {"default_field": True, "content": "default.basic.text"}}
        def embed(texts, settings, model):
            return []
    ''',
    "local": '''
        from pydantic import BaseModel
        name = "local-engine"
        local = True
        class EngineSettings(BaseModel):
            size: int = 2
        def load(settings, model):
            return object()
        def unload(instance):
            pass
        def embed(instance, texts, settings, model):
            return [[1.0] for _ in texts]
        def vector_space(settings):
            return "local"
    ''',
    "local_without_unload": '''
        from pydantic import BaseModel
        name = "local-without-unload"
        local = True
        class EngineSettings(BaseModel):
            size: int = 2
        def load(settings, model):
            return object()
        def embed(instance, texts, settings, model):
            return []
    ''',
    "model_without_formats": '''
        from pydantic import BaseModel
        name = "model-without-formats"
        class EngineSettings(BaseModel):
            model_id: int
        def embed(texts, settings, model):
            return []
    ''',
}


@pytest.fixture
def family(crud_database, tmp_path: Path, monkeypatch) -> EngineFamily:
    package = f"fake_engines_{uuid.uuid4().hex}"
    root = tmp_path / package
    root.mkdir()
    (root / "__init__.py").write_text("")
    for module, source in ENGINES.items():
        (root / f"{module}.py").write_text(textwrap.dedent(source))
    monkeypatch.syspath_prepend(str(tmp_path))
    family = EngineFamily(
        kind="embedding",
        package=package,
        required=("embed",),
        engine_table=EmbeddingEngine,
        preset_table=PresetEmbedding,
        engine_fk="embedding_engine_id",
        preset_out=PresetEmbeddingOut,
    )
    family.discover()
    yield family
    for name in [name for name in sys.modules if name.startswith(package)]:
        del sys.modules[name]


def engine_id(family: EngineFamily, name: str) -> int:
    return next(engine.id for engine in family.engines() if engine.name == name)


def add_model(crud_database, selected_format: str = "safetensors") -> int:
    with crud_database() as session:
        model = LLMModel(name="m", hf_path=f"org/m-{selected_format}", local_path="/tmp/m", dimension=2, formats=[selected_format], selected_format=selected_format)
        session.add(model)
        session.commit()
        return model.id


def test_discover_registers_valid_engines_and_records_broken_ones(family):
    names = {engine.name: engine for engine in family.engines()}

    assert set(names) == {"good", "plain", "local-engine"}
    assert names["good"].formats == ["safetensors"]
    assert names["good"].file_path == "good.py"
    assert names["good"].kwargs_key["model_id"]["content"] == "default.basic.reference"
    assert names["good"].kwargs_key["size"]["default"] == 2
    failed = {failure.source.rsplit(".", 1)[-1]: failure.error for failure in load_failures() if family.package in failure.source}
    assert set(failed) == {"broken", "bad_fields", "model_without_formats", "local_without_unload"}
    assert "embed" in failed["broken"]


def test_engines_say_whether_they_run_a_model_on_this_machine(family):
    names = {engine.name: engine for engine in family.engines()}
    failed = {failure.source.rsplit(".", 1)[-1]: failure.error for failure in load_failures() if family.package in failure.source}

    assert names["local-engine"].local is True
    assert names["good"].local is False and names["plain"].local is False
    assert "unload" in failed["local_without_unload"]  # a local engine must be able to free its model


def test_first_preset_becomes_the_default(family, crud_database):
    model_id = add_model(crud_database)

    first = family.create_preset("first", engine_id(family, "good"), {"model_id": model_id})
    second = family.create_preset("second", engine_id(family, "plain"), {"label": "x"})

    assert first.default is True and first.valid is True
    assert second.default is False
    assert family.default_preset().id == first.id


def test_marking_a_preset_default_unsets_the_previous_one(family, crud_database):
    first = family.create_preset("first", engine_id(family, "plain"), {"label": "a"})
    second = family.create_preset("second", engine_id(family, "plain"), {"label": "b"}, default=True)

    assert family.preset(first.id).default is False
    assert second.default is True
    assert family.update_preset(first.id, {"default": True}).default is True
    assert family.preset(second.id).default is False


def test_the_default_cannot_be_unset_without_choosing_another(family):
    preset = family.create_preset("only", engine_id(family, "plain"), {"label": "a"})

    with pytest.raises(ConflictError) as error:
        family.update_preset(preset.id, {"default": False})
    assert error.value.code == "default_preset_required"


def test_deleting_the_default_promotes_the_oldest_remaining_preset(family):
    first = family.create_preset("first", engine_id(family, "plain"), {"label": "a"})
    second = family.create_preset("second", engine_id(family, "plain"), {"label": "b"})
    third = family.create_preset("third", engine_id(family, "plain"), {"label": "c"}, default=True)

    family.delete_preset(third.id)

    assert family.default_preset().id == first.id
    family.delete_preset(first.id)
    family.delete_preset(second.id)
    assert family.default_preset() is None


def test_invalid_kwargs_are_rejected_per_field(family):
    with pytest.raises(InvalidSettingsError) as error:
        family.create_preset("bad", engine_id(family, "good"), {"size": "big", "other": 1})

    assert set(error.value.fields) == {"model_id", "size", "other"}


def test_model_id_must_reference_a_model_in_a_supported_format(family, crud_database):
    onnx_model = add_model(crud_database, "onnx")

    with pytest.raises(InvalidSettingsError) as missing:
        family.create_preset("missing", engine_id(family, "good"), {"model_id": 999})
    with pytest.raises(InvalidSettingsError) as unsupported:
        family.create_preset("unsupported", engine_id(family, "good"), {"model_id": onnx_model})

    assert "does not exist" in missing.value.fields["model_id"]
    assert "not supported" in unsupported.value.fields["model_id"]


def test_preset_names_are_unique(family):
    family.create_preset("same", engine_id(family, "plain"), {"label": "a"})

    with pytest.raises(ConflictError):
        family.create_preset("same", engine_id(family, "plain"), {"label": "b"})


def test_resolve_hands_the_model_and_settings_to_the_engine(family, crud_database, sql_activity):
    model_id = add_model(crud_database)
    family.create_preset("good", engine_id(family, "good"), {"model_id": model_id, "size": 3})
    sql_activity["statements"].clear()

    resolved = family.resolve()

    assert len(sql_activity["statements"]) == 3  # preset, engine, model: each read once
    assert resolved.model.id == model_id
    assert resolved.settings.size == 3
    assert embed_texts(["ab", "abcd"], resolved) == [[2.0, 2.0, 2.0], [4.0, 4.0, 4.0]]
    assert vector_space(resolved) == "org/m-safetensors"


def test_engines_without_model_name_their_vector_space(family):
    preset = family.create_preset("plain", engine_id(family, "plain"), {"label": "remote"})

    assert vector_space(family.resolve(preset.id)) == "plain:remote"


def test_a_preset_whose_model_was_deleted_is_reported_invalid(family, crud_database):
    model_id = add_model(crud_database)
    preset = family.create_preset("good", engine_id(family, "good"), {"model_id": model_id})
    with crud_database() as session:
        session.delete(session.get(LLMModel, model_id))
        session.commit()

    stored = family.preset(preset.id)

    assert stored.valid is False
    assert "model_id" in stored.errors
    with pytest.raises(InvalidSettingsError):
        family.resolve()


def test_resolve_without_presets_explains_what_to_do(family):
    with pytest.raises(UnavailableError) as error:
        family.resolve()

    assert error.value.code == "no_default_embedding_preset"


def test_unknown_preset_and_engine_are_not_found(family):
    with pytest.raises(NotFoundError):
        family.preset(404)
    with pytest.raises(NotFoundError):
        family.create_preset("x", 404, {})
