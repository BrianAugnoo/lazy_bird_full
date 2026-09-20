"""remove inferenceengine column: format

Revision ID: f1c4fdf11dc0
Revises: 1daafd26e24c
Create Date: 2026-09-18 14:38:21.921270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f1c4fdf11dc0'
down_revision: Union[str, None] = '1daafd26e24c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('inferenceengine', 'formats')


def downgrade() -> None:
    op.add_column('inferenceengine', sa.Column('formats', sqlmodel.sql.sqltypes.JSON, nullable=False))
