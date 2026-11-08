"""Optional periodic rate refresh used by an external runner."""

import logging
import time

from valutatrade_hub.core.exceptions import ApiRequestError

from .updater import RatesUpdater


def run_forever(interval_seconds: int = 300, updater: RatesUpdater | None = None) -> None:
    """Refresh until interrupted; failures are logged and retried."""
    if interval_seconds <= 0:
        raise ValueError("Интервал обновления должен быть положительным.")
    service = updater or RatesUpdater()
    while True:
        try:
            service.run_update()
        except ApiRequestError:
            logging.getLogger(__name__).exception("Не удалось обновить курсы")
        time.sleep(interval_seconds)
