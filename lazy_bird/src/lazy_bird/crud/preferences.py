from typing import Any

from lazy_bird.preferences import get_preferences, update_preferences


def get() -> dict[str, Any]:
    return get_preferences()


def update(values: dict[str, Any]) -> bool:
    return update_preferences(values)