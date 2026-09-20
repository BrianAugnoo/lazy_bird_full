from pydantic import BaseModel, ConfigDict

class InferenceEngineOut(BaseModel):
    id: int
    name: str
    file_path: str
    kwargs_keys: dict[str, list]
    kwargs: dict
    model_config = ConfigDict(from_attributes=True)
    
class InferenceEngineKwargsIn(BaseModel):
    kwargs: dict
    
class SelectedInferenceEngineIn(BaseModel):
    inference_engine_id: int
    
class SelectedInferenceEngineOut(BaseModel):
    configured: bool
    engine: InferenceEngineOut | None = None
    
class Response(BaseModel):
    content: str
    reasoning: str | None = None
    model_config = ConfigDict(from_attributes=True)