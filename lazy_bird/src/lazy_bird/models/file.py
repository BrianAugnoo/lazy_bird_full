from sqlmodel import Relationship, SQLModel, Field

class File(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default=None)
    path: str = Field(default=None)
    extension: str = Field(default=None)
    size: int = Field(default=None)
    status: str = Field(default="pending")  # pending, processing, format-error, chunck-error, incomplete-vectors, done

