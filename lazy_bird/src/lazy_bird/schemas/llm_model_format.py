from pydantic import BaseModel


class SelectedFormatIn(BaseModel):
    selected_format: str
