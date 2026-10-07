from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from lazy_bird import preferences

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesUpdateOut(BaseModel):
    preferences: dict[str, dict[str, Any]]
    restart_required: list[str]


@router.get("/")
def get_preferences() -> dict[str, dict[str, Any]]:
    """Every preference section with its values (defaults filled in)."""
    return preferences.get_preferences()


@router.get("/form")
def get_preferences_form() -> dict[str, dict[str, Any]]:
    """The settings form of each section (``title`` and ``kwargs_key``)."""
    return preferences.form()


@router.patch("/", response_model=PreferencesUpdateOut)
def update_preferences(changes: dict[str, dict[str, Any]]):
    """Change some preferences (``{section: {key: value}}``) and apply them."""
    values, restart = preferences.update_preferences(changes)
    preferences.apply_preferences()
    return PreferencesUpdateOut(preferences=values, restart_required=restart)
