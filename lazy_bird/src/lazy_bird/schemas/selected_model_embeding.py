from pydantic import BaseModel, ConfigDict


class SelectedModelEmbedingOut(BaseModel):
    llm_model_id: int | None
    batch: int = 1

    model_config = ConfigDict(from_attributes=True)


class SelectedModelEmbedingIn(BaseModel):
    llm_model_id: int
    batch: int = 1

    model_config = ConfigDict(from_attributes=True)
