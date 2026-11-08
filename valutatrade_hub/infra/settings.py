"""Application settings, loaded once from the environment."""

import os
import tomllib
from pathlib import Path
from typing import Any


class SettingsLoader:
    """One cached settings object; __new__ keeps imports from duplicating it."""

    _instance: "SettingsLoader | None" = None

    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.reload()
        return cls._instance

    def reload(self) -> None:
        root = Path(__file__).resolve().parents[2]
        project_file = root / "pyproject.toml"
        if project_file.exists():
            with project_file.open("rb") as stream:
                config = tomllib.load(stream).get("tool", {}).get("valutatrade", {})
        else:
            root = Path.cwd()
            config = {}
        configured_data_dir = Path(config.get("data_dir", "data"))
        if not configured_data_dir.is_absolute():
            configured_data_dir = root / configured_data_dir
        self.data_dir = Path(os.environ.get("VALUTATRADE_DATA_DIR", configured_data_dir))
        self.ttl_seconds = int(os.environ.get("VALUTATRADE_RATE_TTL", config.get("rates_ttl_seconds", 300)))
        if self.ttl_seconds <= 0:
            raise ValueError("RATES_TTL_SECONDS должен быть положительным.")
        self.base_currency = config.get("base_currency", "USD")
        self.log_file = self.data_dir / Path(config.get("log_file", "data/app.log")).name
        self.api_key = os.environ.get("EXCHANGERATE_API_KEY", "")
        self.log_level = os.environ.get("VALUTATRADE_LOG_LEVEL", config.get("log_level", "INFO"))

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
