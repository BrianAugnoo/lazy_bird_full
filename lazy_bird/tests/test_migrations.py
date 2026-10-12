import json

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


def _upgrade_fresh(tmp_path, name: str, revision: str = "head"):
    db_url = f"sqlite:///{tmp_path / name}"
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


def test_lookup_indexes_preserve_populated_rows_in_both_directions(migrated_database):
    from sqlmodel import Session
    from lazy_bird.models.agent import Agent, AgentHierarchy
    from lazy_bird.models.conversation import Conversation
    from lazy_bird.models.file import File
    from lazy_bird.models.file_processing import FileProcessing
    from lazy_bird.models.session import Session as SessionRow
    from lazy_bird.models.task import Task

    with Session(migrated_database.engine) as session:
        session.add_all([SessionRow(id=1, title="s"), File(id=1, name="f", path="/f.md", extension=".md", size=1), Task(id=1, kind="k", title="queued")])
        session.flush()
        session.add_all([Agent(id=1, name="parent", session_id=1), Agent(id=2, name="child", session_id=1)])
        session.flush()
        session.add_all([AgentHierarchy(parent_id=1, child_id=2), Conversation(id=1, agent_id=1, title="chat"), FileProcessing(file_id=1, processor="chunking", task_id=1)])
        session.commit()
    tables = ("agent", "agenthierarchy", "conversation", "fileprocessing", "task")

    def snapshot():
        with migrated_database.engine.connect() as connection:
            return {table: connection.execute(text(f"SELECT * FROM {table}")).all() for table in tables}

    before = snapshot()
    config = alembic_config(migrated_database.url)
    command.downgrade(config, "e5b7c9d1f3a5")
    assert snapshot() == before
    command.upgrade(config, "head")
    assert snapshot() == before


def test_migrations_downgrade_to_base_and_upgrade_again(migrated_database):
    config = alembic_config(migrated_database.url)
    head_tables = _tables(migrated_database.engine)

    command.downgrade(config, "base")
    assert _tables(migrated_database.engine) == {"alembic_version"}

    command.upgrade(config, "head")
    assert _tables(migrated_database.engine) == head_tables


def test_vector_migration_removes_relational_chunks(tmp_path):
    db_url, config = _upgrade_fresh(tmp_path, "chunks.db", "c82ad12db6f1")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO file (name, path, extension, size, status) VALUES ('notes', '/tmp/notes.md', '.md', 10, 'pending')"))
        connection.execute(text("INSERT INTO chunk (file_id, content, start_line, end_line) VALUES (1, 'content', 1, 1)"))
    engine.dispose()

    command.upgrade(config, "9d3f1a7c2b44")

    engine = create_engine(db_url)
    assert "chunk" not in _tables(engine)
    engine.dispose()


def test_migrations_upgrade_a_populated_file_table(tmp_path):
    db_url, config = _upgrade_fresh(tmp_path, "populated.db", "364a345aff9f")
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


def test_engine_preset_migration_keeps_engine_configuration(tmp_path):
    db_url, config = _upgrade_fresh(tmp_path, "presets.db", "d16202b6ed97")
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


def test_chunk_migration_requeues_embedded_files(tmp_path):
    db_url, config = _upgrade_fresh(tmp_path, "chunk-table.db", "39c55806b344")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        for name, status in [("done", "done"), ("broken", "format-error"), ("failed", "embedding-error")]:
            connection.execute(text(f"INSERT INTO file (name, path, extension, size, status) VALUES ('{name}', '/tmp/{name}', '.md', 1, '{status}')"))
    engine.dispose()

    command.upgrade(config, "eee74044513a")

    engine = create_engine(db_url)
    with engine.connect() as connection:
        statuses = dict(connection.execute(text("SELECT name, status FROM file")).all())
    tables = _tables(engine)
    engine.dispose()
    assert statuses == {"done": "pending", "broken": "format-error", "failed": "pending"}
    assert "chunk" in tables and not {"embedded", "embeddedvectordatabase", "vectordatabase"} & tables


def test_priority_migration_mirrors_priorities_around_the_new_default(tmp_path):
    db_url, config = _upgrade_fresh(tmp_path, "priorities.db", "c3e5a7b9d1f2")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        for priority in (0, 10, -10):
            connection.execute(
                text("INSERT INTO task (kind, title, params, status, priority, position, resources, state, attempts, max_attempts, created_at, updated_at) "
                     "VALUES ('k', 't', '{}', 'queued', :priority, 1, '{}', '{}', 0, 1, '2026-01-01', '2026-01-01')"),
                {"priority": priority},
            )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(db_url)
    with engine.connect() as connection:
        upgraded = [row[0] for row in connection.execute(text("SELECT priority FROM task ORDER BY id"))]
    engine.dispose()
    command.downgrade(config, "c3e5a7b9d1f2")
    engine = create_engine(db_url)
    with engine.connect() as connection:
        restored = [row[0] for row in connection.execute(text("SELECT priority FROM task ORDER BY id"))]
    engine.dispose()

    assert upgraded == [5, -5, 15]  # the default stays average, the old "high" runs sooner, the old "low" later
    assert restored == [0, 10, -10]


def test_engine_migration_removes_the_unloading_setting_from_saved_presets(tmp_path):
    db_url, config = _upgrade_fresh(tmp_path, "unloading.db", "d4a6b8c0e2f4")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO embeddingengine (name, file_path, formats, kwargs_key) VALUES ('st', 'st.py', '[]', '{}')"))
        for name, kwargs in (("old", '{"model_id": 1, "unloading": false, "batch_size": 8}'), ("new", '{"model_id": 2}')):
            connection.execute(
                text('INSERT INTO presetembedding (name, embedding_engine_id, kwargs, "default") VALUES (:name, 1, :kwargs, 0)'),
                {"name": name, "kwargs": kwargs},
            )
    engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(db_url)
    with engine.connect() as connection:
        kwargs = {name: json.loads(value) for name, value in connection.execute(text("SELECT name, kwargs FROM presetembedding"))}
        local = connection.execute(text("SELECT local FROM embeddingengine")).scalar_one()
    engine.dispose()
    assert kwargs == {"old": {"model_id": 1, "batch_size": 8}, "new": {"model_id": 2}}
    assert local == 0  # engines learn whether they are local when they are discovered at startup
