from pydantic import BaseModel, ConfigDict

class LLMModelOut(BaseModel):
    id: int
    name: str
    hf_path: str
    dimension: int
    formats: list[str]
    selected_format: str | None = None
    local_path: str
    max_context_length: int | None = None
    selected_context: int | None = None

    model_config = ConfigDict(from_attributes=True)

class LLMModelIn(BaseModel):
    hf_path: str

    model_config = ConfigDict(from_attributes=True)
