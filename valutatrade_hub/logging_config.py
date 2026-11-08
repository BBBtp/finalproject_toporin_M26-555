"""Rotating application log configuration."""

import logging
import time
from logging.handlers import RotatingFileHandler

from .infra.database import DatabaseManager
from .infra.settings import SettingsLoader


def configure_logging() -> None:
    settings = SettingsLoader()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    DatabaseManager().ensure_files()
    logger = logging.getLogger("valutatrade_hub")
    if logger.handlers:
        return
    logger.setLevel(settings.log_level.upper())
    handler = RotatingFileHandler(settings.log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ")
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logger.addHandler(handler)
