import importlib
from pathlib import Path
from sqlmodel import select
from lazy_bird.database import db
from lazy_bird.models.embedding_engine import EmbeddingEngine, SelectedEmbeddingEngine
from lazy_bird.schemas.embedding_engine import EmbeddingEngineOut, SelectedEmbeddingEngineOut


def select_engine(engine_id: int):
    with db() as session:
        engine = session.get(EmbeddingEngine, engine_id)
        if engine is None:
            return None
        module = importlib.import_module(f"lazy_bird.embedding.engines.{Path(engine.file_path).stem}")
        configured = module.validate_kwargs(engine.kwargs) is True
        record = session.exec(select(SelectedEmbeddingEngine)).first()
        if record is None:
            record = SelectedEmbeddingEngine(id=1, embedding_engine_id=engine_id)
            session.add(record)
        else:
            record.embedding_engine_id = engine_id
        session.commit()
        return SelectedEmbeddingEngineOut(configured=configured, engine=EmbeddingEngineOut.model_validate(engine))


def get():
    with db() as session:
        record = session.exec(select(SelectedEmbeddingEngine)).first()
        if record is None:
            return None
        engine = session.get(EmbeddingEngine, record.embedding_engine_id)
        return engine
