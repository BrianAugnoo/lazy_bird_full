import importlib
import re
from pathlib import Path
from copy import deepcopy
from sqlmodel import select
from lazy_bird.database import db
from lazy_bird.models.embedding_engine import EmbeddingEngine
from lazy_bird.schemas.embedding_engine import EmbeddingEngineOut


def _kwargs_keys(module) -> dict[str, list]:
    keys = {}
    for key, field in module.EngineSettings.model_fields.items():
        type_match = re.search(
            r"\b(bool|int|float|str|list|dict|tuple|set|bytes)\b",
            repr(field.annotation),
        )
        value_type = type_match.group(1) if type_match else "unknown"
        value = "required" if field.is_required() else deepcopy(field.default)
        keys[key] = [value_type, value]
    return keys


def upsert(name: str, file_path: str, formats: list[str]):
    module = importlib.import_module(f"lazy_bird.embedding.engines.{Path(file_path).stem}")
    kwargs_keys = _kwargs_keys(module)
    with db() as session:
        record = session.exec(select(EmbeddingEngine).where(EmbeddingEngine.name == name)).first()
        if record is None:
            record = EmbeddingEngine(name=name, file_path=file_path, formats=formats, kwargs_keys=kwargs_keys)
            session.add(record)
        else:
            record.file_path, record.formats, record.kwargs_keys = file_path, formats, kwargs_keys
        session.commit(); session.refresh(record)
        return EmbeddingEngineOut.model_validate(record)

def get(engine_id: int):
    with db() as session:
        record = session.get(EmbeddingEngine, engine_id)
        return EmbeddingEngineOut.model_validate(record) if record else None

def get_all():
    with db() as session:
        return [EmbeddingEngineOut.model_validate(item) for item in session.exec(select(EmbeddingEngine)).all()]

def update_kwargs(engine_id: int, kwargs: dict):
    with db() as session:
        record = session.get(EmbeddingEngine, engine_id)
        if record is None:
            return None
        module = importlib.import_module(f"lazy_bird.embedding.engines.{Path(record.file_path).stem}")
        invalid = module.validate_kwargs(kwargs)
        if invalid is not True:
            return {"success": False, "invalid_keys": invalid}
        record.kwargs = kwargs
        session.commit(); session.refresh(record)
        return {"success": True, "engine": EmbeddingEngineOut.model_validate(record)}
