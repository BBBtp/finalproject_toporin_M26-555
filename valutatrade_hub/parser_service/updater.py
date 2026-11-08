"""Fetch and merge independent currency rate providers."""

import logging
from decimal import Decimal

from valutatrade_hub.core.exceptions import ApiRequestError, ValidationError

from .api_clients import BaseApiClient, CoinGeckoClient, ExchangeRateApiClient
from .storage import RatesStorage


class RatesUpdater:
    def __init__(self, storage: RatesStorage | None = None, clients: list[BaseApiClient] | None = None) -> None:
        self.storage = storage or RatesStorage()
        self.clients = clients if clients is not None else [CoinGeckoClient(), ExchangeRateApiClient()]

    def run_update(self, source: str | None = None) -> dict:
        if source and source not in {client.name for client in self.clients}:
            raise ValidationError(f"Неизвестный источник курсов: {source}.")
        updated: dict[str, Decimal] = {}
        errors: dict[str, str] = {}
        logger = logging.getLogger("valutatrade_hub.parser")
        logger.info("Starting rates update source=%s", source or "all")
        for client in self.clients:
            if source and client.name != source:
                continue
            try:
                logger.info("Fetching from %s", client.name)
                rates = client.fetch_rates()
                if not rates:
                    raise ApiRequestError("Источник вернул пустой список курсов.")
                self.storage.save(rates, client.name)
                updated.update(rates)
                logger.info("Fetched from %s: %d rates", client.name, len(rates))
            except ApiRequestError as exc:
                errors[client.name] = str(exc)
                logger.error("Failed to fetch from %s: %s", client.name, exc)
        if not updated:
            reasons = [message.removeprefix("Ошибка при обращении к внешнему API: ") for message in errors.values()]
            raise ApiRequestError("Не удалось обновить курсы: " + "; ".join(reasons))
        logger.info("Rates update complete: %d rates, %d errors", len(updated), len(errors))
        return {"updated": updated, "errors": errors, "last_refresh": self.storage.read()["last_refresh"]}
