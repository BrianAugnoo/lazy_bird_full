"""per-processing file states and content hashes

- ``file`` gains ``content_hash`` (SHA-256), ``modified_at`` and ``missing``, computed
  here from the files on disk, and loses the global ``status`` column;
- ``file_processing`` holds one state per (file, processor, target).

The old status is converted: ``format-error`` -> chunking ``unsupported``,
``chunck-error`` -> chunking ``failed``, and files that have chunks get a chunking
``done`` row for their current content. Embeddings are re-queued at startup.

Revision ID: 3873d7d45e9c
Revises: 8d97d5339f33
Create Date: 2026-10-07 09:00:00

"""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "3873d7d45e9c"
down_revision: Union[str, None] = "8d97d5339f33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _identity(path: str) -> tuple[str | None, datetime | None, bool]:
    """Return (sha256, modification time, missing) of a stored file."""
    try:
        file_path = Path(path)
        stat = file_path.stat()
        digest = hashlib.sha256()
        with file_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest(), datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(tzinfo=None), False
    except OSError:
        return None, None, True


def upgrade() -> None:
    connection = op.get_bind()
    op.create_table(
        "fileprocessing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("processor", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("content_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["file.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "processor", "target", name="uq_file_processing"),
    )
    op.create_index("ix_fileprocessing_file_id", "fileprocessing", ["file_id"], unique=False)

    with op.batch_alter_table("file") as batch_op:
        batch_op.add_column(sa.Column("content_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column("modified_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("missing", sa.Boolean(), nullable=False, server_default=sa.false()))

    files = connection.execute(sa.text("SELECT id, path, status FROM file")).all()
    chunked = {row[0] for row in connection.execute(sa.text("SELECT DISTINCT file_id FROM chunk")).all()}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for file_id, path, status in files:
        content_hash, modified_at, missing = _identity(path)
        connection.execute(
            sa.text("UPDATE file SET content_hash = :hash, modified_at = :modified, missing = :missing WHERE id = :id"),
            {"hash": content_hash, "modified": modified_at, "missing": missing, "id": file_id},
        )
        state = {"format-error": "unsupported", "chunck-error": "failed"}.get(status)
        if state is None and file_id in chunked and content_hash is not None:
            state = "done"
        if state is not None:
            connection.execute(
                sa.text(
                    "INSERT INTO fileprocessing (file_id, processor, target, state, content_hash, updated_at) "
                    "VALUES (:file_id, 'chunking', '', :state, :hash, :now)"
                ),
                {"file_id": file_id, "state": state, "hash": content_hash, "now": now},
            )

    with op.batch_alter_table("file") as batch_op:
        batch_op.alter_column("missing", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
        batch_op.drop_column("status")


def downgrade() -> None:
    connection = op.get_bind()
    with op.batch_alter_table("file") as batch_op:
        batch_op.add_column(sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="pending"))
    rows = connection.execute(sa.text("SELECT file_id, processor, state FROM fileprocessing")).all()
    states: dict[int, dict[str, str]] = {}
    for file_id, processor, state in rows:
        states.setdefault(file_id, {})[processor] = state
    for file_id, by_processor in states.items():
        chunking, embedding = by_processor.get("chunking"), by_processor.get("embedding")
        status = (
            "format-error" if chunking == "unsupported"
            else "chunck-error" if chunking == "failed"
            else "embedding-error" if embedding == "failed"
            else "done" if chunking == "done" and embedding == "done"
            else "pending"
        )
        connection.execute(sa.text("UPDATE file SET status = :status WHERE id = :id"), {"status": status, "id": file_id})
    with op.batch_alter_table("file") as batch_op:
        batch_op.alter_column("status", existing_type=sqlmodel.sql.sqltypes.AutoString(), existing_nullable=False, server_default=None)
        batch_op.drop_column("missing")
        batch_op.drop_column("modified_at")
        batch_op.drop_column("content_hash")
    op.drop_index("ix_fileprocessing_file_id", table_name="fileprocessing")
    op.drop_table("fileprocessing")
