"""message hooks

Revision ID: d1f3a5c7e9b2
Revises: c9e1a3b5d7f2
Create Date: 2026-10-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1f3a5c7e9b2'
down_revision: Union[str, None] = 'c9e1a3b5d7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing messages have nothing attached by hooks.
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hooks', sa.JSON(), nullable=False, server_default='{}'))

    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.alter_column('hooks', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.drop_column('hooks')
