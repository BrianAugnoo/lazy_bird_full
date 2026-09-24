import importlib
import re
from pathlib import Path
from copy import deepcopy

from sqlmodel import select

from lazy_bird.database import db
from lazy_bird.models.inference_engine import InferenceEngine
from lazy_bird.schemas.inference_engine import InferenceEngineOut
from lazy_bird.crud.conversation import messages

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


def upsert(name: str, file_path: str):
    module = importlib.import_module(
        f"lazy_bird.inference.engines.{Path(file_path).stem}"
    )
    kwargs_keys = _kwargs_keys(module)

    with db() as session:
        record = session.exec(
            select(InferenceEngine).where(InferenceEngine.name == name)
        ).first()

        if record is None:
            record = InferenceEngine(
                name=name,
                file_path=file_path,
                kwargs_keys=kwargs_keys,
            )
            session.add(record)
        else:
            record.file_path = file_path
            record.kwargs_keys = kwargs_keys

        session.commit()
        session.refresh(record)

        return InferenceEngineOut.model_validate(record)


def get(engine_id: int):
    with db() as session:
        record = session.get(InferenceEngine, engine_id)

        return (
            InferenceEngineOut.model_validate(record)
            if record
            else None
        )


def get_all():
    with db() as session:
        return [
            InferenceEngineOut.model_validate(item)
            for item in session.exec(select(InferenceEngine)).all()
        ]


def update_kwargs(engine_id: int, kwargs: dict):
    with db() as session:
        record = session.get(InferenceEngine, engine_id)

        if record is None:
            return None

        module = importlib.import_module(
            f"lazy_bird.inference.engines.{Path(record.file_path).stem}"
        )

        invalid = module.validate_kwargs(kwargs)

        if invalid is not True:
            return {
                "success": False,
                "invalid_keys": invalid,
            }

        record.kwargs = kwargs

        session.commit()
        session.refresh(record)

        return {
            "success": True,
            "engine": InferenceEngineOut.model_validate(record),
        }
        
def single_turn(query: str, instructions: str = None):
    from lazy_bird.inference import single_turn as inference_single_turn

    return inference_single_turn(query, instructions)

def chat(conversation_id: int, tools: list[dict] = None, max_iter: int = 20):
    from lazy_bird.inference import agentic_loop

    agentic_loop(conversation_id, tools, max_iter)
    return messages(conversation_id)
