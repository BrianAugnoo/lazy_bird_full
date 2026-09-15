import pytest
from pydantic import ValidationError

from lazy_bird.models.api_key import APIKey
from lazy_bird.schemas.api_key import APIKeyIn, APIKeyOut


def test_api_key_input_validates_credentials():
    schema = APIKeyIn(name="OpenAI", key="secret")

    assert schema.model_dump() == {"name": "OpenAI", "key": "secret"}


def test_api_key_output_reads_model_attributes():
    schema = APIKeyOut.model_validate(APIKey(name="OpenAI", key="secret"))

    assert schema.name == "OpenAI"
    assert "key" not in schema.model_dump()


def test_api_key_input_requires_key():
    with pytest.raises(ValidationError):
        APIKeyIn(name="OpenAI")
