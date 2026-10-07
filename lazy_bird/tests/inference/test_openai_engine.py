from types import SimpleNamespace

import httpx
import openai
import pytest

from lazy_bird.inference.engines import openai as engine
from lazy_bird.inference.types import CallbackEmitter, ChatMessage, EngineError, ToolCall


def chunk(content=None, reasoning=None, tool_calls=None, model="m"):
    delta = SimpleNamespace(content=content, reasoning=reasoning, tool_calls=tool_calls)
    return SimpleNamespace(model=model, usage=None, choices=[SimpleNamespace(delta=delta)])


def tool_delta(index, id=None, name=None, arguments=None):
    return SimpleNamespace(index=index, id=id, function=SimpleNamespace(name=name, arguments=arguments))


class FakeStream(list):
    closed = False

    def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, stream):
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.stream = stream

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if isinstance(self.stream, Exception):
            raise self.stream
        return self.stream


SETTINGS = engine.EngineSettings(base_url="http://llm", model_name="m", temperature=0.2)


def run(monkeypatch, stream, emitter=None):
    client = FakeClient(stream)
    monkeypatch.setattr(engine, "_client", lambda settings: client)
    events = []
    result = engine.chat([ChatMessage("user", "hi")], [], SETTINGS, None, emitter or CallbackEmitter(events.append))
    return result, events, client


def test_tokens_and_reasoning_are_emitted_while_streaming(monkeypatch):
    result, events, client = run(monkeypatch, FakeStream([chunk(reasoning="think"), chunk(content="Hel"), chunk(content="lo")]))

    assert result.content == "Hello" and result.reasoning == "think"
    assert [event["type"] for event in events] == ["reasoning", "token", "token"]
    assert client.requests[0]["stream"] is True and client.requests[0]["temperature"] == 0.2


def test_tool_call_fragments_are_assembled(monkeypatch):
    stream = FakeStream(
        [
            chunk(tool_calls=[tool_delta(0, id="a", name="sea", arguments='{"q"')]),
            chunk(tool_calls=[tool_delta(0, name="rch", arguments=': "x"}'), tool_delta(1, id="b", name="fetch", arguments="not json")]),
        ]
    )

    result, _, _ = run(monkeypatch, stream)

    assert result.tool_calls == [ToolCall("a", "search", {"q": "x"}), ToolCall("b", "fetch", {"__invalid_json__": "not json"})]


def test_stopping_closes_the_stream_and_drops_tool_calls(monkeypatch):
    emitter = CallbackEmitter(lambda event: None)
    emitter.stop()
    stream = FakeStream([chunk(content="never")])

    result, _, _ = run(monkeypatch, stream, emitter)

    assert result.stopped and result.content == "" and stream.closed


def test_history_is_converted_to_the_openai_format():
    converted = engine._to_openai(
        [
            ChatMessage("system", "rules"),
            ChatMessage("assistant", None, tool_calls=(ToolCall("a", "search", {"q": 1}),)),
            ChatMessage("tool", "result", tool_call_id="a", name="search"),
        ]
    )

    assert converted[1]["tool_calls"][0]["function"] == {"name": "search", "arguments": '{"q": 1}'}
    assert converted[2] == {"role": "tool", "tool_call_id": "a", "content": "result"}


@pytest.mark.parametrize(
    ("error", "code", "retryable"),
    [
        (openai.AuthenticationError("no", response=httpx.Response(401, request=httpx.Request("POST", "http://x")), body=None), "engine_auth_failed", False),
        (openai.RateLimitError("slow", response=httpx.Response(429, request=httpx.Request("POST", "http://x")), body=None), "engine_rate_limited", True),
        (openai.APIConnectionError(request=httpx.Request("POST", "http://x")), "engine_unreachable", True),
    ],
)
def test_sdk_errors_become_typed_engine_errors(monkeypatch, error, code, retryable):
    with pytest.raises(EngineError) as raised:
        run(monkeypatch, error)

    assert (raised.value.code, raised.value.retryable) == (code, retryable)
