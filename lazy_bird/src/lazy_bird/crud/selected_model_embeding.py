from sqlmodel import Session, select

from lazy_bird.database import db
from lazy_bird.models.selected_model_embeding import SelectedModelEmbeding
from lazy_bird.schemas.selected_model_embeding import (
    SelectedModelEmbedingIn,
    SelectedModelEmbedingOut,
)


def upsert(selected_model_in: SelectedModelEmbedingIn):
    with db() as session:
        record = session.exec(select(SelectedModelEmbeding)).first()
        if record is None:
            record = SelectedModelEmbeding(id=1, llm_model_id=selected_model_in.llm_model_id, batch=selected_model_in.batch)
            session.add(record)
        else:
            record.llm_model_id = selected_model_in.llm_model_id
            record.batch = selected_model_in.batch
        session.commit()
        session.refresh(record)
        return SelectedModelEmbedingOut.model_validate(record)


def get():
    with db() as session:
        record = session.exec(select(SelectedModelEmbeding)).first()
        if record is None:
            return SelectedModelEmbedingOut(llm_model_id=None)
        return SelectedModelEmbedingOut.model_validate(record)
