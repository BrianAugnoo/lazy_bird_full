import json

from pydantic import BaseModel, ConfigDict, Field
from openai import OpenAI
from lazy_bird.schemas.inference_engine import Response
from lazy_bird.crud.api_key import find_key
from lazy_bird.schemas.message import MessageOut
from lazy_bird.logging_config import traced

name = "openai-client"


class EngineSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key_name: str | None = Field(default=None, title="API key", description="Name of a stored API key; empty for servers without authentication.")
    base_url: str = Field(title="Base URL", description="OpenAI-compatible endpoint, e.g. https://api.openai.com/v1")
    model_name: str = Field(title="Model name")


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
            raise RuntimeError(f"No API key found for '{settings.api_key_name}'")
    return OpenAI(base_url=settings.base_url, api_key=api_key)


def _strip_tools_for_api(tools: list[dict] | None) -> list[dict]:
    return [{"type": t["type"], "function": t["function"]} for t in (tools or [])]

@traced
def _to_openai_messages(history: list[MessageOut]) -> list[dict]:
    messages = []
    for msg in history:
        meta = msg.meta or {}

        if msg.role in ("system", "user", "assistant"):
            messages.append({"role": msg.role, "content": meta.get("content") or ""})

        elif msg.role == "tool-calling":
            tool_calls = meta.get("tool-calling") or []
            messages.append({
                "role": "assistant",
                "content": meta.get("content"),
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc.get("arguments") or {}),
                        },
                    }
                    for tc in tool_calls
                ],
            })

        elif msg.role == "tool-response":
            tr = meta.get("tool-response") or {}
            result = tr.get("result")
            if isinstance(result, str):
                content = result
            else:
                try:
                    content = json.dumps(result)
                except TypeError:
                    content = str(result)
            messages.append({
                "role": "tool",
                "tool_call_id": tr.get("id"),
                "content": content,
            })
        # autre role inconnu -> ignoré défensivement plutot que de casser l'appel API

    return messages

@traced
def single_turn(query: str, settings: EngineSettings, instructions: str = None, tools: list[dict] = None):
    client = _client(settings)
    messages = [{"role": "system", "content": instructions}] if instructions else []
    messages.append({"role": "user", "content": query})

    response = client.chat.completions.create(
        model=settings.model_name,
        messages=messages,
        tools=_strip_tools_for_api(tools) or None,
    )
    return Response(
        content=response.choices[0].message.content,
        reasoning=response.choices[0].message.reasoning if hasattr(response.choices[0].message, "reasoning") else None,
    )


def chat(settings: EngineSettings, tools: list[dict] = None, history: list[MessageOut] = None):
    client = _client(settings)

    response = client.chat.completions.create(
        model=settings.model_name,
        messages=_to_openai_messages(history or []),
        tools=_strip_tools_for_api(tools) or None,
    )

    choice_message = response.choices[0].message
    reasoning = choice_message.reasoning if hasattr(choice_message, "reasoning") else None

    if choice_message.tool_calls:
        return {
            "role": "tool-calling",
            "meta": {
                "content": choice_message.content,
                "reasoning": reasoning,
                "tool-calling": [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments or "{}"),
                    }
                    for tc in choice_message.tool_calls
                ],
                "model": settings.model_name,
                "engine": name,
            },
        }

    return {
        "role": "assistant",
        "meta": {
            "content": choice_message.content,
            "reasoning": reasoning,
            "model": settings.model_name,
            "engine": name,
        },
    }