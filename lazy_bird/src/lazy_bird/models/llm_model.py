from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field


class LLMModel(SQLModel, table=True):
    """A model stored in the Hugging Face cache (downloaded, or imported from disk)."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    # Repository id: "org/name" for Hugging Face models, "local/<name>" for imports.
    hf_path: str = Field(unique=True)
    # Snapshot directory in the cache.
    local_path: str
    revision: str | None = Field(default=None)
    source: str = Field(default="huggingface")  # "huggingface" or "local"
    dimension: int | None = Field(default=None)
    max_context_length: int | None = Field(default=None)
    selected_context: int | None = Field(default=None)
    formats: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    # Weight files per format, relative to local_path.
    files: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    selected_format: str | None = Field(default=None)
    # The file to load when the format has alternatives (one GGUF quantization).
    selected_file: str | None = Field(default=None)
