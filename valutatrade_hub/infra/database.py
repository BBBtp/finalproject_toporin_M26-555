"""Atomic local JSON persistence."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from valutatrade_hub.core.exceptions import StorageError

from .settings import SettingsLoader


class DatabaseManager:
    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def data_dir(self) -> Path:
        return SettingsLoader().data_dir

    def _path(self, name: str) -> Path:
        if name not in {"users", "portfolios", "rates", "exchange_rates"}:
            raise StorageError(f"Неизвестное хранилище: {name}.")
        return self.data_dir / f"{name}.json"

    def _recover_accounts(self) -> None:
        """Roll back an interrupted registration before exposing either store."""
        journal = self.data_dir / ".registration-journal.json"
        if not journal.exists():
            return
        try:
            previous = json.loads(journal.read_text(encoding="utf-8"))
            self._write_path(self._path("portfolios"), previous["portfolios"])
            self._write_path(self._path("users"), previous["users"])
            journal.unlink()
        except (OSError, ValueError, KeyError, TypeError, StorageError) as exc:
            raise StorageError("Не удалось восстановить регистрацию; проверьте доступность каталога data.") from exc

    def write_accounts(self, users: list[dict], portfolios: dict) -> None:
        """Update both account stores with a rollback journal for crash recovery."""
        self._recover_accounts()
        previous = {"users": self.read("users", []), "portfolios": self.read("portfolios", {})}
        journal = self.data_dir / ".registration-journal.json"
        self._write_path(journal, previous)
        try:
            self._write_path(self._path("portfolios"), portfolios)
            self._write_path(self._path("users"), users)
            journal.unlink()
        except (OSError, StorageError) as exc:
            try:
                self._recover_accounts()
            except StorageError:
                raise StorageError(
                    "Регистрация не завершена; восстановление будет повторено при следующем запуске."
                ) from exc
            raise StorageError("Регистрация не завершена; прежние данные восстановлены.") from exc

    def ensure_files(self) -> None:
        """Create empty local stores on first run without overwriting data."""
        self._recover_accounts()
        for name, default in (
            ("users", []),
            ("portfolios", {}),
            ("rates", {"pairs": {}, "last_refresh": None}),
            ("exchange_rates", []),
        ):
            if not self._path(name).exists():
                self.write(name, default)

    def read(self, name: str, default: Any) -> Any:
        self._recover_accounts()
        path = self._path(name)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StorageError(f"Не удалось прочитать {path.name}: {exc}") from exc

    def write(self, name: str, payload: Any) -> None:
        self._recover_accounts()
        self._write_path(self._path(name), payload)

    def _write_path(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=path.parent, prefix=f".{path.stem}-", suffix=".tmp", delete=False
            ) as stream:
                temporary = stream.name
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except (OSError, TypeError, ValueError) as exc:
            raise StorageError(f"Не удалось сохранить {path.name}: {exc}") from exc
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
