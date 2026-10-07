"""agent hooks, instructions and presets; tool and hook settings tables

- ``agent`` gains ``hooks``, ``instruction_fulls``, ``instruction_subs`` (lists of
  extension ids) and ``preset``; ``tools`` and ``skills`` become non-null lists;
- ``toolsettings`` and ``hooksettings`` store the configuration of class tools and
  hooks (``file_path``, ``kwargs``, ``kwargs_key``).

Agents created before this revision list tools by function name; they must be
edited to use tool ids (``{extension}-{module}-{function}``), which the agent
endpoints report as invalid until then.

Revision ID: f982faa98909
Revises: db72f7b8fcd6
Create Date: 2026-10-07 11:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "f982faa98909"
down_revision: Union[str, None] = "db72f7b8fcd6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _settings_table(name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("kwargs", sa.JSON(), nullable=False),
        sa.Column("kwargs_key", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_path"),
    )


def upgrade() -> None:
    _settings_table("toolsettings")
    _settings_table("hooksettings")
    op.execute("UPDATE agent SET tools = '[]' WHERE tools IS NULL")
    op.execute("UPDATE agent SET skills = '[]' WHERE skills IS NULL")
    with op.batch_alter_table("agent") as batch_op:
        batch_op.add_column(sa.Column("instruction_fulls", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch_op.add_column(sa.Column("instruction_subs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch_op.add_column(sa.Column("hooks", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch_op.add_column(sa.Column("preset", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.alter_column("tools", existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column("skills", existing_type=sa.JSON(), nullable=False)
    with op.batch_alter_table("agent") as batch_op:
        for column in ("instruction_fulls", "instruction_subs", "hooks"):
            batch_op.alter_column(column, existing_type=sa.JSON(), existing_nullable=False, server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("agent") as batch_op:
        batch_op.alter_column("skills", existing_type=sa.JSON(), nullable=True)
        batch_op.alter_column("tools", existing_type=sa.JSON(), nullable=True)
        batch_op.drop_column("preset")
        batch_op.drop_column("hooks")
        batch_op.drop_column("instruction_subs")
        batch_op.drop_column("instruction_fulls")
    op.drop_table("hooksettings")
    op.drop_table("toolsettings")
