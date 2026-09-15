from sqlmodel import SQLModel, Session, create_engine, select

import lazy_bird.database as database
from lazy_bird.models.api_key import APIKey


def test_db_context_yields_a_session_and_commits(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'session.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "status", database.DatabaseStatus(ready=True))

    with database.db() as session:
        session.add(APIKey(name="OpenAI", key="secret"))
        session.commit()

    with Session(engine) as session:
        assert session.exec(select(APIKey)).one().key == "secret"

    engine.dispose()


def test_test_db_context_creates_tables(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test-session.db'}")
    monkeypatch.setattr(database, "test_engine", engine)

    with database.test_db() as session:
        session.add(APIKey(name="OpenAI", key="secret"))
        session.commit()

    with Session(engine) as session:
        assert session.exec(select(APIKey)).one().name == "OpenAI"

    engine.dispose()
