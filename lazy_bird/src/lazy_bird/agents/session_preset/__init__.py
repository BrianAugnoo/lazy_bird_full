"""Session presets: ``session_preset/{extension_name}/{name}.json``.

Keys (unknown keys are rejected):

- ``name``: must equal the file name;
- ``description``: shown in the frontend only;
- ``agents``: agent preset ids (``{extension}/{name}``) created in the session;
- ``meta``: the session meta (passed to class tools and hooks);
- ``master``: the agent preset receiving the user's prompts; exactly one, in ``agents``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lazy_bird.agents import agent_preset
from lazy_bird.agents.presets import PresetRegistry

ROOT = Path(__file__).resolve().parent


class SessionPresetData(BaseModel):
    name: str
    description: str = ""
    agents: list[str] = Field(min_length=1)
    meta: dict[str, Any] = Field(default_factory=dict)
    master: str
    model_config = ConfigDict(extra="forbid")


def references(data: SessionPresetData) -> dict[str, str]:
    errors = {}
    missing = [item for item in data.agents if not agent_preset.registry.exists(item)]
    if missing:
        errors["agents"] = f"Unknown: {', '.join(missing)}"
    if data.master not in data.agents:
        errors["master"] = "must be one of the session's agents"
    return errors


registry: PresetRegistry[SessionPresetData] = PresetRegistry(ROOT, SessionPresetData, "session", references)
