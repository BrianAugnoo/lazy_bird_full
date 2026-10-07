from sqlalchemy import Column, Index, JSON, text
from sqlmodel import Field, SQLModel


class InferenceEngine(SQLModel, table=True):
    """An inference engine module discovered in ``inference/engines/``."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    file_path: str
    formats: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    kwargs_key: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class PresetInference(SQLModel, table=True):
    """A named configuration (kwargs) of an inference engine.

    At most one row has ``default`` set; the partial unique index enforces it.
    """

    __table_args__ = (
        Index(
            "uq_presetinference_single_default",
            "default",
            unique=True,
            sqlite_where=text('"default" = 1'),
            postgresql_where=text('"default"'),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    inference_engine_id: int = Field(foreign_key="inferenceengine.id", nullable=False)
    kwargs: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    default: bool = Field(default=False, nullable=False)
