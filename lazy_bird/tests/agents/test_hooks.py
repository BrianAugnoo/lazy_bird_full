"""Message hooks: data hooks attach to messages, and how the LLM reads it."""

import pytest

from lazy_bird.agents import hook
from lazy_bird.crud import agent as agent_crud
from lazy_bird.crud import conversation as conversation_crud
from lazy_bird.crud import message as message_crud
from lazy_bird.crud import session as session_crud
from lazy_bird.crud import user as user_crud
from lazy_bird.errors import ConflictError
from lazy_bird.schemas.agent import AgentIn
from lazy_bird.schemas.session import SessionIn
from lazy_bird.schemas.user import UserIn

SYSTEM_HOOKS = ["default-system-System-date", "default-system-System-environment_information", "default-system-System-user_information"]


@pytest.fixture
def conversation(fake_inference) -> int:
    hook.initialize_hooks()
    session_id = session_crud.create(SessionIn(title="s", meta={"workspace": "lazy_bird"})).id
    agent_id = agent_crud.create(AgentIn(name="agent", session_id=session_id, instructions="Be nice.", hooks=SYSTEM_HOOKS)).id
    conversation_id = conversation_crud.create(agent_id).id
    conversation_crud.add_user_message(conversation_id, "Hello")
    return conversation_id


def test_the_yaml_leaves_out_keys_without_value_at_any_depth():
    hooks = {"system": {"Date": "2026-10-13", "User": {"Name": "Ada", "Age": None, "Extra": {"gone": None}}, "Nothing": None}, "empty": {}}

    assert hook.hooks_text(hooks) == "system:\n  Date: '2026-10-13'\n  User:\n    Name: Ada"
    assert hook.hooks_text({"system": {"Age": None}}) == ""


def test_multi_line_values_are_written_as_blocks():
    assert hook.hooks_text({"About": "line one\nline two"}) == "About: |-\n  line one\n  line two"


def test_hooks_go_after_the_system_prompt_and_before_the_user_text(conversation):
    system, prompt = message_crud.for_conversation(conversation)
    message_crud.edit_hooks(system.id, {"ext": {"Workspace": "lazy_bird", "Missing": None}})
    message_crud.edit_hooks(prompt.id, {"ext": {"Date": "today"}})

    formatted = hook.format_messages(conversation)

    assert [message.content for message in formatted] == ["Be nice.\next:\n  Workspace: lazy_bird", "ext:\n  Date: today\nHello"]
    assert [message.content for message in message_crud.for_conversation(conversation)] == ["Be nice.", "Hello"]


def test_messages_without_hooks_are_read_as_stored(conversation):
    assert hook.format_messages(conversation) == message_crud.for_conversation(conversation)


def test_each_hook_module_keeps_its_own_key(conversation):
    prompt = message_crud.last(conversation)
    message_crud.edit_hooks(prompt.id, {"first": {"a": 1}})
    message_crud.edit_hooks(prompt.id, {"second": {"b": 2}})

    assert message_crud.get(prompt.id).hooks == {"first": {"a": 1}, "second": {"b": 2}}


def test_hooks_only_attach_to_system_and_user_messages(conversation):
    answer = message_crud.create(conversation, "assistant", "Hi")

    with pytest.raises(ConflictError):
        message_crud.edit_hooks(answer.id, {"ext": {"a": 1}})


def test_the_system_hook_gives_the_date_the_environment_and_the_user(conversation):
    user_crud.create(UserIn(name="Ada", profession="Engineer", languages=["French", "English"]))

    hook.run_hooks(SYSTEM_HOOKS, conversation, {"workspace": "lazy_bird"})

    system, prompt = message_crud.for_conversation(conversation)
    assert set(prompt.hooks["system"]) == {"Date"}
    environment = system.hooks["system"]["Environment Information"]
    assert environment["Workspace"] == "lazy_bird" and environment["OS"]["system"]
    assert system.hooks["system"]["User Information"]["Languages"] == "French, English"
    instructions, question = hook.format_messages(conversation)
    assert instructions.content.startswith("Be nice.\nsystem:\n  Environment Information:")
    assert "    Name: Ada\n    Profession: Engineer\n" in instructions.content and "Age" not in instructions.content
    assert question.content.startswith("system:\n  Date: '") and question.content.endswith("'\nHello")


def test_the_system_hook_leaves_out_what_it_does_not_know(conversation):
    hook.run_hooks(SYSTEM_HOOKS, conversation, {})

    instructions = hook.format_messages(conversation)[0].content
    assert "Environment Information" in instructions
    assert "Workspace" not in instructions and "User Information" not in instructions


def test_the_date_stays_with_the_prompt_that_started_the_turn(conversation):
    message_crud.create(conversation, "tool-calling", None, {"tool_calls": []})

    hook.run_hooks(SYSTEM_HOOKS, conversation, {})

    assert message_crud.for_conversation(conversation)[1].hooks == {}
