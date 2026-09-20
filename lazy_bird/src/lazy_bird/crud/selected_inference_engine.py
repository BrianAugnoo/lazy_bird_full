import importlib
from pathlib import Path
from sqlmodel import select
from lazy_bird.database import db
from lazy_bird.models.inference_engine import InferenceEngine, SelectedInferenceEngine
from lazy_bird.schemas.inference_engine import InferenceEngineOut, SelectedInferenceEngineOut


def select_engine(engine_id: int):
    with db() as session:
        engine = session.get(InferenceEngine, engine_id)
        if engine is None:
            return None
        module = importlib.import_module(f"lazy_bird.inference.engines.{Path(engine.file_path).stem}")
        configured = module.validate_kwargs(engine.kwargs) is True
        record = session.exec(select(SelectedInferenceEngine)).first()
        if record is None:
            record = SelectedInferenceEngine(id=1, inference_engine_id=engine_id)
            session.add(record)
        else:
            record.inference_engine_id = engine_id
        session.commit()
        return SelectedInferenceEngineOut(configured=configured, engine=InferenceEngineOut.model_validate(engine))


def get():
    with db() as session:
        record = session.exec(select(SelectedInferenceEngine)).first()
        if record is None:
            return None
        engine = session.get(InferenceEngine, record.inference_engine_id)
        return engine