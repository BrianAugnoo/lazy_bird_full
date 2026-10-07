import threading

import pytest

import lazy_bird.inference as inference
from lazy_bird.agents import hook as hooks
from lazy_bird.agents import tools
from lazy_bird.agents.callables import Entry
from lazy_bird.crud import agent as agent_crud
from lazy_bird.crud import conversation as conversation_crud
from lazy_bird.crud import message as message_crud
from lazy_bird.crud import session as session_crud
from lazy_bird.errors import ConflictError, InvalidInputError
from lazy_bird.inference.types import CallbackEmitter, ChatResult, EngineError, ToolCall
from lazy_bird.schemas.agent import AgentIn
from lazy_bird.schemas.session import SessionIn


def echo(text: str) -> str:
    """
    Repeat a text.

    Args:
        text: The text to repeat.
    """
    if text == "boom":
        raise RuntimeError("echo exploded")
    return text.upper()


@pytest.fixture
def echo_tool(monkeypatch):
    entry = Entry(id="test-tools-echo", name="echo", extension="test", module="tools", file_path="test/tools.py", function=echo, description="Repeat", schema={"type": "function", "function": {"name": "echo", "description": "Repeat", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}}}})
    monkeypatch.setattr(tools._found, "entries", {**tools._found.entries, entry.id: entry})
    return entry


@pytest.fixture
def no_delay(monkeypatch):
    monkeypatch.setattr(inference, "MAX_RETRY_DELAY_SECONDS", 0)


def make_agent(**values) -> int:
    session_id = session_crud.create(SessionIn(title="s", meta={"workspace": "lazy_bird"})).id
    return agent_crud.create(AgentIn(name=values.pop("name", "agent"), session_id=session_id, instructions="Be nice.", **values)).id


def conversation_with(agent_id: int, *prompts: str) -> int:
    conversation = conversation_crud.create(agent_id)
    for prompt in prompts:
        conversation_crud.add_user_message(conversation.id, prompt)
    return conversation.id


def roles(conversation_id: int) -> list[str]:
    return [message.role for message in message_crud.for_conversation(conversation_id)]


def test_the_agent_waits_for_a_user_message(fake_inference):
    conversation = conversation_crud.create(make_agent())

    assert roles(conversation.id) == ["system"] and conversation.runnable is False
    with pytest.raises(ConflictError) as error:
        inference.agentic_loop(conversation.id)
    assert error.value.code == "nothing_to_answer"


def test_an_answer_is_streamed_then_stored(fake_inference):
    fake_inference.script = [ChatResult(content="Hello there friend", reasoning="greet")]
    conversation_id = conversation_with(make_agent(), "Hi")
    events = []

    outcome = inference.agentic_loop(conversation_id, emit=CallbackEmitter(events.append))

    assert outcome.reason == "completed"
    assert [event["delta"] for event in events if event["type"] == "token"] == ["Hello", " there", " friend"]
    assert [event["type"] for event in events][-2:] == ["message", "done"]
    answer = message_crud.for_conversation(conversation_id)[-1]
    assert (answer.role, answer.content, answer.meta["reasoning"], answer.meta["engine"]) == ("assistant", "Hello there friend", "greet", "fake-llm")
    sent = fake_inference.calls[0]["messages"]
    assert [(message.role, message.content) for message in sent] == [("system", "Be nice."), ("user", "Hi")]
    assert conversation_crud.get(conversation_id).runnable is False
    assert conversation_crud.get(conversation_id).title == "Hi"


def test_tools_are_called_and_their_results_sent_back(fake_inference, echo_tool):
    fake_inference.script = [
        ChatResult(tool_calls=[ToolCall("c1", "echo", {"text": "hi"}), ToolCall("c2", "echo", {"text": "boom"})]),
        ChatResult(content="Done"),
    ]
    conversation_id = conversation_with(make_agent(tools=[echo_tool.id]), "Echo hi")

    inference.agentic_loop(conversation_id)

    messages = message_crud.for_conversation(conversation_id)
    assert [message.role for message in messages] == ["system", "user", "tool-calling", "tool-response", "tool-response", "assistant"]
    assert (messages[3].content, messages[3].meta["status"]) == ("HI", "ok")
    assert messages[4].meta["status"] == "error" and "echo exploded" in messages[4].content
    second = fake_inference.calls[1]["messages"]
    assert second[2].tool_calls[0].name == "echo" and second[3].tool_call_id == "c1"
    assert fake_inference.calls[0]["tools"][0]["function"]["name"] == "echo"


def test_failures_are_retried_then_recorded_as_an_error_message(fake_inference, no_delay):
    fake_inference.script = [EngineError("down", code="engine_unreachable"), ChatResult(content="Recovered")]
    conversation_id = conversation_with(make_agent(), "Hi")
    events = []

    assert inference.agentic_loop(conversation_id, emit=CallbackEmitter(events.append)).reason == "completed"
    assert any(event.get("state") == "retrying" for event in events)

    conversation_crud.add_user_message(conversation_id, "Again")
    fake_inference.script = [EngineError("down", code="engine_unreachable")] * 3
    outcome = inference.agentic_loop(conversation_id, retry=2)

    error = message_crud.for_conversation(conversation_id)[-1]
    assert outcome.reason == "error"
    assert (error.role, error.content, error.meta["code"], error.meta["details"]["attempts"]) == ("error", "down", "engine_unreachable", 3)
    assert conversation_crud.get(conversation_id).runnable is True


def test_permanent_failures_are_not_retried(fake_inference, no_delay):
    fake_inference.script = [EngineError("bad key", code="engine_auth_failed", retryable=False), ChatResult(content="never")]
    conversation_id = conversation_with(make_agent(), "Hi")

    inference.agentic_loop(conversation_id)

    assert message_crud.for_conversation(conversation_id)[-1].meta["code"] == "engine_auth_failed"
    assert len(fake_inference.calls) == 1


def test_error_messages_are_never_sent_to_the_llm(fake_inference, no_delay):
    fake_inference.script = [EngineError("down", retryable=False), ChatResult(content="Fine now")]
    conversation_id = conversation_with(make_agent(), "Hi")
    inference.agentic_loop(conversation_id)

    inference.agentic_loop(conversation_id)

    assert [message.role for message in fake_inference.calls[1]["messages"]] == ["system", "user"]
    assert roles(conversation_id)[-2:] == ["error", "assistant"]


def test_hooks_run_before_the_conversation_is_read(fake_inference, monkeypatch):
    seen = []

    def inject(conversation_id):
        seen.append(conversation_id)
        message_crud.create(conversation_id, "system", "Today is Tuesday.")

    entry = Entry(id="test-hooks-inject", name="inject", extension="test", module="hooks", file_path="test/hooks.py", function=inject)
    monkeypatch.setattr(hooks._found, "entries", {entry.id: entry})
    fake_inference.script = [ChatResult(content="Tuesday")]
    conversation_id = conversation_with(make_agent(hooks=[entry.id]), "Which day?")

    inference.agentic_loop(conversation_id)

    assert seen == [conversation_id]
    assert fake_inference.calls[0]["messages"][-1].content == "Today is Tuesday."


def test_a_failing_hook_stops_the_turn(fake_inference, monkeypatch):
    def refuse(conversation_id):
        raise PermissionError("unsafe request")

    entry = Entry(id="test-hooks-refuse", name="refuse", extension="test", module="hooks", file_path="test/hooks.py", function=refuse)
    monkeypatch.setattr(hooks._found, "entries", {entry.id: entry})
    conversation_id = conversation_with(make_agent(hooks=[entry.id]), "Hi")

    outcome = inference.agentic_loop(conversation_id)

    assert outcome.reason == "error" and outcome.answer.meta["code"] == "hook_failed"
    assert fake_inference.calls == []


def test_stopping_keeps_the_partial_answer(fake_inference):
    def slow(messages, emit):
        emitter.stop()
        return ChatResult(content="one two three")

    emitter = CallbackEmitter(lambda event: None)
    fake_inference.script = [slow]
    conversation_id = conversation_with(make_agent(), "Hi")

    outcome = inference.agentic_loop(conversation_id, emit=emitter)

    assert outcome.reason == "stopped"
    assert outcome.answer.meta["stopped"] is True


def test_a_conversation_runs_once_at_a_time(fake_inference):
    entered, release = threading.Event(), threading.Event()

    def blocking(messages, emit):
        entered.set()
        release.wait(5)
        return ChatResult(content="late")

    fake_inference.script = [blocking]
    conversation_id = conversation_with(make_agent(), "Hi")
    thread = threading.Thread(target=inference.agentic_loop, args=(conversation_id,))
    thread.start()
    entered.wait(5)

    assert conversation_crud.get(conversation_id).running is True
    with pytest.raises(ConflictError) as error:
        inference.agentic_loop(conversation_id)
    assert error.value.code == "conversation_busy"
    release.set()
    thread.join(5)
    assert conversation_crud.get(conversation_id).running is False


def test_endless_tool_loops_end_with_an_error(fake_inference, echo_tool):
    fake_inference.script = [ChatResult(tool_calls=[ToolCall(f"c{index}", "echo", {"text": "x"})]) for index in range(5)]
    conversation_id = conversation_with(make_agent(tools=[echo_tool.id]), "Loop")

    outcome = inference.agentic_loop(conversation_id, max_iter=3)

    assert outcome.answer.meta["code"] == "max_iterations"


def test_parents_delegate_tasks_to_their_sub_agents(fake_inference):
    child_id = make_agent(name="researcher", description="Finds facts")
    child = agent_crud.get(child_id)
    parent_id = agent_crud.create(AgentIn(name="lead", session_id=child.session_id, sub_agents_ids=[child_id])).id
    fake_inference.script = [
        ChatResult(tool_calls=[ToolCall("d1", "delegate_to_agent", {"agent": "researcher", "task": "Find the capital of France"})]),
        ChatResult(content="Paris"),
        ChatResult(content="The researcher says Paris."),
    ]
    conversation_id = conversation_with(parent_id, "Capital of France?")
    events = []

    inference.agentic_loop(conversation_id, emit=CallbackEmitter(events.append))

    parent_messages = message_crud.for_conversation(conversation_id)
    assert parent_messages[-2].content == "Paris" and parent_messages[-1].content == "The researcher says Paris."
    [child_conversation] = conversation_crud.get_all(child_id)
    assert child_conversation.title == "Task from lead"
    assert any(event["type"] == "delegation" for event in events)
    tool_names = [tool["function"]["name"] for tool in fake_inference.calls[0]["tools"]]
    assert tool_names == ["delegate_to_agent"]


def test_agents_need_an_inference_configuration(crud_database):
    session_id = session_crud.create(SessionIn(title="s")).id

    with pytest.raises(InvalidInputError) as error:
        agent_crud.create(AgentIn(name="a", session_id=session_id))

    assert error.value.code == "no_inference_preset"


def test_agent_inference_configuration_is_validated(fake_inference):
    session_id = session_crud.create(SessionIn(title="s")).id

    default = agent_crud.create(AgentIn(name="a", session_id=session_id))
    custom = agent_crud.create(AgentIn(name="b", session_id=session_id, meta={"inference_engine_id": fake_inference.engine.id, "inference_settings": {"label": "x"}, "color": "blue"}))

    assert default.meta == {"preset_inference_engine_id": fake_inference.preset.id}
    assert custom.meta["inference_settings"] == {"label": "x"} and custom.meta["color"] == "blue"
    with pytest.raises(InvalidInputError) as error:
        agent_crud.create(AgentIn(name="c", session_id=session_id, meta={"inference_engine_id": fake_inference.engine.id, "inference_settings": {"wrong": 1}}))
    assert "meta.inference_settings.wrong" in error.value.details["fields"]
    with pytest.raises(InvalidInputError):
        agent_crud.update(default.id, {"meta": {"preset_inference_engine_id": 404}})


def test_unanswered_tool_calls_are_closed_when_the_user_writes(fake_inference):
    conversation_id = conversation_with(make_agent(), "Hi")
    message_crud.create(conversation_id, "tool-calling", None, {"tool_calls": [{"id": "x1", "name": "echo", "arguments": {}}]})

    conversation_crud.add_user_message(conversation_id, "Never mind")

    messages = message_crud.for_conversation(conversation_id)
    assert [message.role for message in messages[-3:]] == ["tool-calling", "tool-response", "user"]
    assert messages[-2].meta == {"tool_call_id": "x1", "name": "echo", "status": "cancelled"}


def test_an_interrupted_tool_turn_resumes_with_its_tools(fake_inference, echo_tool):
    conversation_id = conversation_with(make_agent(tools=[echo_tool.id]), "Echo")
    message_crud.create(conversation_id, "tool-calling", None, {"tool_calls": [{"id": "x1", "name": "echo", "arguments": {"text": "again"}}]})
    fake_inference.script = [ChatResult(content="Resumed")]

    inference.agentic_loop(conversation_id)

    assert roles(conversation_id)[-3:] == ["tool-calling", "tool-response", "assistant"]
    assert message_crud.for_conversation(conversation_id)[-2].content == "AGAIN"
