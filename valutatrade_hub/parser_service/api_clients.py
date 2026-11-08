"""HTTP clients that return USD prices for one unit of each currency."""

from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import MAX_RATE, MIN_RATE
from valutatrade_hub.infra.settings import SettingsLoader

from .config import COINGECKO_URL, CRYPTO_IDS, EXCHANGE_RATE_URL, FIAT_CODES


def _positive_rate(value: object, code: str) -> Decimal:
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ApiRequestError(f"Некорректный курс {code} в ответе API.") from exc
    if not rate.is_finite() or rate < MIN_RATE or rate > MAX_RATE:
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
        except requests.RequestException:
            raise ApiRequestError("CoinGecko: ошибка сети или HTTP. Повторите обновление позже.") from None
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ApiRequestError("CoinGecko вернул неверные данные.") from exc


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
            if not isinstance(payload, dict):
                raise ApiRequestError("ExchangeRate-API вернул неверные данные.")
            if payload.get("result") != "success" or payload.get("base_code") != "USD":
                reason = payload.get("error-type", "неверный ответ")
                allowed = {"unsupported-code", "malformed-request", "invalid-key", "inactive-account", "quota-reached"}
                if reason not in allowed:
                    reason = "неверный ответ"
                raise ApiRequestError(f"ExchangeRate-API: {reason}.")
            rates = payload["conversion_rates"]
            if not isinstance(rates, dict):
                raise ApiRequestError("ExchangeRate-API вернул неверные данные.")
            return {code: Decimal("1") / _positive_rate(rates[code], code) for code in FIAT_CODES}
        except requests.RequestException:
            raise ApiRequestError("ExchangeRate-API: ошибка сети или HTTP. Проверьте ключ и лимит запросов.") from None
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ApiRequestError("ExchangeRate-API вернул неверные данные.") from exc
