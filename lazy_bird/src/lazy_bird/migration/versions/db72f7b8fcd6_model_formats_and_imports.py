"""model weight files, local imports and normalized format names

- ``llmmodel`` gains ``files`` (weight files per format), ``selected_file`` (the GGUF
  quantization in use), ``source`` ("huggingface" or "local") and ``revision``;
- ``dimension`` becomes optional (unknown for some formats);
- ``hf_path`` becomes unique (duplicates get a ``#<id>`` suffix);
- format names are lowercase ("ONNX" -> "onnx");
- names extracted from ``config.json`` (often another model's name) are replaced by
  the repository id. ``files`` is filled by the cache sync at the next startup.

Revision ID: db72f7b8fcd6
Revises: 3873d7d45e9c
Create Date: 2026-10-07 10:00:00

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "db72f7b8fcd6"
down_revision: Union[str, None] = "3873d7d45e9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    seen: set[str] = set()
    for model_id, hf_path, formats, selected in connection.execute(sa.text("SELECT id, hf_path, formats, selected_format FROM llmmodel ORDER BY id")).all():
        unique_path = hf_path if hf_path not in seen else f"{hf_path}#{model_id}"
        seen.add(unique_path)
        lowered = [str(value).lower() for value in json.loads(formats or "[]")]
        connection.execute(
            sa.text("UPDATE llmmodel SET hf_path = :path, name = :path, formats = :formats, selected_format = :selected WHERE id = :id"),
            {"path": unique_path, "formats": json.dumps(lowered), "selected": selected.lower() if selected else None, "id": model_id},
        )
    with op.batch_alter_table("llmmodel") as batch_op:
        batch_op.add_column(sa.Column("revision", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="huggingface"))
        batch_op.add_column(sa.Column("files", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
        batch_op.add_column(sa.Column("selected_file", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.alter_column("dimension", existing_type=sa.Integer(), nullable=True)
        batch_op.create_unique_constraint("uq_llmmodel_hf_path", ["hf_path"])
    with op.batch_alter_table("llmmodel") as batch_op:
        batch_op.alter_column("source", existing_type=sqlmodel.sql.sqltypes.AutoString(), existing_nullable=False, server_default=None)
        batch_op.alter_column("files", existing_type=sa.JSON(), existing_nullable=False, server_default=None)


def downgrade() -> None:
    op.execute("UPDATE llmmodel SET dimension = 0 WHERE dimension IS NULL")
    with op.batch_alter_table("llmmodel") as batch_op:
        batch_op.drop_constraint("uq_llmmodel_hf_path", type_="unique")
        batch_op.alter_column("dimension", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("selected_file")
        batch_op.drop_column("files")
        batch_op.drop_column("source")
        batch_op.drop_column("revision")
