"""add embedding engine registry and model formats"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "f4c2e9a1b7d3"
down_revision = "d19ec84b73a2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("llmmodel") as batch:
        batch.drop_column("onnx")
        batch.alter_column("format", new_column_name="formats")
        batch.add_column(sa.Column("selected_format", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.execute("UPDATE llmmodel SET selected_format = formats WHERE selected_format IS NULL")
    op.execute("UPDATE llmmodel SET formats = '[\"' || formats || '\"]'")
    with op.batch_alter_table("llmmodel") as batch:
        batch.alter_column("formats", type_=sa.JSON(), nullable=False)
    op.create_table(
        "embeddingengine",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("formats", sa.JSON(), nullable=False),
        sa.Column("kwargs", sa.JSON(), nullable=False),
    )
    op.create_table(
        "selectedembeddingengine",
        sa.Column("id", sa.Integer(), primary_key=True, server_default="1"),
        sa.Column("embedding_engine_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["embedding_engine_id"], ["embeddingengine.id"]),
        sa.CheckConstraint("id = 1", name="selected_embedding_engine_id_is_one"),
    )


def downgrade():
    op.drop_table("selectedembeddingengine")
    op.drop_table("embeddingengine")
    with op.batch_alter_table("llmmodel") as batch:
        batch.drop_column("selected_format")
        batch.alter_column("formats", new_column_name="format", type_=sa.String())
        batch.add_column(sa.Column("onnx", sa.Boolean(), nullable=False, server_default=sa.false()))
