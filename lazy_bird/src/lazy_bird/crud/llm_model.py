from lazy_bird.database import db
from lazy_bird.models.llm_model import LLMModel as LLMModelORM
from lazy_bird.models.selected_model_embeding import SelectedModelEmbeding
from lazy_bird.schemas.llm_model import LLMModelOut, LLMModelIn
from sqlmodel import select, delete
from lazy_bird.tools.model_extraction import extract, download_model


def _create_from_extraction(hf_path: str, local_path: str):
    extraction_result = extract(local_path)
    llm_model = LLMModelORM(
        name=extraction_result["name"] or hf_path,
        hf_path=hf_path,
        local_path=str(local_path),
        dimension=extraction_result["dimension"],
        max_context_length=extraction_result.get("max_context_length"),
        formats=extraction_result["formats"],
        selected_format=extraction_result["formats"][0],
    )
    with db() as session:
        session.add(llm_model)
        session.commit()
        session.refresh(llm_model)
        return LLMModelOut.model_validate(llm_model)


def create(llm_model_in: LLMModelIn):
    model_path = download_model(llm_model_in.hf_path)
    return _create_from_extraction(llm_model_in.hf_path, model_path)


def create_from_local_path(hf_path: str, local_path: str):
    return _create_from_extraction(hf_path, local_path)

def find(id: int):
    with db() as session:
        llm_model = session.get(LLMModelORM, id)
        if llm_model is None:
            return None
        return LLMModelOut.model_validate(llm_model)

def get_all():
    with db() as session:
        statement = select(LLMModelORM)
        llm_models = session.exec(statement).all()
        return [LLMModelOut.model_validate(llm_model) for llm_model in llm_models]

def delete_all():
    with db() as session:
        session.exec(delete(SelectedModelEmbeding))
        session.exec(delete(LLMModelORM))
        session.commit()
