from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ModuleSettingsOut(BaseModel):
    """Settings of a tools/hooks module; ``errors`` lists what is missing (empty when ``valid``)."""

    file_path: str
    kwargs: dict[str, Any]
    kwargs_key: dict[str, dict[str, Any]]
    available: bool = True
    valid: bool = True
    errors: dict[str, str] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True)


class ModuleSettingsIn(BaseModel):
    kwargs: dict[str, Any] = Field(default_factory=dict)
