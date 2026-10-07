"""Agent presets: ``agent_preset/{extension_name}/{name}.json``.

Keys (unknown keys are rejected):

- ``name``: must equal the file name;
- ``description``: shown to users and to parent agents;
- ``tools`` / ``hooks``: tool and hook ids (``{extension}-{module}-{function}``);
- ``skills``: skill ids (``{extension}/{name}``);
- ``sub_agents``: agent preset ids (``{extension}/{name}``) this agent directs;
- ``instruction_fulls`` / ``instruction_subs``: instruction ids (``{extension}/{name}``).

There is no ``parent_agents`` key: a sub-agent must be able to work alone.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from lazy_bird.agents import hook as hooks
from lazy_bird.agents import instruction as instructions
from lazy_bird.agents import skill as skills
from lazy_bird.agents import tools
from lazy_bird.agents.presets import PresetRegistry
from lazy_bird.errors import NotFoundError

ROOT = Path(__file__).resolve().parent


class AgentPresetData(BaseModel):
    name: str
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    sub_agents: list[str] = Field(default_factory=list)
    instruction_fulls: list[str] = Field(default_factory=list)
    instruction_subs: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")


def _missing(values: list[str], exists) -> list[str]:
    return [value for value in values if not exists(value)]


def _found(getter):
    def exists(value: str) -> bool:
        try:
            getter(value)
        except NotFoundError:
            return False
        return True

    return exists


def references(data: AgentPresetData) -> dict[str, str]:
    """One message per key whose references do not exist."""
    checks = {
        "tools": _missing(data.tools, _found(tools.get)),
        "hooks": _missing(data.hooks, _found(hooks.get)),
        "skills": _missing(data.skills, skills.exists),
        "instruction_fulls": _missing(data.instruction_fulls, lambda item: instructions.exists("full", item)),
        "instruction_subs": _missing(data.instruction_subs, lambda item: instructions.exists("sub", item)),
        "sub_agents": _missing(data.sub_agents, lambda item: registry.exists(item)),
    }
    return {key: f"Unknown: {', '.join(missing)}" for key, missing in checks.items() if missing}


registry: PresetRegistry[AgentPresetData] = PresetRegistry(ROOT, AgentPresetData, "agent", references)
