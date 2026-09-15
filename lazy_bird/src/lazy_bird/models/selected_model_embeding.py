from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


class SelectedModelEmbeding(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("id = 1", name="selected_model_embeding_id_is_one"),
    )

    id: int = Field(default=1, primary_key=True, nullable=False)
    llm_model_id: int = Field(foreign_key="llmmodel.id", nullable=False)
    batch: int = Field(default=1, nullable=False)
