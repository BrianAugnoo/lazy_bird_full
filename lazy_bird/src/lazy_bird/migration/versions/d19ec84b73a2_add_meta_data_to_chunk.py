"""add meta_data to Chunk

Revision ID: d19ec84b73a2
Revises: c82ad12db6f1
Create Date: 2026-08-17 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d19ec84b73a2"
down_revision: Union[str, None] = "c82ad12db6f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chunk", schema=None) as batch_op:
        batch_op.add_column(sa.Column("meta_data", sa.JSON(), nullable=True))

    op.execute(sa.text("UPDATE chunk SET meta_data = '{}' WHERE meta_data IS NULL"))

    with op.batch_alter_table("chunk", schema=None) as batch_op:
        batch_op.alter_column(
            "meta_data",
            existing_type=sa.JSON(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("chunk", schema=None) as batch_op:
        batch_op.drop_column("meta_data")
