"""move chunk storage to vector databases"""
from alembic import op
import sqlalchemy as sa

revision = "9d3f1a7c2b44"
down_revision = "f4c2e9a1b7d3"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("selectedmodelembeding") as batch:
        batch.add_column(sa.Column("batch", sa.Integer(), nullable=False, server_default="1"))
    op.create_table("vectordatabase", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(), nullable=False, unique=True))
    op.create_table("embedded", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("file_id", sa.Integer(), nullable=False), sa.Column("llm_model_id", sa.Integer(), nullable=False), sa.Column("status", sa.String(), nullable=False, server_default="pending"), sa.Column("created_at", sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(["file_id"], ["file.id"]), sa.ForeignKeyConstraint(["llm_model_id"], ["llmmodel.id"]), sa.UniqueConstraint("file_id", "llm_model_id", name="uq_embedded_file_model"))
    op.create_table("embeddedvectordatabase", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("embedded_id", sa.Integer(), nullable=False), sa.Column("vector_database_id", sa.Integer(), nullable=False), sa.ForeignKeyConstraint(["embedded_id"], ["embedded.id"]), sa.ForeignKeyConstraint(["vector_database_id"], ["vectordatabase.id"]), sa.UniqueConstraint("embedded_id", "vector_database_id", name="uq_embedded_vector_database"))
    op.drop_table("chunk")

def downgrade():
    op.create_table("chunk", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("file_id", sa.Integer(), nullable=False), sa.Column("content", sa.String(), nullable=False), sa.Column("start_line", sa.Integer(), nullable=False), sa.Column("end_line", sa.Integer(), nullable=False), sa.Column("start_row", sa.Integer()), sa.Column("end_row", sa.Integer()), sa.Column("meta_data", sa.JSON(), nullable=False), sa.ForeignKeyConstraint(["file_id"], ["file.id"]))
    op.drop_table("embeddedvectordatabase"); op.drop_table("embedded"); op.drop_table("vectordatabase")
    with op.batch_alter_table("selectedmodelembeding") as batch:
        batch.drop_column("batch")
