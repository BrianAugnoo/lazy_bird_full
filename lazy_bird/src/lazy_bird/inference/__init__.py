"""Inference: chat with LLMs through an inference preset.

Engine modules live in ``inference/engines/`` (see ``crud.engine`` for the shared
contract). An inference engine additionally defines ``chat(settings, tools, history)``.
"""

from lazy_bird.crud.engine import EngineFamily
from lazy_bird.errors import UnavailableError
from lazy_bird.models.inference_engine import InferenceEngine, PresetInference
from lazy_bird.schemas.inference_engine import PresetInferenceOut
from lazy_bird.schemas.message import MessageIn
import lazy_bird.crud.conversation as ConversationCRUD
import lazy_bird.crud.message as MessageCRUD

engine_family = EngineFamily(
    kind="inference",
    package="lazy_bird.inference.engines",
    required=("chat",),
    engine_table=InferenceEngine,
    preset_table=PresetInference,
    engine_fk="inference_engine_id",
    preset_out=PresetInferenceOut,
)


def initialize_inference_engines():
    return engine_family.discover()


def single_turn(query: str, instructions: str | None = None, preset_id: int | None = None):
    resolved = engine_family.resolve(preset_id)
    if not hasattr(resolved.module, "single_turn"):
        raise UnavailableError(f"Engine '{resolved.engine.name}' does not support single-turn requests.", code="unsupported_operation")
    return resolved.module.single_turn(query, resolved.settings, instructions)


def agentic_loop(conversation_id: int, tools: list[dict] = None, max_iter: int = 20, preset_id: int | None = None):
    resolved = engine_family.resolve(preset_id)
    module, settings = resolved.module, resolved.settings
    tool_registry = {t["function"]["name"]: t.get("callable") for t in (tools or [])}

    for _ in range(max_iter):
        messages = ConversationCRUD.messages(conversation_id)
        response = module.chat(settings, tools, messages)
        created = MessageCRUD.create(
            MessageIn(conversation_id=conversation_id, **response)
        )

        if response["role"] != "tool-calling":
            return created

        for call in response["meta"].get("tool-calling") or []:
            tool_name = call["name"]
            tool_fn = tool_registry.get(tool_name)

            if tool_fn is None:
                result = f"Error: unknown tool '{tool_name}'. Available tools: {list(tool_registry)}"
            else:
                try:
                    result = tool_fn(**(call.get("arguments") or {}))
                except Exception as exc:
                    result = f"Error while executing tool '{tool_name}': {exc}"

            MessageCRUD.create(
                MessageIn(
                    conversation_id=conversation_id,
                    role="tool-response",
                    meta={
                        "tool-response": {
                            "id": call["id"],
                            "name": tool_name,
                            "result": result,
                        }
                    },
                )
            )

    raise RuntimeError(
        f"agentic_loop exceeded max_iter={max_iter} without reaching a final assistant response"
    )
