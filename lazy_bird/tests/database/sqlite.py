from sqlalchemy import text

from lazy_bird.database.sql_db.sqlite import initialize


def test_init_db_enables_foreign_keys_and_wal(tmp_path):
    database_path = tmp_path / "sqlite.db"
    engine = initialize(url=f"sqlite:///{database_path}")

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert connection.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"

    engine.dispose()
