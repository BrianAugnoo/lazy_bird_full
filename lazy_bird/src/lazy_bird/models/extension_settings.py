from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class ToolSettings(SQLModel, table=True):
    """Saved configuration of a tools module declaring ``ToolSettings``."""

    id: int | None = Field(default=None, primary_key=True)
    file_path: str = Field(unique=True)  # "{extension}/{module}.py"
    kwargs: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    kwargs_key: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class HookSettings(SQLModel, table=True):
    """Saved configuration of a hooks module declaring ``HookSettings``."""

    id: int | None = Field(default=None, primary_key=True)
    file_path: str = Field(unique=True)
    kwargs: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    kwargs_key: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
