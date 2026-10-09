"""The saved database choices: read when needed, written only when they change."""

import json
import os
import subprocess
import sys

from lazy_bird import database
from lazy_bird.database.vector_db import lancedb

PROBE = """
import sys
import lazy_bird.database as database
print(database.engine is None, "alembic" in sys.modules)
"""


def test_importing_the_database_package_writes_nothing_and_connects_nothing():
    config_file = database.DATABASE_DIR / "config.json"  # the real one: only its time is read
    before = config_file.stat().st_mtime_ns if config_file.exists() else None
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join(path for path in sys.path if path)}

    output = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, check=True, env=environment).stdout

    assert output.split() == ["True", "False"]  # no engine, and the migration tool is not even loaded
    assert (config_file.stat().st_mtime_ns if config_file.exists() else None) == before


def test_choices_that_no_longer_exist_fall_back_without_rewriting_the_file():
    saved = {"selected_sql_database": "gone", "selected_vector_database": "gone-too"}
    database.CONFIG_FILE.write_text(json.dumps(saved), encoding="utf-8")

    config = database.current_config()

    assert (config.selected_sql_database, config.selected_vector_database) == ("sqlite", "lancedb")
    assert json.loads(database.CONFIG_FILE.read_text(encoding="utf-8")) == saved


def test_a_new_choice_is_saved_and_read_back(tmp_path, monkeypatch):
    monkeypatch.setattr(lancedb, "_connection", None)  # connections are restored after the test
    monkeypatch.setattr(database, "_vector_initialized", None)
    vectors = str(tmp_path / "vectors")
    database.switch_database("vector", "lancedb", {"path": vectors})

    monkeypatch.setattr(database, "_config", None)  # as a new process would

    assert database.current_config().vector_databases["lancedb"].settings == {"path": vectors}
