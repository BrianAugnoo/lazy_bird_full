from sqlalchemy import Column, Index, JSON, text
from sqlmodel import Field, SQLModel


class CrossEncoderEngine(SQLModel, table=True):
    """A cross-encoder engine module discovered in ``cross_encoder/engines/``."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    file_path: str
    formats: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    kwargs_key: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class PresetCrossEncoder(SQLModel, table=True):
    """A named configuration (kwargs) of a cross-encoder engine.

    At most one row has ``default`` set; the partial unique index enforces it.
    """

    __table_args__ = (
        Index(
            "uq_presetcrossencoder_single_default",
            "default",
            unique=True,
            sqlite_where=text('"default" = 1'),
            postgresql_where=text('"default"'),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    cross_encoder_engine_id: int = Field(foreign_key="crossencoderengine.id", nullable=False)
    kwargs: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    default: bool = Field(default=False, nullable=False)
