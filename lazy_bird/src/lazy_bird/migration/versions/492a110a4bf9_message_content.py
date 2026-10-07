"""message content column and normalized tool metadata

- ``message.content`` holds the text (it was ``meta["content"]``);
- ``tool-calling`` messages keep their calls in ``meta.tool_calls``;
- ``tool-response`` messages store the result in ``content`` and
  ``meta.tool_call_id`` / ``meta.name``;
- index on ``message.conversation_id``.

Revision ID: 492a110a4bf9
Revises: f982faa98909
Create Date: 2026-10-07 12:00:00

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "492a110a4bf9"
down_revision: Union[str, None] = "f982faa98909"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _as_text(value) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def upgrade() -> None:
    connection = op.get_bind()
    with op.batch_alter_table("message") as batch_op:
        batch_op.add_column(sa.Column("content", sa.Text(), nullable=True))
        batch_op.create_index("ix_message_conversation_id", ["conversation_id"], unique=False)
    for message_id, role, raw in connection.execute(sa.text("SELECT id, role, meta FROM message")).all():
        meta = json.loads(raw) if raw else {}
        content = meta.pop("content", None)
        if role == "tool-calling":
            meta["tool_calls"] = meta.pop("tool-calling", None) or []
        elif role == "tool-response":
            response = meta.pop("tool-response", None) or {}
            content = _as_text(response.get("result"))
            meta.update({"tool_call_id": response.get("id"), "name": response.get("name"), "status": "ok"})
        connection.execute(
            sa.text("UPDATE message SET content = :content, meta = :meta WHERE id = :id"),
            {"content": _as_text(content), "meta": json.dumps(meta), "id": message_id},
        )


def downgrade() -> None:
    connection = op.get_bind()
    for message_id, role, content, raw in connection.execute(sa.text("SELECT id, role, content, meta FROM message")).all():
        meta = json.loads(raw) if raw else {}
        if role == "tool-calling":
            meta["tool-calling"] = meta.pop("tool_calls", [])
            meta["content"] = content
        elif role == "tool-response":
            meta = {"tool-response": {"id": meta.get("tool_call_id"), "name": meta.get("name"), "result": content}}
        else:
            meta["content"] = content
        connection.execute(sa.text("UPDATE message SET meta = :meta WHERE id = :id"), {"meta": json.dumps(meta), "id": message_id})
    with op.batch_alter_table("message") as batch_op:
        batch_op.drop_index("ix_message_conversation_id")
        batch_op.drop_column("content")
