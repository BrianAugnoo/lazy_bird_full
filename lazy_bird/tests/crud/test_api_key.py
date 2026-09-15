import pytest

import lazy_bird.crud.api_key as api_key_crud
from lazy_bird.crud.error import UniqueFieldError
from lazy_bird.schemas.api_key import APIKeyIn


def test_create_persists_and_returns_api_key(crud_database):
    created = api_key_crud.create(APIKeyIn(name="OpenAI", key="secret"))

    assert created.model_dump() == {"name": "OpenAI"}
    assert api_key_crud.find("OpenAI") == created


def test_create_rejects_duplicate_name(crud_database):
    api_key_crud.create(APIKeyIn(name="OpenAI", key="first"))

    with pytest.raises(UniqueFieldError) as exc_info:
        api_key_crud.create(APIKeyIn(name="OpenAI", key="second"))

    assert exc_info.value.field_name == "name"
    assert exc_info.value.field_value == "OpenAI"
    assert api_key_crud.find("OpenAI").name == "OpenAI"


def test_find_returns_none_for_unknown_name(crud_database):
    assert api_key_crud.find("missing") is None


def test_get_all_returns_all_records(crud_database):
    api_key_crud.create(APIKeyIn(name="OpenAI", key="one"))
    api_key_crud.create(APIKeyIn(name="Anthropic", key="two"))

    records = api_key_crud.get_all()

    assert {record.name for record in records} == {"OpenAI", "Anthropic"}
