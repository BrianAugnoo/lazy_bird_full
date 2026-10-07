"""Router factory shared by every engine family (embedding, inference...).

Do not add ``from __future__ import annotations`` here: FastAPI must see the
payload classes passed to the factory as real annotations.
"""

from fastapi import APIRouter, Response
from pydantic import BaseModel

from lazy_bird.crud.engine import EngineFamily
from lazy_bird.errors import NotFoundError
from lazy_bird.schemas.engine import EngineOut


def engine_router(
    family: EngineFamily,
    *,
    engines_prefix: str,
    presets_prefix: str,
    tag: str,
    preset_in: type[BaseModel],
    preset_update: type[BaseModel],
    preset_out: type[BaseModel],
) -> APIRouter:
    router = APIRouter(tags=[tag])

    @router.get(f"{engines_prefix}/", response_model=list[EngineOut])
    def list_engines():
        return family.engines()

    @router.get(f"{engines_prefix}/{{engine_id}}", response_model=EngineOut)
    def get_engine(engine_id: int):
        return family.engine(engine_id)

    @router.get(f"{presets_prefix}/", response_model=list[preset_out])
    def list_presets():
        return family.presets()

    @router.post(f"{presets_prefix}/", response_model=preset_out, status_code=201)
    def create_preset(payload: preset_in):
        return family.create_preset(
            payload.name, getattr(payload, family.engine_fk), payload.kwargs, payload.default
        )

    @router.get(f"{presets_prefix}/default", response_model=preset_out)
    def get_default_preset():
        preset = family.default_preset()
        if preset is None:
            raise NotFoundError(f"{family.kind.capitalize()} preset", "default", code="no_default_preset")
        return preset

    @router.get(f"{presets_prefix}/{{preset_id}}", response_model=preset_out)
    def get_preset(preset_id: int):
        return family.preset(preset_id)

    @router.patch(f"{presets_prefix}/{{preset_id}}", response_model=preset_out)
    def update_preset(preset_id: int, payload: preset_update):
        return family.update_preset(preset_id, payload.model_dump(exclude_unset=True))

    @router.delete(f"{presets_prefix}/{{preset_id}}", status_code=204)
    def delete_preset(preset_id: int):
        family.delete_preset(preset_id)
        return Response(status_code=204)

    return router
