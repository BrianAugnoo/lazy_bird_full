"""remove the AwaitFile table after moving queue state to Huey

Revision ID: a4e7c9d1f2b3
Revises: 9d3f1a7c2b44
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4e7c9d1f2b3"
down_revision: Union[str, None] = "9d3f1a7c2b44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "awaitfile" in inspector.get_table_names():
        op.drop_table("awaitfile")


def downgrade() -> None:
    op.create_table(
        "awaitfile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["file.id"]),
        sa.PrimaryKeyConstraint("id"),
    )