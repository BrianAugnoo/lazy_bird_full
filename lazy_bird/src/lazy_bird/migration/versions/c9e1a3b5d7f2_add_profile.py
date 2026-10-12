"""add profile

Revision ID: c9e1a3b5d7f2
Revises: b8d2f4a6c0e1
Create Date: 2026-10-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e1a3b5d7f2'
down_revision: Union[str, None] = 'b8d2f4a6c0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user = sa.table('user', sa.column('id', sa.Integer))
profile = sa.table('profile', sa.column('id', sa.Integer), sa.column('user_id', sa.Integer))


def upgrade() -> None:
    op.create_table('profile',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.CheckConstraint('id = 1', name='ck_profile_single_instance'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )

    # Users that already exist: the first one added is the profile's user.
    connection = op.get_bind()
    first = connection.execute(sa.select(sa.func.min(user.c.id))).scalar()
    if first is not None:
        connection.execute(profile.insert().values(id=1, user_id=first))


def downgrade() -> None:
    op.drop_table('profile')
