from typing import Any

from fastapi import APIRouter

import lazy_bird.crud.preferences as preferences_crud
from lazy_bird.preferences import apply_preferences

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("/")
def get_preferences() -> dict[str, Any]:
    return preferences_crud.get()


@router.put("/")
def update_preferences(values: dict[str, Any]) -> dict[str, Any]:
    changed = preferences_crud.update(values)
    if changed:
        apply_preferences()
    return preferences_crud.get()