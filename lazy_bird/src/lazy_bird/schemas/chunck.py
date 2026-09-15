from pydantic import BaseModel, ConfigDict

class ChunckOut(BaseModel):
    id: int
    file_id: int
    content: str
    start_line: int
    end_line: int
    start_row: int | None
    end_row: int | None
    meta_data: dict

    model_config = ConfigDict(from_attributes=True)