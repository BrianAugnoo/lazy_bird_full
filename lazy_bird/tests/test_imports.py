import importlib

import lazy_bird.models
from sqlmodel import SQLModel


def test_main_module_exposes_fastapi_application():
    main_module = importlib.import_module("lazy_bird.main")

    assert hasattr(main_module, "app")


def test_all_model_modules_are_registered_in_metadata():
    table_names = set(SQLModel.metadata.tables)

    assert {"apikey", "file", "llmmodel"}.issubset(table_names)
