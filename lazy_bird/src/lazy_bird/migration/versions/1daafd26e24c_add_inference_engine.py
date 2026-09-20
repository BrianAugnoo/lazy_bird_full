"""add inference engine

Revision ID: 1daafd26e24c
Revises: b5e8f1a2c3d4
Create Date: 2026-09-18 11:48:33.963630

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '1daafd26e24c'
down_revision: Union[str, None] = 'b5e8f1a2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inferenceengine",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("formats", sa.JSON(), nullable=False),
        sa.Column("kwargs", sa.JSON(), nullable=False),
        sa.Column("kwargs_keys", sa.JSON(), nullable=False),
    )
    op.create_table(
        "selectedinferenceengine",
        sa.Column("id", sa.Integer(), primary_key=True, server_default="1"),
        sa.Column("inference_engine_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["inference_engine_id"], ["inferenceengine.id"]),
        sa.CheckConstraint("id = 1", name="selected_inference_engine_id_is_one"),
    )


def downgrade() -> None:
    op.drop_table("selectedinferenceengine")
    op.drop_table("inferenceengine")
