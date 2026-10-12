"""Bounded database work for lists whose histories can grow without bound."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event
from sqlmodel import Session

from lazy_bird.crud import agent, conversation, task
from lazy_bird.models.agent import Agent, AgentHierarchy
from lazy_bird.models.conversation import Conversation
from lazy_bird.models.message import Message
from lazy_bird.models.session import Session as SessionRow
from lazy_bird.models.task import Task


@pytest.fixture
def loaded_rows():
    rows = []

    def loaded(session, row):
        rows.append(row)

    event.listen(Session, "loaded_as_persistent", loaded)
    try:
        yield rows
    finally:
        event.remove(Session, "loaded_as_persistent", loaded)


def test_conversation_summaries_read_last_roles_without_loading_histories(crud_database, sql_activity, loaded_rows):
    with crud_database() as session:
        session.add(SessionRow(id=1, title="s"))
        session.flush()
        session.add(Agent(id=1, name="a", session_id=1))
        session.flush()
        for id, role in enumerate((None, "system", "user", "assistant", "tool-calling", "tool-response", "error"), 1):
            session.add(Conversation(id=id, agent_id=1, title=str(id)))
            session.flush()
            if role:
                session.add_all([Message(conversation_id=id, role="user", content="history" * 100) for _ in range(30)])
                session.flush()
                session.add(Message(conversation_id=id, role=role, content="last"))
        session.commit()
    sql_activity["statements"].clear()

    summaries = conversation.get_all()

    assert {item.id for item in summaries if item.runnable} == {3, 5, 6, 7}
    assert len(sql_activity["statements"]) == 1
    assert not any(isinstance(row, Message) for row in loaded_rows)
    assert conversation.get(1).runnable is False
    assert conversation.latest(1).id == summaries[0].id
    assert len(conversation.detail(3).messages) == 31


def test_agent_relationships_are_loaded_in_batches(crud_database, sql_activity):
    with crud_database() as session:
        session.add(SessionRow(id=1, title="s"))
        session.flush()
        session.add_all([Agent(id=id, name=str(id), session_id=1) for id in range(1, 41)])
        session.flush()
        session.add_all([AgentHierarchy(parent_id=1, child_id=id) for id in range(2, 41)])
        session.commit()
    sql_activity["statements"].clear()

    agents = agent.get_by_session(1)

    assert len(agents) == 40
    assert agents[0].sub_agents_ids == list(range(2, 41))
    assert all(item.parent_agents_ids == [1] for item in agents[1:])
    assert len(sql_activity["statements"]) == 4  # session, agents, both directions of links


def test_task_lists_limit_loaded_rows_and_keep_the_existing_order(crud_database, loaded_rows):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with crud_database() as session:
        session.add_all([
            Task(id=1, kind="k", title="running", status="running", priority=5),
            Task(id=2, kind="k", title="queued", priority=1),
            Task(id=3, kind="other", title="paused", status="paused", priority=3),
            *[Task(id=id, kind="k", title="finished", status="completed", finished_at=now + timedelta(seconds=id)) for id in range(4, 504)],
        ])
        session.commit()

    assert [row.id for row in task.list_tasks(limit=5)] == [1, 2, 3, 503, 502]
    assert len(loaded_rows) == 5
    assert [row.id for row in task.list_tasks(statuses=["completed"], limit=2)] == [503, 502]
    assert [row.id for row in task.list_tasks(kind="other")] == [3]
    assert task.list_tasks(limit=0) == []


def test_scheduler_does_not_load_future_tasks(crud_database, loaded_rows):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with crud_database() as session:
        session.add_all([
            Task(id=1, kind="k", title="now", run_at=now, priority=2),
            Task(id=2, kind="k", title="immediate", priority=1),
            *[Task(kind="k", title="future", run_at=now + timedelta(days=1)) for _ in range(500)],
        ])
        session.commit()

    assert [row.id for row in task.ready(now.astimezone(timezone(timedelta(hours=4))))] == [2, 1]
    assert len(loaded_rows) == 2


def test_task_pruning_keeps_latest_finished_and_all_active_without_loading_rows(crud_database, loaded_rows):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with crud_database() as session:
        session.add_all([
            Task(id=1, kind="k", title="queued"),
            *[Task(id=id, kind="k", title="finished", status="completed", finished_at=now) for id in range(2, 202)],
        ])
        session.commit()

    assert task.prune_finished(2) == 198
    assert loaded_rows == []
    assert {row.id for row in task.list_tasks()} == {1, 200, 201}
    assert task.clear_finished() == 2
    assert [row.id for row in task.list_tasks()] == [1]
