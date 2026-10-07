from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlmodel import SQLModel

import lazy_bird.models  # noqa: F401  (registers every table)
from tests.conftest import alembic_config


def _tables(engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def _upgrade_fresh(tmp_path, monkeypatch, name: str, revision: str = "head"):
    import lazy_bird.database as database_module

    db_url = f"sqlite:///{tmp_path / name}"
    monkeypatch.setattr(database_module, "db_url", db_url)
    config = alembic_config(db_url)
    command.upgrade(config, revision)
    return db_url, config


def test_migrations_reach_the_script_head(migrated_database):
    config = alembic_config(migrated_database.url)
    expected = ScriptDirectory.from_config(config).get_current_head()

    with migrated_database.engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == expected


def test_models_match_the_migrated_schema(migrated_database):
    with migrated_database.engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "compare_server_default": True, "render_as_batch": True}
        )
        assert compare_metadata(context, SQLModel.metadata) == []


def test_migrations_downgrade_to_base_and_upgrade_again(migrated_database):
    config = alembic_config(migrated_database.url)
    head_tables = _tables(migrated_database.engine)

    command.downgrade(config, "base")
    assert _tables(migrated_database.engine) == {"alembic_version"}

    command.upgrade(config, "head")
    assert _tables(migrated_database.engine) == head_tables


def test_vector_migration_removes_relational_chunks(tmp_path, monkeypatch):
    db_url, config = _upgrade_fresh(tmp_path, monkeypatch, "chunks.db", "c82ad12db6f1")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO file (name, path, extension, size, status) VALUES ('notes', '/tmp/notes.md', '.md', 10, 'pending')"))
        connection.execute(text("INSERT INTO chunk (file_id, content, start_line, end_line) VALUES (1, 'content', 1, 1)"))
    engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(db_url)
    assert "chunk" not in _tables(engine)
    engine.dispose()


def test_migrations_upgrade_a_populated_file_table(tmp_path, monkeypatch):
    db_url, config = _upgrade_fresh(tmp_path, monkeypatch, "populated.db", "364a345aff9f")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO file (name, path, format) VALUES ('report', '/tmp/report.pdf', 'pdf')"))
    engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(db_url)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT name, extension, size FROM file")).one()
    engine.dispose()
    assert tuple(row) == ("report", ".pdf", 0)


def test_engine_preset_migration_keeps_engine_configuration(tmp_path, monkeypatch):
    db_url, config = _upgrade_fresh(tmp_path, monkeypatch, "presets.db", "d16202b6ed97")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO llmmodel (id, name, hf_path, local_path, dimension, formats, selected_format) VALUES (7, 'm', 'org/m', '/tmp/m', 8, '[\"safetensors\"]', 'safetensors')"))
        connection.execute(text("INSERT INTO embeddingengine (id, name, file_path, formats, kwargs, kwargs_keys) VALUES (1, 'sentence-transformers', 'st', '[]', '{\"device\": \"cpu\", \"model_path\": \"/x\"}', '{}')"))
        connection.execute(text("INSERT INTO embeddingengine (id, name, file_path, formats, kwargs, kwargs_keys) VALUES (2, 'unused', 'unused', '[]', '{}', '{}')"))
        connection.execute(text("INSERT INTO inferenceengine (id, name, file_path, kwargs, kwargs_keys) VALUES (1, 'openai-client', 'openai', '{\"base_url\": \"http://x\", \"model_name\": \"m\"}', '{}')"))
        connection.execute(text("INSERT INTO selectedembeddingengine (id, embedding_engine_id) VALUES (1, 1)"))
        connection.execute(text("INSERT INTO selectedmodelembeding (id, llm_model_id, batch) VALUES (1, 7, 16)"))
    engine.dispose()

    command.upgrade(config, "39c55806b344")

    engine = create_engine(db_url)
    with engine.connect() as connection:
        embedding = connection.execute(text('SELECT name, embedding_engine_id, kwargs, "default" FROM presetembedding')).all()
        inference = connection.execute(text('SELECT name, inference_engine_id, kwargs, "default" FROM presetinference')).all()
    engine.dispose()
    assert [tuple(row) for row in embedding] == [
        ("sentence-transformers", 1, '{"device": "cpu", "model_id": 7, "batch_size": 16}', 1)
    ]
    assert [tuple(row) for row in inference] == [("openai-client", 1, '{"base_url": "http://x", "model_name": "m"}', 1)]

    command.downgrade(config, "d16202b6ed97")

    engine = create_engine(db_url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT llm_model_id, batch FROM selectedmodelembeding")).one() == (7, 16)
        assert connection.execute(text("SELECT embedding_engine_id FROM selectedembeddingengine")).scalar() == 1
        assert connection.execute(text("SELECT kwargs FROM embeddingengine WHERE id = 1")).scalar() == '{"device": "cpu"}'
    engine.dispose()
