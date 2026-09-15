from pydantic import BaseModel, ConfigDict


class EmbeddingEngineOut(BaseModel):
    id: int
    name: str
    file_path: str
    formats: list[str]
    kwargs: dict
    kwargs_keys: dict[str, list]
    model_config = ConfigDict(from_attributes=True)


class EmbeddingEngineKwargsIn(BaseModel):
    kwargs: dict


class SelectedEmbeddingEngineIn(BaseModel):
    embedding_engine_id: int


class SelectedEmbeddingEngineOut(BaseModel):
    configured: bool
    engine: EmbeddingEngineOut | None = None
