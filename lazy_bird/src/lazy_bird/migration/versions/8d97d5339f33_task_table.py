"""add the task table of the background task system

Replaces the Huey SQLite queue (``database/storage/lazy_bird_queue.db``). Jobs that
were pending in Huey are not imported: they only processed pending files, which
auto-embedding queues again at startup. The old queue file can be deleted.

Revision ID: 8d97d5339f33
Revises: eee74044513a
Create Date: 2026-10-07 08:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "8d97d5339f33"
down_revision: Union[str, None] = "eee74044513a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE = "status IN ('queued', 'running', 'paused')"


def upgrade() -> None:
    op.create_table(
        "task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("control", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("run_at", sa.DateTime(), nullable=True),
        sa.Column("resources", sa.JSON(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_kind", "task", ["kind"], unique=False)
    op.create_index("ix_task_queue_order", "task", ["status", "priority", "position"], unique=False)
    op.create_index(
        "uq_task_active_dedupe_key",
        "task",
        ["dedupe_key"],
        unique=True,
        sqlite_where=sa.text(ACTIVE),
        postgresql_where=sa.text(ACTIVE),
    )


def downgrade() -> None:
    op.drop_index("uq_task_active_dedupe_key", table_name="task")
    op.drop_index("ix_task_queue_order", table_name="task")
    op.drop_index("ix_task_kind", table_name="task")
    op.drop_table("task")
