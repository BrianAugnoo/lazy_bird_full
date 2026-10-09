"""task priority: the lowest number now runs first

Priorities used to run highest first with 0 as the default; they now run lowest first
with 5 as the default and 0 reserved for "run now". The change is a mirror around 5
(``new = 5 - old``), so the order of existing tasks is kept. It is its own inverse.

Revision ID: d4a6b8c0e2f4
Revises: c3e5a7b9d1f2
Create Date: 2026-10-09 05:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4a6b8c0e2f4"
down_revision: Union[str, None] = "c3e5a7b9d1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _mirror() -> None:
    task = sa.table("task", sa.column("priority", sa.Integer()))
    op.execute(task.update().values(priority=5 - task.c.priority))


def upgrade() -> None:
    _mirror()


def downgrade() -> None:
    _mirror()
