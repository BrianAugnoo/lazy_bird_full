"""store chunks in SQL and replace the Embedded join tables

- create ``chunk`` (content, positions, token count and metadata of each chunk);
- drop ``embedded``, ``embeddedvectordatabase`` and ``vectordatabase``: vector
  databases now hold one table per model with ``chunk_id`` and ``vector`` only;
- files that were (being) embedded go back to ``pending`` so they are chunked and
  embedded again.

Vector data: tables written before this revision (LanceDB tables named
``model_*``) are ignored by the new layout. They can be deleted safely, e.g. by
removing ``database/storage/lance/`` while the server is stopped.

Revision ID: eee74044513a
Revises: 39c55806b344
Create Date: 2026-10-07 07:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "eee74044513a"
down_revision: Union[str, None] = "39c55806b344"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RESET_STATUSES = ("done", "processing", "incomplete-vectors", "embedding-error")


def upgrade() -> None:
    op.create_table(
        "chunk",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("start_row", sa.Integer(), nullable=True),
        sa.Column("end_row", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["file.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "position", name="uq_chunk_file_position"),
    )
    op.create_index("ix_chunk_file_id", "chunk", ["file_id"], unique=False)

    op.drop_table("embeddedvectordatabase")
    op.drop_table("embedded")
    op.drop_table("vectordatabase")

    statuses = ", ".join(f"'{status}'" for status in RESET_STATUSES)
    op.execute(f"UPDATE file SET status = 'pending' WHERE status IN ({statuses})")


def downgrade() -> None:
    op.create_table(
        "vectordatabase",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )
    op.create_table(
        "embedded",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("llm_model_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["file.id"]),
        sa.ForeignKeyConstraint(["llm_model_id"], ["llmmodel.id"]),
        sa.UniqueConstraint("file_id", "llm_model_id", name="uq_embedded_file_model"),
    )
    op.create_table(
        "embeddedvectordatabase",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("embedded_id", sa.Integer(), nullable=False),
        sa.Column("vector_database_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["embedded_id"], ["embedded.id"]),
        sa.ForeignKeyConstraint(["vector_database_id"], ["vectordatabase.id"]),
        sa.UniqueConstraint("embedded_id", "vector_database_id", name="uq_embedded_vector_database"),
    )
    op.drop_index("ix_chunk_file_id", table_name="chunk")
    op.drop_table("chunk")
