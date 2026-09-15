from sqlmodel import SQLModel, Field

class APIKey(SQLModel, table=True):
    name: str = Field(default=None, primary_key=True)
    key: str = Field(default=None)