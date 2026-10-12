"""index task and relationship lookups

Revision ID: f6a8b0c2d4e6
Revises: e5b7c9d1f3a5
Create Date: 2026-10-12 15:23:00.145050

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f6a8b0c2d4e6'
down_revision: Union[str, None] = 'e5b7c9d1f3a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Indexes only: existing rows and relationships are preserved.
    with op.batch_alter_table('agent', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_agent_session_id'), ['session_id'], unique=False)

    with op.batch_alter_table('agenthierarchy', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_agenthierarchy_child_id'), ['child_id'], unique=False)

    with op.batch_alter_table('conversation', schema=None) as batch_op:
        batch_op.create_index('ix_conversation_agent_updated', ['agent_id', 'updated_at'], unique=False)

    with op.batch_alter_table('fileprocessing', schema=None) as batch_op:
        batch_op.create_index('ix_fileprocessing_processor_target', ['processor', 'target'], unique=False)
        batch_op.create_index(batch_op.f('ix_fileprocessing_task_id'), ['task_id'], unique=False)

    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.create_index('ix_task_status_finished', ['status', 'finished_at', 'id'], unique=False)
        batch_op.create_index('ix_task_status_position', ['status', 'position'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.drop_index('ix_task_status_position')
        batch_op.drop_index('ix_task_status_finished')

    with op.batch_alter_table('fileprocessing', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_fileprocessing_task_id'))
        batch_op.drop_index('ix_fileprocessing_processor_target')

    with op.batch_alter_table('conversation', schema=None) as batch_op:
        batch_op.drop_index('ix_conversation_agent_updated')

    with op.batch_alter_table('agenthierarchy', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_agenthierarchy_child_id'))

    with op.batch_alter_table('agent', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_agent_session_id'))

