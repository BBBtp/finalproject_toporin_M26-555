"""HTTP clients that return USD prices for one unit of each currency."""

from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import MAX_RATE, MIN_RATE

from .config import ParserConfig


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

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, Decimal]:
        try:
            response = requests.get(
                self.config.coingecko_url,
                params={"ids": ",".join(self.config.crypto_id_map.values()), "vs_currencies": "usd"},
                timeout=self.config.request_timeout,
            )
            response.raise_for_status()
            payload = response.json()
            return {
                f"{code}_USD": _positive_rate(payload[coin_id]["usd"], code)
                for code, coin_id in self.config.crypto_id_map.items()
            }
        except requests.RequestException as exc:
            if getattr(exc.response, "status_code", None) == 429:
                raise ApiRequestError("CoinGecko: превышен лимит запросов (429). Повторите позже.") from None
            raise ApiRequestError("CoinGecko: ошибка сети или HTTP. Повторите обновление позже.") from None
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ApiRequestError("CoinGecko вернул неверные данные.") from exc


class ExchangeRateApiClient(BaseApiClient):
    name = "exchangerate"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, Decimal]:
        key = self.config.api_key
        if not key:
            raise ApiRequestError("Для фиатных курсов задайте EXCHANGERATE_API_KEY.")
        try:
            response = requests.get(self.config.exchangerate_url.format(key=key), timeout=self.config.request_timeout)
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
            rates = payload.get("conversion_rates", payload.get("rates"))
            if not isinstance(rates, dict):
                raise ApiRequestError("ExchangeRate-API вернул неверные данные.")
            return {
                f"{code}_USD": Decimal("1") / _positive_rate(rates[code], code) for code in self.config.fiat_currencies
            }
        except requests.RequestException as exc:
            if getattr(exc.response, "status_code", None) == 401:
                raise ApiRequestError("ExchangeRate-API: неверный ключ (401).") from None
            if getattr(exc.response, "status_code", None) == 429:
                raise ApiRequestError("ExchangeRate-API: превышен лимит запросов (429).") from None
            raise ApiRequestError("ExchangeRate-API: ошибка сети или HTTP. Проверьте ключ и лимит запросов.") from None
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ApiRequestError("ExchangeRate-API вернул неверные данные.") from exc
