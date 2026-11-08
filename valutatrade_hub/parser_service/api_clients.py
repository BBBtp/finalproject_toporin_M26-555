"""HTTP clients that return USD prices for one unit of each currency."""

from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra.settings import SettingsLoader

from .config import COINGECKO_URL, CRYPTO_IDS, EXCHANGE_RATE_URL, FIAT_CODES


def _positive_rate(value: object, code: str) -> Decimal:
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ApiRequestError(f"Некорректный курс {code} в ответе API.") from exc
    if not rate.is_finite() or rate <= 0:
        raise ApiRequestError(f"Некорректный курс {code} в ответе API.")
    return rate


class BaseApiClient(ABC):
    name: str

    @abstractmethod
    def fetch_rates(self) -> dict[str, Decimal]:
        """Return USD price for one unit of each supported currency."""


class CoinGeckoClient(BaseApiClient):
    name = "coingecko"

    def fetch_rates(self) -> dict[str, Decimal]:
        try:
            response = requests.get(
                COINGECKO_URL,
                params={"ids": ",".join(CRYPTO_IDS.values()), "vs_currencies": "usd"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            return {code: _positive_rate(payload[coin_id]["usd"], code) for code, coin_id in CRYPTO_IDS.items()}
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            raise ApiRequestError(f"CoinGecko недоступен или вернул неверные данные: {exc}") from exc


class ExchangeRateApiClient(BaseApiClient):
    name = "exchangerate"

    def fetch_rates(self) -> dict[str, Decimal]:
        key = SettingsLoader().api_key
        if not key:
            raise ApiRequestError("Для фиатных курсов задайте EXCHANGERATE_API_KEY.")
        try:
            response = requests.get(EXCHANGE_RATE_URL.format(key=key), timeout=10)
            response.raise_for_status()
            payload = response.json()
            if payload.get("result") != "success" or payload.get("base_code") != "USD":
                raise ApiRequestError(f"ExchangeRate-API: {payload.get('error-type', 'неверный ответ')}.")
            rates = payload["conversion_rates"]
            return {code: Decimal("1") / _positive_rate(rates[code], code) for code in FIAT_CODES}
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            raise ApiRequestError(f"ExchangeRate-API недоступен или вернул неверные данные: {exc}") from exc
