"""Saved settings of tools and hooks modules (``ToolSettings`` / ``HookSettings`` tables)."""

from __future__ import annotations

from typing import Any

from sqlmodel import SQLModel, select

from lazy_bird.database import db
from lazy_bird.errors import NotFoundError
from lazy_bird.extension.settings import SettingsContract
from lazy_bird.schemas.extension_settings import ModuleSettingsOut


class ModuleSettingsStore:
    def __init__(self, table: type[SQLModel], kind: str) -> None:
        self.table = table
        self.kind = kind
        self.contracts: dict[str, SettingsContract] = {}

    def sync(self, contracts: dict[str, SettingsContract]) -> None:
        """Record the settings form of every discovered module, keeping saved values."""
        self.contracts = dict(contracts)
        with db() as session:
            for file_path, contract in contracts.items():
                row = session.exec(select(self.table).where(self.table.file_path == file_path)).first()
                if row is None:
                    row = self.table(file_path=file_path, kwargs={})
                row.kwargs_key = contract.kwargs_key()
                session.add(row)
            session.commit()

    def _out(self, row: SQLModel) -> ModuleSettingsOut:
        contract = self.contracts.get(row.file_path)
        errors = contract.errors(row.kwargs) if contract else {"__root__": "The module is not installed anymore."}
        return ModuleSettingsOut.model_validate(row).model_copy(
            update={"available": contract is not None, "valid": not errors, "errors": errors}
        )

    def all(self) -> list[ModuleSettingsOut]:
        with db() as session:
            rows = session.exec(select(self.table).order_by(self.table.file_path)).all()
        return [self._out(row) for row in rows]

    def get(self, file_path: str) -> ModuleSettingsOut:
        with db() as session:
            row = session.exec(select(self.table).where(self.table.file_path == file_path)).first()
        if row is None:
            raise NotFoundError(f"{self.kind.capitalize()} settings", file_path, code="settings_not_found")
        return self._out(row)

    def saved(self, file_path: str) -> dict[str, Any]:
        return dict(self.get(file_path).kwargs)

    def update(self, file_path: str, kwargs: dict[str, Any]) -> ModuleSettingsOut:
        contract = self.contracts.get(file_path)
        if contract is None:
            raise NotFoundError(f"{self.kind.capitalize()} module with settings", file_path, code="settings_not_found")
        normalized = contract.normalize(kwargs)
        with db() as session:
            row = session.exec(select(self.table).where(self.table.file_path == file_path)).first()
            if row is None:
                row = self.table(file_path=file_path, kwargs_key=contract.kwargs_key())
            row.kwargs = normalized
            session.add(row)
            session.commit()
            session.refresh(row)
        return self._out(row)
