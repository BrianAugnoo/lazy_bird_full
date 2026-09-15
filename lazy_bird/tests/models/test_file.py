from lazy_bird.models.file import File


def test_file_table_shape():
    table = File.__table__

    assert table.name == "file"
    assert list(table.columns.keys()) == ["id", "name", "path", "extension", "size", "status"]
    assert table.c.id.primary_key is True
    assert table.c.id.autoincrement == "auto"
    assert all(not table.c[column].nullable for column in ("name", "path", "extension", "size", "status"))


def test_file_instance_accepts_storage_metadata():
    record = File(name="report", path="uploads/report.pdf", extension=".pdf", size=10)

    assert record.id is None
    assert record.name == "report"
    assert record.path == "uploads/report.pdf"
    assert record.extension == ".pdf"
    assert record.size == 10
