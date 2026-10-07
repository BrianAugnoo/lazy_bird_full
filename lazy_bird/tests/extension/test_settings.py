from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from lazy_bird.errors import InvalidSettingsError
from lazy_bird.extension import ExtensionContractError
from lazy_bird.extension.settings import SettingsContract, settings_contract


class DemoSettings(BaseModel):
    url: str = Field(title="Server URL", description="Where to connect")
    retries: int = Field(default=3, ge=0, le=10)
    ratio: float | None = None
    enabled: bool = True
    mode: Literal["fast", "safe"] = "safe"
    password: SecretStr
    tags: list[str] = Field(default_factory=list)
    extra: dict = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid")


def test_kwargs_key_derives_a_default_widget_for_every_attribute():
    key = SettingsContract(DemoSettings).kwargs_key()

    assert {name: descriptor["content"] for name, descriptor in key.items()} == {
        "url": "default.basic.text",
        "retries": "default.basic.integer",
        "ratio": "default.basic.number",
        "enabled": "default.basic.checkbox",
        "mode": "default.basic.select",
        "password": "default.basic.password",
        "tags": "default.basic.list",
        "extra": "default.basic.json",
    }
    assert key["url"] == {
        "default_field": True,
        "content": "default.basic.text",
        "args": {},
        "type": "string",
        "required": True,
        "nullable": False,
        "default": None,
        "title": "Server URL",
        "description": "Where to connect",
    }
    assert key["retries"]["args"] == {"min": 0, "max": 10}
    assert key["retries"]["default"] == 3
    assert key["ratio"]["nullable"] is True and key["ratio"]["required"] is False
    assert key["mode"]["args"] == {"options": ["fast", "safe"]}
    assert key["tags"]["default"] == []


def test_fields_override_the_widget_but_keep_the_metadata():
    contract = SettingsContract(
        DemoSettings,
        {
            "password": {"default_field": True, "content": "default.basic.password", "args": {"confirm": False}},
            "url": {"default_field": False, "content": "<input data-field-input>"},
        },
    )

    key = contract.kwargs_key()

    assert key["password"]["args"] == {"confirm": False}
    assert key["password"]["required"] is True
    assert key["url"]["default_field"] is False
    assert key["url"]["content"] == "<input data-field-input>"
    assert key["url"]["args"] == {}
    assert key["url"]["title"] == "Server URL"


@pytest.mark.parametrize(
    "fields",
    [
        {"unknown": {"default_field": True, "content": "default.basic.text"}},
        {"url": {"default_field": True, "content": "<b>not a function path</b>"}},
        {"url": {"default_field": False, "content": "<input>", "args": {"x": 1}}},
        {"url": {"content": "default.basic.text"}},
        ["not", "a", "dict"],
    ],
)
def test_malformed_fields_are_rejected(fields):
    with pytest.raises(ExtensionContractError):
        SettingsContract(DemoSettings, fields)


def test_validate_returns_parsed_settings():
    settings = SettingsContract(DemoSettings).validate({"url": "http://x", "password": "secret", "retries": "5"})

    assert settings.retries == 5
    assert settings.password.get_secret_value() == "secret"


def test_validate_reports_one_message_per_invalid_attribute():
    with pytest.raises(InvalidSettingsError) as error:
        SettingsContract(DemoSettings).validate({"retries": 99, "mode": "slow", "nope": 1})

    assert set(error.value.fields) == {"url", "password", "retries", "mode", "nope"}
    assert error.value.fields["nope"].startswith("Extra inputs") or error.value.fields["nope"] == "Unknown setting"
    assert error.value.details == {"fields": error.value.fields}


def test_unknown_keys_are_rejected_even_when_the_model_allows_extras():
    class Permissive(BaseModel):
        value: int = 1

    assert SettingsContract(Permissive).errors({"other": 2}) == {"other": "Unknown setting"}


def test_dump_keeps_only_provided_values_and_reveals_secrets():
    contract = SettingsContract(DemoSettings)

    assert contract.normalize({"url": "http://x", "password": "secret", "retries": "4"}) == {
        "url": "http://x",
        "password": "secret",
        "retries": 4,
    }


def test_settings_contract_reads_module_declarations():
    module = type("Module", (), {"EngineSettings": DemoSettings, "fields": {}})

    assert settings_contract(module, "EngineSettings").model is DemoSettings
    assert settings_contract(object(), "EngineSettings") is None
    with pytest.raises(ExtensionContractError):
        settings_contract(object(), "EngineSettings", required=True)
    with pytest.raises(ExtensionContractError):
        settings_contract(type("Broken", (), {"fields": {"a": {}}}), "ToolSettings")
