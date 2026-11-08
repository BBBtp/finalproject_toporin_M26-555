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

    def read(self, name: str, default: Any) -> Any:
        path = self._path(name)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StorageError(f"Не удалось прочитать {path.name}: {exc}") from exc

    def write(self, name: str, payload: Any) -> None:
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=path.parent, prefix=f".{name}-", suffix=".tmp", delete=False
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
