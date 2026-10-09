import pytest
import yaml

from lazy_bird import preferences
from lazy_bird.errors import InvalidInputError


@pytest.fixture
def preference_file(tmp_path, monkeypatch):
    path = tmp_path / "preference.yaml"
    monkeypatch.setattr(preferences, "PREFERENCE_FILE", path)
    return path


def test_missing_values_take_their_default(preference_file):
    preference_file.write_text("chunking:\n  max_tokens: 256\n")

    values = preferences.get_preferences()

    assert values["chunking"]["max_tokens"] == 256
    assert values["auto-embedding"]["enable"] is True and values["files"]["scan_every_minutes"] == 10


def test_updates_are_merged_validated_and_saved(preference_file):
    values, restart = preferences.update_preferences({"tasks": {"workers": 2}, "files": {"scan_every_minutes": 0}})

    assert values["tasks"] == {"workers": 2, "resources": {}}
    assert restart == ["tasks.workers"]
    assert yaml.safe_load(preference_file.read_text())["files"] == {"scan_every_minutes": 0}
    assert preferences.scan_every_minutes() == 0


def test_invalid_updates_are_reported_per_key(preference_file):
    with pytest.raises(InvalidInputError) as error:
        preferences.update_preferences({"chunking": {"max_tokens": 1}, "tasks": {"workers": "many", "speed": 3}})

    assert set(error.value.details["fields"]) == {"chunking.max_tokens", "tasks.workers", "tasks.speed"}
    with pytest.raises(InvalidInputError):
        preferences.update_preferences({"colors": {}})


def test_a_hand_broken_file_is_reported_clearly(preference_file):
    preference_file.write_text("chunking:\n  max_tokens: lots\n")

    with pytest.raises(preferences.InvalidPreferencesError) as error:
        preferences.chunking_max_tokens()

    assert "chunking" in error.value.message


def test_the_form_describes_every_section():
    form = preferences.form()

    assert set(form) == {"auto-embedding", "chunking", "files", "tasks", "smart-memory"}
    assert form["chunking"]["kwargs_key"]["max_tokens"]["args"] == {"min": 2}
    assert form["smart-memory"]["kwargs_key"]["fallback"]["default_field"] is True
    assert form["smart-memory"]["kwargs_key"]["fallback"]["default"] == "wait"


def test_smart_memory_is_on_by_default_and_can_be_configured(preference_file):
    assert preferences.smart_memory().model_dump() == {"enable": True, "fallback": "wait", "interrupt_timeout_seconds": 60}

    preferences.update_preferences({"smart-memory": {"enable": False, "fallback": "cpu"}})

    assert preferences.smart_memory().enable is False and preferences.smart_memory().fallback == "cpu"


def test_the_memory_fallback_only_accepts_cpu_or_wait(preference_file):
    with pytest.raises(InvalidInputError) as error:
        preferences.update_preferences({"smart-memory": {"fallback": "gpu", "interrupt_timeout_seconds": 0}})

    assert set(error.value.details["fields"]) == {"smart-memory.fallback", "smart-memory.interrupt_timeout_seconds"}
