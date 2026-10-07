"""Agents of sessions, their hierarchy and their creation from presets."""

from __future__ import annotations

from typing import Any

from sqlmodel import select

from lazy_bird.agents import agent_preset
from lazy_bird.agents import hook as hooks
from lazy_bird.agents import instruction as instructions
from lazy_bird.agents import skill as skills
from lazy_bird.agents import tools
from lazy_bird.database import db
from lazy_bird.errors import ConflictError, InvalidInputError, NotFoundError
from lazy_bird.models.agent import Agent as AgentORM, AgentHierarchy
from lazy_bird.models.session import Session as SessionORM
from lazy_bird.schemas.agent import AgentIn, AgentOut, AgentToolOut

LIST_FIELDS = ("instruction_fulls", "instruction_subs", "skills", "tools", "hooks")


def _exists(getter, value: str) -> bool:
    try:
        getter(value)
    except NotFoundError:
        return False
    return True


def reference_errors(values: dict[str, list[str]]) -> dict[str, str]:
    """One message per list holding ids of extension items that do not exist."""
    checks = {
        "tools": lambda item: _exists(tools.get, item),
        "hooks": lambda item: _exists(hooks.get, item),
        "skills": skills.exists,
        "instruction_fulls": lambda item: instructions.exists("full", item),
        "instruction_subs": lambda item: instructions.exists("sub", item),
    }
    errors = {}
    for key, exists in checks.items():
        missing = [item for item in values.get(key) or [] if not exists(item)]
        if missing:
            errors[key] = f"Unknown: {', '.join(missing)}"
    return errors


def _out(agent: AgentORM) -> AgentOut:
    values = {key: list(getattr(agent, key) or []) for key in LIST_FIELDS}
    errors = reference_errors(values)
    return AgentOut(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        instructions=agent.instructions,
        master=agent.master,
        meta=agent.meta,
        session_id=agent.session_id,
        preset=agent.preset,
        sub_agents_ids=[child.id for child in agent.sub_agents],
        parent_agents_ids=[parent.id for parent in agent.parent_agents],
        valid=not errors,
        errors=errors,
        **values,
    )


def _row(session, agent_id: int) -> AgentORM:
    agent = session.get(AgentORM, agent_id)
    if agent is None:
        raise NotFoundError("Agent", agent_id)
    return agent


def _require_session(session, session_id: int) -> SessionORM:
    found = session.get(SessionORM, session_id)
    if found is None:
        raise NotFoundError("Session", session_id)
    return found


def _check_master(session, session_id: int, agent_id: int | None) -> None:
    query = select(AgentORM).where(AgentORM.session_id == session_id, AgentORM.master == True)  # noqa: E712
    existing = session.exec(query).first()
    if existing is not None and existing.id != agent_id:
        raise ConflictError(f"Session {session_id} already has a master agent ({existing.name}).", code="master_exists")


def _check_references(values: dict[str, Any]) -> None:
    errors = reference_errors(values)
    if errors:
        raise InvalidInputError("The agent references extension items that do not exist.", code="invalid_agent", details={"fields": errors})


def _set_children(session, agent: AgentORM, children_ids: list[int]) -> None:
    """Replace the sub-agents of an agent (same session, no self, no cycle)."""
    for link in session.exec(select(AgentHierarchy).where(AgentHierarchy.parent_id == agent.id)).all():
        session.delete(link)
    session.flush()
    for child_id in dict.fromkeys(children_ids):
        child = _row(session, child_id)
        if child.id == agent.id or child.session_id != agent.session_id:
            raise InvalidInputError("Sub-agents must be other agents of the same session.", code="invalid_sub_agent", details={"fields": {"sub_agents_ids": f"Invalid: {child_id}"}})
        if _descends(session, child.id, agent.id):
            raise InvalidInputError("Sub-agents cannot form a cycle.", code="agent_cycle", details={"fields": {"sub_agents_ids": f"{child_id} already directs this agent"}})
        session.add(AgentHierarchy(parent_id=agent.id, child_id=child.id))


def _descends(session, start: int, target: int) -> bool:
    """Whether ``target`` is reachable from ``start`` through sub-agent links."""
    pending, seen = [start], set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(link.child_id for link in session.exec(select(AgentHierarchy).where(AgentHierarchy.parent_id == current)).all())
    return False


def get_all() -> list[AgentOut]:
    with db() as session:
        return [_out(agent) for agent in session.exec(select(AgentORM).order_by(AgentORM.id)).all()]


def get(agent_id: int) -> AgentOut:
    with db() as session:
        return _out(_row(session, agent_id))


def get_by_id(agent_id: int) -> AgentOut | None:
    try:
        return get(agent_id)
    except NotFoundError:
        return None


def get_by_session(session_id: int) -> list[AgentOut]:
    with db() as session:
        _require_session(session, session_id)
        agents = session.exec(select(AgentORM).where(AgentORM.session_id == session_id).order_by(AgentORM.id)).all()
        return [_out(agent) for agent in agents]


def create(payload: AgentIn) -> AgentOut:
    data = payload.model_dump(exclude={"sub_agents_ids"})
    _check_references(data)
    with db() as session:
        _require_session(session, payload.session_id)
        if payload.master:
            _check_master(session, payload.session_id, None)
        agent = AgentORM(**data)
        session.add(agent)
        session.flush()
        _set_children(session, agent, payload.sub_agents_ids)
        session.commit()
        session.refresh(agent)
        return _out(agent)


def update(agent_id: int, changes: dict[str, Any]) -> AgentOut:
    children = changes.pop("sub_agents_ids", None)
    _check_references({key: value for key, value in changes.items() if key in LIST_FIELDS})
    with db() as session:
        agent = _row(session, agent_id)
        if changes.get("master"):
            _check_master(session, agent.session_id, agent.id)
        for key, value in changes.items():
            setattr(agent, key, value)
        if children is not None:
            _set_children(session, agent, children)
        session.add(agent)
        session.commit()
        session.refresh(agent)
        return _out(agent)


def delete(agent_id: int) -> None:
    with db() as session:
        agent = _row(session, agent_id)
        for link in session.exec(select(AgentHierarchy).where((AgentHierarchy.parent_id == agent_id) | (AgentHierarchy.child_id == agent_id))).all():
            session.delete(link)
        session.delete(agent)
        session.commit()


def tools_of(agent_id: int) -> list[AgentToolOut]:
    """The tools of an agent under the names its LLM sees."""
    from lazy_bird.agents.runtime import tool_ids

    agent = get(agent_id)
    ids = [tool_id for tool_id in tool_ids(agent) if _exists(tools.get, tool_id)]
    names = tools.llm_names(ids)
    return [AgentToolOut(id=tool_id, name=names[tool_id], description=tools.get(tool_id).description) for tool_id in ids]


# ------------------------------------------------------------------- from presets
def create_from_preset(session_id: int, preset_id: str) -> AgentOut:
    """Create an agent from a preset, with its sub-agents.

    Sub-agents reuse an agent of the session created from the same preset when there
    is one; otherwise they are created too. Returns the new agent.
    """
    with db() as session:
        _require_session(session, session_id)
        existing: dict[str, int] = {}
        for agent in session.exec(select(AgentORM).where(AgentORM.session_id == session_id).order_by(AgentORM.id)).all():
            if agent.preset:
                existing.setdefault(agent.preset, agent.id)
    agent_id = instantiate(session_id, preset_id, existing, ())
    return get(agent_id)


def instantiate(session_id: int, preset_id: str, existing: dict[str, int], chain: tuple[str, ...]) -> int:
    """Create the agent of ``preset_id`` (and missing sub-agents); return its id.

    ``existing`` maps preset ids to agents already in the session; it is updated.
    """
    if preset_id in chain:
        raise InvalidInputError(
            f"Agent presets form a cycle: {' -> '.join((*chain, preset_id))}.", code="preset_cycle", details={"preset": preset_id}
        )
    data = agent_preset.registry.valid_data(preset_id)
    children = [
        existing.get(child) or instantiate(session_id, child, existing, (*chain, preset_id))
        for child in data.sub_agents
    ]
    with db() as session:
        agent = AgentORM(
            name=data.name,
            description=data.description,
            session_id=session_id,
            tools=data.tools,
            hooks=data.hooks,
            skills=data.skills,
            instruction_fulls=data.instruction_fulls,
            instruction_subs=data.instruction_subs,
            preset=preset_id,
        )
        session.add(agent)
        session.flush()
        _set_children(session, agent, children)
        session.commit()
        existing.setdefault(preset_id, agent.id)
        return agent.id
