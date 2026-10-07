"""Agent and session presets (JSON files of extensions)."""

from fastapi import APIRouter, Response

from lazy_bird.agents import agent_preset, session_preset
from lazy_bird.agents.agent_preset import AgentPresetData
from lazy_bird.agents.presets import Preset, PresetRegistry
from lazy_bird.agents.session_preset import SessionPresetData
from lazy_bird.schemas.extensions import PresetOut

router = APIRouter()


def _out(preset: Preset) -> PresetOut:
    return PresetOut(
        id=preset.id,
        extension=preset.extension,
        name=preset.name,
        editable=preset.editable,
        valid=preset.valid,
        errors=preset.errors,
        data=preset.data.model_dump() if preset.data else None,
    )


def _routes(prefix: str, tag: str, registry: PresetRegistry, schema) -> None:
    @router.get(f"{prefix}/", response_model=list[PresetOut], tags=[tag])
    def list_presets():
        return [_out(preset) for preset in registry.presets()]

    @router.post(f"{prefix}/", response_model=PresetOut, status_code=201, tags=[tag])
    def create_preset(payload: schema):
        return _out(registry.create(payload))

    @router.get(f"{prefix}/{{extension}}/{{name}}", response_model=PresetOut, tags=[tag])
    def get_preset(extension: str, name: str):
        return _out(registry.get(f"{extension}/{name}"))

    @router.put(f"{prefix}/{{extension}}/{{name}}", response_model=PresetOut, tags=[tag])
    def update_preset(extension: str, name: str, payload: schema):
        return _out(registry.update(f"{extension}/{name}", payload))

    @router.delete(f"{prefix}/{{extension}}/{{name}}", status_code=204, tags=[tag])
    def delete_preset(extension: str, name: str):
        registry.delete(f"{extension}/{name}")
        return Response(status_code=204)


_routes("/agent-presets", "agent-presets", agent_preset.registry, AgentPresetData)
_routes("/session-presets", "session-presets", session_preset.registry, SessionPresetData)
