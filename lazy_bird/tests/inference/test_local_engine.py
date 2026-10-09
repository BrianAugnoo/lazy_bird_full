"""A local inference engine: its model lives in a host process, streams through it and stops when asked."""

import os
import threading

import pytest

import lazy_bird.inference as inference
import lazy_bird.tasks as tasks_module
from lazy_bird.crud import agent as agent_crud
from lazy_bird.crud import conversation as conversation_crud
from lazy_bird.crud import session as session_crud
from lazy_bird.inference import engine_family
from lazy_bird.inference.types import CallbackEmitter
from lazy_bird.residency import residency
from lazy_bird.schemas.agent import AgentIn
from lazy_bird.schemas.session import SessionIn
from lazy_bird.tasks.resources import ResourcePool
from lazy_bird.tasks.scheduler import Scheduler
from tests.conftest import wait_until


@pytest.fixture
def hosted_chat(crud_database, monkeypatch):
    """Makes a preset of the hosted chat engine (``tests/hosting/inference.py``) the default one."""
    import tests.hosting.inference as module

    monkeypatch.setattr(engine_family, "_loaded", dict(engine_family._loaded))
    engine = engine_family.register(module)
    return lambda **settings: engine_family.create_preset("hosted", engine.id, settings, default=True)


@pytest.fixture
def machine(migrated_database, monkeypatch):
    """A machine with 1000 MB of GPU memory."""
    pool = ResourcePool({"cpu": 8, "vram_mb": 1000, "ram_mb": 64000})
    monkeypatch.setattr(tasks_module, "_scheduler", Scheduler(pool, workers=2, poll_interval=0.02))
    return pool


def conversation() -> int:
    session_id = session_crud.create(SessionIn(title="s")).id
    agent_id = agent_crud.create(AgentIn(name="agent", session_id=session_id)).id
    conversation_id = conversation_crud.create(agent_id).id
    conversation_crud.add_user_message(conversation_id, "Hi")
    return conversation_id


def answer_in_thread(conversation_id: int, events: list) -> tuple[threading.Thread, list]:
    outcome: list = []
    thread = threading.Thread(target=lambda: outcome.append(inference.agentic_loop(conversation_id, emit=CallbackEmitter(events.append))))
    thread.start()
    return thread, outcome


def test_a_local_model_answers_from_its_own_process_and_its_tokens_are_streamed(hosted_chat):
    hosted_chat()
    events: list = []

    outcome = inference.agentic_loop(conversation(), emit=CallbackEmitter(events.append))

    assert outcome.reason == "completed", (outcome.answer.content, outcome.answer.meta)
    assert [event["delta"] for event in events if event["type"] == "token"] == ["hello ", "from ", "the ", "host "]
    assert [event["delta"] for event in events if event["type"] == "reasoning"] == ["pondering"]
    assert outcome.answer.content == "hello from the host"
    assert outcome.answer.meta["model"] != str(os.getpid())  # it answered from its host process


def test_stopping_the_conversation_stops_the_model_in_its_process(hosted_chat):
    hosted_chat(until_stopped=True)
    conversation_id, events = conversation(), []
    thread, outcome = answer_in_thread(conversation_id, events)
    wait_until(lambda: any(event.get("delta") == "thinking" for event in events), message="the model never started")
    [model] = residency().describe()
    assert model["users"] == [f"inference:{conversation_id}"]  # leased for this conversation

    assert inference.stop(conversation_id)
    thread.join(5)

    assert not thread.is_alive()
    assert outcome[0].answer.meta["stopped"] is True and outcome[0].answer.content == "thinking"


def test_an_engine_error_raised_in_the_host_keeps_its_code(hosted_chat):
    hosted_chat(error_code="model_refused")

    outcome = inference.agentic_loop(conversation())

    assert outcome.reason == "error"
    assert outcome.answer.meta["code"] == "model_refused" and outcome.answer.content == "The model refused (pretend)."


def test_a_local_model_waits_for_its_memory_and_says_so(hosted_chat, machine):
    hosted_chat(gpu_mb=600)
    machine.try_acquire("other-work", {"vram_mb": 800})  # 200 MB free: 400 are missing
    events: list = []
    thread, outcome = answer_in_thread(conversation(), events)
    wait_until(lambda: any(event.get("state") == "waiting_resources" for event in events), message="the wait was not shown")

    machine.release("other-work")
    thread.join(10)

    assert outcome[0].reason == "completed"
    [waiting] = [event for event in events if event.get("state") == "waiting_resources"]
    assert waiting["needs"] == {"vram_mb": 400}
