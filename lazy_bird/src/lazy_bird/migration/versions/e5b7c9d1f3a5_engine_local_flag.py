"""engines know whether they run a model on this machine; presets lose the unloading setting

``local`` is set from the engine module each time engines are discovered, so rows that
exist before the upgrade only need a value for the migration itself. The sentence-transformers
engines no longer have an ``unloading`` setting (their models are now released by
``lazy_bird.residency``): the key is removed from saved presets, which would otherwise be
rejected as invalid.

Revision ID: e5b7c9d1f3a5
Revises: d4a6b8c0e2f4
Create Date: 2026-10-09 06:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b7c9d1f3a5"
down_revision: Union[str, None] = "d4a6b8c0e2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENGINE_TABLES = ("embeddingengine", "crossencoderengine", "inferenceengine")
PRESET_TABLES = ("presetembedding", "presetcrossencoder")


def upgrade() -> None:
    for table in ENGINE_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("local", sa.Boolean(), nullable=False, server_default=sa.false()))
        with op.batch_alter_table(table) as batch:
            batch.alter_column("local", server_default=None)
    connection = op.get_bind()
    for name in PRESET_TABLES:
        presets = sa.table(name, sa.column("id", sa.Integer()), sa.column("kwargs", sa.JSON()))
        for row in connection.execute(sa.select(presets.c.id, presets.c.kwargs)).all():
            if row.kwargs and "unloading" in row.kwargs:
                kwargs = {key: value for key, value in row.kwargs.items() if key != "unloading"}
                connection.execute(presets.update().where(presets.c.id == row.id).values(kwargs=kwargs))


def downgrade() -> None:
    for table in ENGINE_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("local")
