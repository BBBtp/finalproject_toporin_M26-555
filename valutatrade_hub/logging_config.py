"""Rotating application log configuration."""

import logging
from logging.handlers import RotatingFileHandler

from .infra.settings import SettingsLoader


def configure_logging() -> None:
    settings = SettingsLoader()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("valutatrade_hub")
    if logger.handlers:
        return
    logger.setLevel(settings.log_level.upper())
    handler = RotatingFileHandler(settings.data_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
