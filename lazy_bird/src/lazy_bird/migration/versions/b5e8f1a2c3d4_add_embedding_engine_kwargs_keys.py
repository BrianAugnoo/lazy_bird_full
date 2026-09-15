"""add embedding engine kwargs metadata"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5e8f1a2c3d4"
down_revision: Union[str, None] = "a4e7c9d1f2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("embeddingengine") as batch:
        batch.add_column(
            sa.Column("kwargs_keys", sa.JSON(), nullable=False, server_default=sa.text("('{}')"))
        )
    with op.batch_alter_table("embeddingengine") as batch:
        batch.alter_column("kwargs_keys", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("embeddingengine") as batch:
        batch.drop_column("kwargs_keys")