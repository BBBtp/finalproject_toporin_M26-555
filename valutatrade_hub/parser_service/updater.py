"""Fetch and merge independent currency rate providers."""

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
        for client in self.clients:
            if source and client.name != source:
                continue
            try:
                rates = client.fetch_rates()
                if not rates:
                    raise ApiRequestError("Источник вернул пустой список курсов.")
                self.storage.save(rates, client.name)
                updated.update(rates)
            except ApiRequestError as exc:
                errors[client.name] = str(exc)
        if not updated:
            raise ApiRequestError("Не удалось обновить курсы: " + "; ".join(errors.values()))
        return {"updated": updated, "errors": errors}
