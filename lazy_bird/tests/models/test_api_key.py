from lazy_bird.models.api_key import APIKey


def test_api_key_table_shape():
    table = APIKey.__table__

    assert table.name == "apikey"
    assert list(table.columns.keys()) == ["name", "key"]
    assert table.c.name.primary_key is True
    assert table.c.key.nullable is False


def test_api_key_instance_keeps_credentials():
    record = APIKey(name="OpenAI", key="secret")

    assert record.name == "OpenAI"
    assert record.key == "secret"
