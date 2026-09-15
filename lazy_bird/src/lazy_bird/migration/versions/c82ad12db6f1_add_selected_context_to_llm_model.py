"""add selected_context to LLMModel

Revision ID: c82ad12db6f1
Revises: 1aafe7416dd5
Create Date: 2026-08-17 15:13:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c82ad12db6f1"
down_revision: Union[str, None] = "1aafe7416dd5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("llmmodel", schema=None) as batch_op:
        batch_op.add_column(sa.Column("selected_context", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("llmmodel", schema=None) as batch_op:
        batch_op.drop_column("selected_context")
