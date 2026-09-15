"""add selected model embeding

Revision ID: 7f2ef6d9d5d2
Revises: dad756b512a1
Create Date: 2026-08-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f2ef6d9d5d2'
down_revision: Union[str, None] = 'dad756b512a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'selectedmodelembeding',
        sa.Column('id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('llm_model_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['llm_model_id'], ['llmmodel.id']),
        sa.CheckConstraint('id = 1', name='selected_model_embeding_id_is_one'),
    )


def downgrade() -> None:
    op.drop_table('selectedmodelembeding')
