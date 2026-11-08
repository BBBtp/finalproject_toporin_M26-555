"""Application settings, loaded once from the environment."""

import os
from pathlib import Path


class SettingsLoader:
    _instance: "SettingsLoader | None" = None

    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.reload()
        return cls._instance

    def reload(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.data_dir = Path(os.environ.get("VALUTATRADE_DATA_DIR", root / "data"))
        self.ttl_seconds = int(os.environ.get("VALUTATRADE_RATE_TTL", "300"))
        self.api_key = os.environ.get("EXCHANGERATE_API_KEY", "")
        self.log_level = os.environ.get("VALUTATRADE_LOG_LEVEL", "INFO")

    def get(self, key: str) -> object:
        return getattr(self, key)
