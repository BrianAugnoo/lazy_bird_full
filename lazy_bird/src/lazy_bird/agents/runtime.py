"""What an agent needs to run a turn: its system prompt, tools and hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lazy_bird.agents import hook as hooks
from lazy_bird.agents import instruction as instructions
from lazy_bird.agents import skill as skills
from lazy_bird.agents import tools
from lazy_bird.agents.callables import Entry, Runner, unique
from lazy_bird.errors import NotFoundError
from lazy_bird.schemas.agent import AgentOut

SKILL_TOOLS = ("default-skills-load_skill", "default-skills-read_skill_file")


def tool_ids(agent: AgentOut) -> list[str]:
    """The agent's tools, plus the skill tools when it has skills."""
    return unique([*agent.tools, *(SKILL_TOOLS if agent.skills else ())])


def system_prompt(agent: AgentOut) -> str:
    parts = [instructions.compose(agent.instruction_fulls, agent.instruction_subs, agent.instructions), skills.listing(agent.skills)]
    return "\n\n".join(part for part in parts if part)


@dataclass
class AgentRuntime:
    agent: AgentOut
    system_prompt: str
    tools: list[dict[str, Any]]
    entries: dict[str, Entry]
    tool_runner: Runner
    meta: dict[str, Any] = field(default_factory=dict)

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        entry = self.entries.get(name)
        if entry is None:
            raise NotFoundError("Tool", name, code="unknown_tool")
        return self.tool_runner.call(entry, arguments)

    def run_hooks(self, conversation_id: int) -> None:
        hooks.run_hooks(self.agent.hooks, conversation_id, self.meta)


def build(agent: AgentOut, session_meta: dict[str, Any] | None) -> AgentRuntime:
    """Resolve an agent's references; raises ``NotFoundError`` for a missing extension item."""
    ids = tool_ids(agent)
    names = tools.llm_names(ids)
    entries = {names[tool_id]: tools.get(tool_id) for tool_id in ids}
    return AgentRuntime(
        agent=agent,
        system_prompt=system_prompt(agent),
        tools=[tools.llm_schema(entry, name) for name, entry in entries.items()],
        entries=entries,
        tool_runner=tools.runner(session_meta),
        meta=dict(session_meta or {}),
    )
