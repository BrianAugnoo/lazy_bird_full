"""user age, ranked languages and meta

Revision ID: b8d2f4a6c0e1
Revises: a7c1e3f5b9d2
Create Date: 2026-10-12 11:00:00.000000

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d2f4a6c0e1'
down_revision: Union[str, None] = 'a7c1e3f5b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user = sa.table(
    'user',
    sa.column('id', sa.Integer),
    sa.column('language', sa.String),
    sa.column('languages', sa.JSON),
)


def upgrade() -> None:
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('age', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('languages', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('meta', sa.JSON(), nullable=True))

    # The single language becomes the first (best mastered) of the list.
    connection = op.get_bind()
    for row in connection.execute(sa.select(user.c.id, user.c.language)).all():
        if row.language:
            connection.execute(user.update().where(user.c.id == row.id).values(languages=[row.language]))

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('languages', server_default=None)
        batch_op.drop_column('language')


def downgrade() -> None:
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('language', sa.String(), nullable=True))

    # Only the best mastered language survives.
    connection = op.get_bind()
    for row in connection.execute(sa.select(user.c.id, user.c.languages)).all():
        languages = row.languages if isinstance(row.languages, list) else json.loads(row.languages or '[]')
        if languages:
            connection.execute(user.update().where(user.c.id == row.id).values(language=languages[0]))

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('meta')
        batch_op.drop_column('languages')
        batch_op.drop_column('age')
