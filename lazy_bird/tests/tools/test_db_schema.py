from lazy_bird.tools import db_schema


def test_the_diagram_describes_every_migrated_table_and_relation():
    db_schema.get_schema_diagram.cache_clear()

    diagram = db_schema.get_schema_diagram()

    assert diagram.startswith("erDiagram")
    assert "    chunk {" in diagram and "    task {" in diagram
    assert "alembic_version" not in diagram
    assert "INTEGER id PK" in diagram
    assert 'file ||--o{ chunk : "id -> file_id"' in diagram
