import pytest
from pydantic import ValidationError

from lazy_bird.models.file import File
from lazy_bird.schemas.files import FileOut


def test_file_output_reads_model_attributes():
    schema = FileOut.model_validate(
        File(id=1, name="report", path="uploads/report.pdf", extension=".pdf", size=42)
    )

    assert schema.model_dump() == {
        "id": 1,
        "name": "report",
        "size": 42,
        "extension": ".pdf",
        "path": "uploads/report.pdf",
        "status": "pending",
        "embedded_by": [],
        "vetor_db": [],
    }


def test_file_output_requires_complete_metadata():
    with pytest.raises(ValidationError):
        FileOut(name="report", extension=".pdf", size=42)
