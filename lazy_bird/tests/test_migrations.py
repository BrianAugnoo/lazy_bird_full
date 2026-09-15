from alembic import command
from sqlalchemy import create_engine, inspect, text
import pytest

from tests.conftest import alembic_config


def test_migrations_build_current_schema(migrated_database):
    inspector = inspect(migrated_database.engine)

    assert set(inspector.get_table_names()) == {
        "alembic_version",
        "apikey",
        "embedded",
        "embeddedvectordatabase",
        "embeddingengine",
        "file",
        "llmmodel",
        "selectedmodelembeding",
        "selectedembeddingengine",
        "vectordatabase",
    }
    assert {column["name"] for column in inspector.get_columns("apikey")} == {"name", "key"}
    assert {column["name"] for column in inspector.get_columns("file")} == {
        "id",
        "name",
        "path",
        "extension",
        "size",
        "status",
    }
    assert {column["name"] for column in inspector.get_columns("llmmodel")} == {
        "id",
        "name",
        "hf_path",
        "local_path",
        "dimension",
        "max_context_length",
        "selected_context",
        "formats",
        "selected_format",
    }
    assert {column["name"] for column in inspector.get_columns("selectedmodelembeding")} == {
        "id",
        "llm_model_id",
        "batch",
    }
    assert {column["name"] for column in inspector.get_columns("embeddingengine")} == {
        "id",
        "name",
        "file_path",
        "formats",
        "kwargs",
        "kwargs_keys",
    }


def test_migrations_stamp_database_at_head(migrated_database):
    with migrated_database.engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == "b5e8f1a2c3d4"


def test_migrations_can_downgrade_and_upgrade_again(migrated_database):
    config = alembic_config(migrated_database.url)

    command.downgrade(config, "base")
    assert inspect(migrated_database.engine).get_table_names() == ["alembic_version"]

    command.upgrade(config, "head")
    assert set(inspect(migrated_database.engine).get_table_names()) == {
        "alembic_version",
        "apikey",
        "embedded",
        "embeddedvectordatabase",
        "embeddingengine",
        "file",
        "llmmodel",
        "selectedmodelembeding",
        "selectedembeddingengine",
        "vectordatabase",
    }


def test_vector_migration_removes_relational_chunks(tmp_path, monkeypatch):
    import lazy_bird.database as database_module

    db_path = tmp_path / "chunks.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setattr(database_module, "db_url", db_url)
    config = alembic_config(db_url)
    command.upgrade(config, "c82ad12db6f1")

    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO file (name, path, extension, size, status) "
                "VALUES ('notes', '/tmp/notes.md', '.md', 10, 'pending')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chunk (file_id, content, start_line, end_line) "
                "VALUES (1, 'content', 1, 1)"
            )
        )
    engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(db_url)
    tables = inspect(engine).get_table_names()
    engine.dispose()
    assert "chunk" not in tables


@pytest.mark.xfail(
    reason="The non-null file columns are added without defaults for existing rows",
    strict=True,
)
def test_migrations_upgrade_a_populated_file_table(tmp_path, monkeypatch):
    import lazy_bird.database as database_module

    db_path = tmp_path / "populated.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setattr(database_module, "db_url", db_url)
    config = alembic_config(db_url)
    command.upgrade(config, "364a345aff9f")

    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO file (name, path, format) "
                "VALUES ('report', '/tmp/report.pdf', 'pdf')"
            )
        )
    engine.dispose()

    command.upgrade(config, "head")
