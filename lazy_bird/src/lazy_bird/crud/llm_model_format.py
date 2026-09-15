from lazy_bird.database import db
from lazy_bird.models.llm_model import LLMModel


def update_selected_format(model_id: int, selected_format: str):
    with db() as session:
        model = session.get(LLMModel, model_id)
        if model is None:
            return None
        if selected_format not in model.formats:
            return {"success": False, "invalid_keys": ["selected_format"]}
        model.selected_format = selected_format
        session.commit()
        session.refresh(model)
        return {"success": True, "model": model}
