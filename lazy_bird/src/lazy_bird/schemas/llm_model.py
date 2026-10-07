from pydantic import BaseModel, ConfigDict, Field


class LLMModelOut(BaseModel):
    """A model; ``available`` is false when its files are no longer on disk."""

    id: int
    name: str
    hf_path: str
    local_path: str
    revision: str | None = None
    source: str
    dimension: int | None = None
    max_context_length: int | None = None
    selected_context: int | None = None
    formats: list[str]
    files: dict[str, list[str]] = Field(default_factory=dict)
    selected_format: str | None = None
    selected_file: str | None = None
    available: bool = True
    size_mb: float | None = None

    model_config = ConfigDict(from_attributes=True)


class LLMModelIn(BaseModel):
    """Download a Hugging Face model; ``files`` limits the weights fetched (e.g. one GGUF file)."""

    hf_path: str = Field(min_length=3, pattern=r"^[\w.-]+/[\w.-]+$")
    files: list[str] | None = None
    revision: str | None = None


class UploadedFileOut(BaseModel):
    """A model file received by the server, waiting for the import."""

    path: str
    size: int


class LLMModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    selected_format: str | None = None
    selected_file: str | None = None
    selected_context: int | None = Field(default=None, ge=1)


class HubFileOut(BaseModel):
    path: str
    size: int
    format: str | None = None
