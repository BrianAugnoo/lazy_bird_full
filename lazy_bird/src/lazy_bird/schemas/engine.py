from typing import Any

from pydantic import BaseModel, ConfigDict


class EngineOut(BaseModel):
    """An engine module as discovered at startup.

    ``kwargs_key`` describes every settings attribute (see ``lazy_bird.extension.settings``).
    ``available`` is false when the module is no longer importable or breaks its contract.
    ``local`` is true when the engine runs its model on this machine.
    """

    id: int
    name: str
    file_path: str
    formats: list[str]
    local: bool
    kwargs_key: dict[str, dict[str, Any]]
    available: bool = True
    model_config = ConfigDict(from_attributes=True)
