"""replace selected engines and selected embedding model with engine presets

- create ``presetembedding`` and ``presetinference`` (several presets per engine,
  at most one ``default`` per table, enforced by a partial unique index);
- move ``kwargs`` from the engine tables to the presets;
- rename ``kwargs_keys`` to ``kwargs_key`` and add ``formats`` to inference engines;
- drop ``selectedembeddingengine``, ``selectedinferenceengine`` and
  ``selectedmodelembeding``: the selected model becomes the ``model_id`` setting
  (and ``batch`` the ``batch_size`` setting) of the default embedding preset.

Revision ID: 39c55806b344
Revises: d16202b6ed97
Create Date: 2026-10-07 06:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "39c55806b344"
down_revision: Union[str, None] = "d16202b6ed97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OBSOLETE_EMBEDDING_KEYS = ("model_path",)


def _preset_table(name: str, engine_fk: str) -> sa.Table:
    return sa.table(
        name,
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column(engine_fk, sa.Integer),
        sa.column("kwargs", sa.JSON),
        sa.column("default", sa.Boolean),
    )


def _engine_table(name: str, kwargs_column: str = "kwargs") -> sa.Table:
    return sa.table(name, sa.column("id", sa.Integer), sa.column("name", sa.String), sa.column(kwargs_column, sa.JSON))


def _create_preset_table(name: str, engine_fk: str, engine_table: str) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(engine_fk, sa.Integer(), nullable=False),
        sa.Column("kwargs", sa.JSON(), nullable=False),
        sa.Column("default", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint([engine_fk], [f"{engine_table}.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        f"uq_{name}_single_default",
        name,
        ["default"],
        unique=True,
        sqlite_where=sa.text('"default" = 1'),
        postgresql_where=sa.text('"default"'),
    )


def _migrate_presets(connection, engine_table: str, preset_table: str, engine_fk: str, selected_engine_id, extra_kwargs: dict) -> None:
    """Create one preset per configured or selected engine; the selected engine's preset is the default."""
    presets = []
    engines = _engine_table(engine_table)
    for engine in connection.execute(sa.select(engines.c.id, engines.c.name, engines.c.kwargs)).all():
        kwargs = dict(engine.kwargs or {})
        selected = engine.id == selected_engine_id
        if selected:
            kwargs.update(extra_kwargs)
        if engine_table == "embeddingengine":
            for key in OBSOLETE_EMBEDDING_KEYS:
                kwargs.pop(key, None)
        if kwargs or selected:
            presets.append({"name": engine.name, engine_fk: engine.id, "kwargs": kwargs, "default": selected})
    if presets and not any(preset["default"] for preset in presets):
        presets[0]["default"] = True
    if presets:
        op.bulk_insert(_preset_table(preset_table, engine_fk), presets)


def upgrade() -> None:
    connection = op.get_bind()
    _create_preset_table("presetembedding", "embedding_engine_id", "embeddingengine")
    _create_preset_table("presetinference", "inference_engine_id", "inferenceengine")

    selected_embedding = connection.execute(sa.text("SELECT embedding_engine_id FROM selectedembeddingengine")).scalar()
    selected_inference = connection.execute(sa.text("SELECT inference_engine_id FROM selectedinferenceengine")).scalar()
    selected_model = connection.execute(sa.text("SELECT llm_model_id, batch FROM selectedmodelembeding")).first()
    model_kwargs = {"model_id": selected_model.llm_model_id, "batch_size": selected_model.batch} if selected_model else {}

    _migrate_presets(connection, "embeddingengine", "presetembedding", "embedding_engine_id", selected_embedding, model_kwargs)
    _migrate_presets(connection, "inferenceengine", "presetinference", "inference_engine_id", selected_inference, {})

    op.drop_table("selectedembeddingengine")
    op.drop_table("selectedinferenceengine")
    op.drop_table("selectedmodelembeding")

    with op.batch_alter_table("embeddingengine") as batch_op:
        batch_op.drop_column("kwargs")
        batch_op.alter_column("kwargs_keys", new_column_name="kwargs_key", existing_type=sa.JSON(), existing_nullable=False)

    with op.batch_alter_table("inferenceengine") as batch_op:
        batch_op.drop_column("kwargs")
        batch_op.alter_column("kwargs_keys", new_column_name="kwargs_key", existing_type=sa.JSON(), existing_nullable=False)
        batch_op.add_column(sa.Column("formats", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    with op.batch_alter_table("inferenceengine") as batch_op:
        batch_op.alter_column("formats", existing_type=sa.JSON(), existing_nullable=False, server_default=None)


def _restore_engine_kwargs(connection, engine_table: str, preset_table: str, engine_fk: str, moved_keys: tuple[str, ...] = ()) -> dict:
    """Copy each engine's default (or oldest) preset back into ``kwargs``; return the default preset.

    ``moved_keys`` are settings that the old schema stored elsewhere (the selected model).
    """
    presets = _preset_table(preset_table, engine_fk)
    rows = connection.execute(sa.select(presets).order_by(presets.c.default.desc(), presets.c.id)).all()
    restored = set()
    engines = _engine_table(engine_table)
    for row in rows:
        engine_id = getattr(row, engine_fk)
        if engine_id in restored:
            continue
        restored.add(engine_id)
        kwargs = {key: value for key, value in (row.kwargs or {}).items() if key not in moved_keys}
        connection.execute(sa.update(engines).where(engines.c.id == engine_id).values(kwargs=kwargs))
    default = next((row for row in rows if row.default), None)
    return {"engine_id": getattr(default, engine_fk), "kwargs": dict(default.kwargs or {})} if default else {}


def downgrade() -> None:
    connection = op.get_bind()
    with op.batch_alter_table("inferenceengine") as batch_op:
        batch_op.drop_column("formats")
        batch_op.alter_column("kwargs_key", new_column_name="kwargs_keys", existing_type=sa.JSON(), existing_nullable=False)
        batch_op.add_column(sa.Column("kwargs", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    with op.batch_alter_table("embeddingengine") as batch_op:
        batch_op.alter_column("kwargs_key", new_column_name="kwargs_keys", existing_type=sa.JSON(), existing_nullable=False)
        batch_op.add_column(sa.Column("kwargs", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    for table in ("inferenceengine", "embeddingengine"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("kwargs", existing_type=sa.JSON(), existing_nullable=False, server_default=None)

    op.create_table(
        "selectedembeddingengine",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("embedding_engine_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="selected_embedding_engine_id_is_one"),
        sa.ForeignKeyConstraint(["embedding_engine_id"], ["embeddingengine.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "selectedinferenceengine",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inference_engine_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="selected_inference_engine_id_is_one"),
        sa.ForeignKeyConstraint(["inference_engine_id"], ["inferenceengine.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "selectedmodelembeding",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("llm_model_id", sa.Integer(), nullable=False),
        sa.Column("batch", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="selected_model_embeding_id_is_one"),
        sa.ForeignKeyConstraint(["llm_model_id"], ["llmmodel.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    embedding = _restore_engine_kwargs(connection, "embeddingengine", "presetembedding", "embedding_engine_id", ("model_id", "batch_size"))
    inference = _restore_engine_kwargs(connection, "inferenceengine", "presetinference", "inference_engine_id")
    if embedding:
        connection.execute(sa.text("INSERT INTO selectedembeddingengine (id, embedding_engine_id) VALUES (1, :id)"), {"id": embedding["engine_id"]})
        model_id = embedding["kwargs"].get("model_id")
        if isinstance(model_id, int):
            connection.execute(
                sa.text("INSERT INTO selectedmodelembeding (id, llm_model_id, batch) VALUES (1, :model, :batch)"),
                {"model": model_id, "batch": int(embedding["kwargs"].get("batch_size") or 1)},
            )
    if inference:
        connection.execute(sa.text("INSERT INTO selectedinferenceengine (id, inference_engine_id) VALUES (1, :id)"), {"id": inference["engine_id"]})

    op.drop_index("uq_presetinference_single_default", table_name="presetinference")
    op.drop_table("presetinference")
    op.drop_index("uq_presetembedding_single_default", table_name="presetembedding")
    op.drop_table("presetembedding")
