"""What an agent needs to run a turn: its system prompt, tools and hooks.

Besides the tools listed in ``Agent.tools``, an agent gets built-in tools:

- ``load_skill`` / ``read_skill_file`` when it has skills;
- ``delegate_to_agent`` when it has sub-agents: it gives a task to one of them,
  which works on it in a new conversation of its own and returns its final answer.

Registry tools whose name collides with a built-in one are shown under their id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from lazy_bird.agents import hook as hooks
from lazy_bird.agents import instruction as instructions
from lazy_bird.agents import skill as skills
from lazy_bird.agents import tools
from lazy_bird.agents.callables import Entry, Runner, unique
from lazy_bird.errors import NotFoundError
from lazy_bird.schemas.agent import AgentOut

SKILL_TOOLS = ("default-skills-load_skill", "default-skills-read_skill_file")
DELEGATE_TOOL = "delegate_to_agent"


def tool_ids(agent: AgentOut) -> list[str]:
    """The agent's registry tools, plus the skill tools when it has skills."""
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
    builtins: dict[str, Callable[[dict[str, Any]], Any]] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        if name in self.builtins:
            return self.builtins[name](arguments or {})
        entry = self.entries.get(name)
        if entry is None:
            raise NotFoundError("Tool", name, code="unknown_tool")
        return self.tool_runner.call(entry, arguments)

    def run_hooks(self, conversation_id: int) -> None:
        hooks.run_hooks(self.agent.hooks, conversation_id, self.meta)


def _delegation(agent: AgentOut, emitter) -> tuple[dict[str, Any], Callable[[dict[str, Any]], Any]] | None:
    """The ``delegate_to_agent`` tool of an agent directing sub-agents."""
    from lazy_bird.crud import agent as agent_crud

    children = [agent_crud.get(child_id) for child_id in agent.sub_agents_ids]
    if not children:
        return None
    by_name = {child.name: child for child in children}
    roster = "\n".join(f"- {child.name}: {child.description or 'no description'}" for child in children)
    schema = {
        "type": "function",
        "function": {
            "name": DELEGATE_TOOL,
            "description": f"Give a task to one of the agents you direct and get its answer.\nAgents:\n{roster}",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "enum": list(by_name), "description": "Name of the agent."},
                    "task": {"type": "string", "description": "Self-contained description of the task, with all the context it needs."},
                },
                "required": ["agent", "task"],
            },
        },
    }

    def delegate(arguments: dict[str, Any]) -> str:
        from lazy_bird.inference import delegate as run_delegation

        child = by_name.get(arguments.get("agent", ""))
        if child is None:
            raise NotFoundError("Agent", arguments.get("agent"), code="unknown_sub_agent")
        return run_delegation(agent, child, str(arguments.get("task", "")), emitter)

    return schema, delegate


def build(agent: AgentOut, session_meta: dict[str, Any] | None, emitter=None) -> AgentRuntime:
    """Resolve an agent's references; raises ``NotFoundError`` for a missing extension item."""
    builtins: dict[str, Callable[[dict[str, Any]], Any]] = {}
    schemas: list[dict[str, Any]] = []
    delegation = _delegation(agent, emitter)
    if delegation is not None:
        schemas.append(delegation[0])
        builtins[DELEGATE_TOOL] = delegation[1]
    ids = tool_ids(agent)
    names = {tool_id: (tool_id if name in builtins else name) for tool_id, name in tools.llm_names(ids).items()}
    entries = {names[tool_id]: tools.get(tool_id) for tool_id in ids}
    schemas += [tools.llm_schema(entry, name) for name, entry in entries.items()]
    return AgentRuntime(
        agent=agent,
        system_prompt=system_prompt(agent),
        tools=schemas,
        entries=entries,
        tool_runner=tools.runner(session_meta),
        builtins=builtins,
        meta=dict(session_meta or {}),
    )
