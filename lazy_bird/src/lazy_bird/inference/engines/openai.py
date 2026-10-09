"""Inference through any OpenAI-compatible chat completions API (OpenAI, vLLM, Ollama, proxies...)."""

import json

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from lazy_bird.crud.api_key import find_key
from lazy_bird.inference.types import ChatMessage, ChatResult, Emitter, EngineError, ToolCall

name = "openai-client"
local = False  # the model runs on a server, not on this machine


class EngineSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key_name: str | None = Field(default=None, title="API key", description="Name of a stored API key; empty for servers without authentication.")
    base_url: str = Field(title="Base URL", description="OpenAI-compatible endpoint, e.g. https://api.openai.com/v1")
    model_name: str = Field(title="Model name")
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, title="Max output tokens")
    timeout: float = Field(default=120, gt=0, description="Seconds before a request is abandoned.")


fields = {
    "api_key_name": {
        "default_field": True,
        "content": "default.basic.reference",
        "args": {"endpoint": "/api-keys/", "value_key": "name", "label_key": "name"},
    },
}


def _client(settings: EngineSettings) -> OpenAI:
    api_key = "no-key"
    if settings.api_key_name:
        api_key = find_key(settings.api_key_name)
        if not api_key:
            raise EngineError(f"No API key named '{settings.api_key_name}' is stored.", code="api_key_missing", retryable=False)
    return OpenAI(base_url=settings.base_url, api_key=api_key, timeout=settings.timeout, max_retries=0)


def _to_openai(messages: list[ChatMessage]) -> list[dict]:
    converted = []
    for message in messages:
        if message.role == "tool":
            converted.append({"role": "tool", "tool_call_id": message.tool_call_id, "content": message.content or ""})
        elif message.tool_calls:
            converted.append(
                {
                    "role": "assistant",
                    "content": message.content or None,
                    "tool_calls": [
                        {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": json.dumps(call.arguments)}}
                        for call in message.tool_calls
                    ],
                }
            )
        else:
            converted.append({"role": message.role, "content": message.content or ""})
    return converted


def _engine_error(error: Exception) -> EngineError:
    import openai

    permanent = {
        openai.AuthenticationError: "engine_auth_failed",
        openai.PermissionDeniedError: "engine_auth_failed",
        openai.NotFoundError: "engine_model_not_found",
        openai.BadRequestError: "engine_bad_request",
        openai.UnprocessableEntityError: "engine_bad_request",
    }
    for kind, code in permanent.items():
        if isinstance(error, kind):
            return EngineError(f"The inference server refused the request: {error}", code=code, retryable=False)
    if isinstance(error, openai.RateLimitError):
        return EngineError(f"The inference server is rate limiting: {error}", code="engine_rate_limited")
    if isinstance(error, (openai.APIConnectionError, openai.APITimeoutError)):
        return EngineError(f"The inference server cannot be reached: {error}", code="engine_unreachable")
    return EngineError(f"The inference server failed: {error}", code="engine_server_error")


def chat(messages: list[ChatMessage], tools: list[dict], settings: EngineSettings, model, emit: Emitter) -> ChatResult:
    """Stream a chat completion, emitting tokens and reasoning as they arrive."""
    client = _client(settings)
    options = {key: value for key, value in {"temperature": settings.temperature, "max_tokens": settings.max_tokens}.items() if value is not None}
    result = ChatResult(model=settings.model_name)
    pending: dict[int, dict[str, str]] = {}
    content, reasoning = [], []
    try:
        stream = client.chat.completions.create(
            model=settings.model_name, messages=_to_openai(messages), tools=tools or None, stream=True, **options
        )
        for chunk in stream:
            if emit.stopped:
                stream.close()
                result.stopped = True
                break
            if getattr(chunk, "usage", None):
                result.usage = chunk.usage.model_dump()
            if chunk.choices and chunk.model and chunk.model != "keepalive":
                result.model = chunk.model
            for choice in chunk.choices[:1]:
                delta = choice.delta
                if delta.content:
                    content.append(delta.content)
                    emit.token(delta.content)
                thought = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
                if isinstance(thought, str) and thought:
                    reasoning.append(thought)
                    emit.reasoning(thought)
                for call in delta.tool_calls or []:
                    slot = pending.setdefault(call.index, {"id": "", "name": "", "arguments": ""})
                    slot["id"] = call.id or slot["id"]
                    if call.function is not None:
                        slot["name"] += call.function.name or ""
                        slot["arguments"] += call.function.arguments or ""
    except EngineError:
        raise
    except Exception as error:
        raise _engine_error(error) from error
    result.content = "".join(content)
    result.reasoning = "".join(reasoning) or None
    if not result.stopped:
        result.tool_calls = [_tool_call(index, slot) for index, slot in sorted(pending.items())]
    return result


def _tool_call(index: int, slot: dict[str, str]) -> ToolCall:
    try:
        arguments = json.loads(slot["arguments"] or "{}")
    except ValueError:
        arguments = {"__invalid_json__": slot["arguments"]}
    return ToolCall(id=slot["id"] or f"call_{index}", name=slot["name"], arguments=arguments if isinstance(arguments, dict) else {"value": arguments})
