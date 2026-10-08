"""add cross-encoder engines and presets

Revision ID: c3e5a7b9d1f2
Revises: 492a110a4bf9
Create Date: 2026-10-08 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e5a7b9d1f2"
down_revision: Union[str, None] = "492a110a4bf9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crossencoderengine",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("formats", sa.JSON(), nullable=False),
        sa.Column("kwargs_key", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_crossencoderengine_name"), "crossencoderengine", ["name"], unique=True)
    op.create_table(
        "presetcrossencoder",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("cross_encoder_engine_id", sa.Integer(), nullable=False),
        sa.Column("kwargs", sa.JSON(), nullable=False),
        sa.Column("default", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["cross_encoder_engine_id"], ["crossencoderengine.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "uq_presetcrossencoder_single_default",
        "presetcrossencoder",
        ["default"],
        unique=True,
        sqlite_where=sa.text('"default" = 1'),
        postgresql_where=sa.text('"default"'),
    )


def downgrade() -> None:
    op.drop_index("uq_presetcrossencoder_single_default", table_name="presetcrossencoder")
    op.drop_table("presetcrossencoder")
    op.drop_index(op.f("ix_crossencoderengine_name"), table_name="crossencoderengine")
    op.drop_table("crossencoderengine")
