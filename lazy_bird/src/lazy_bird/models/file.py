from datetime import datetime

from sqlmodel import Field, SQLModel


class File(SQLModel, table=True):
    """A stored file. What was done with it lives in ``FileProcessing`` rows."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default=None)
    path: str = Field(default=None)
    extension: str = Field(default=None)
    size: int = Field(default=None)
    # SHA-256 of the content; processing results remember the hash they were computed from.
    content_hash: str | None = Field(default=None)
    # Modification time of the file on disk when content_hash was computed.
    modified_at: datetime | None = Field(default=None)
    # True when the file disappeared from the storage directory.
    missing: bool = Field(default=False)
