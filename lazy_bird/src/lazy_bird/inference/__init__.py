import importlib
import pkgutil
from pathlib import Path

from lazy_bird.crud import inference_engine as engine_crud
from lazy_bird.crud import selected_inference_engine

from lazy_bird.schemas.conversation import ConversationOut
from lazy_bird.schemas.message import MessageIn
import lazy_bird.crud.conversation as ConversationCRUD
import lazy_bird.crud.message as MessageCRUD


def initialize_inference_engines():
    package = importlib.import_module("lazy_bird.inference.engines")
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        engine_crud.upsert(module.name, info.name)


def _inference_context():
    selected = selected_inference_engine.get()
    if selected is None:
        raise RuntimeError("No inference engine is selected")
    module = importlib.import_module(f"lazy_bird.inference.engines.{Path(selected.file_path).stem}")
    settings = module.EngineSettings.model_validate(selected.kwargs)
    return module, settings


def single_turn(query: str, instructions: str = None):
    module, settings = _inference_context()
    return module.single_turn(query, settings, instructions)


def agentic_loop(conversation_id: int, tools: list[dict] = None, max_iter: int = 20):
    module, settings = _inference_context()
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