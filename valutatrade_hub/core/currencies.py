"""Supported fiat and crypto currencies."""

from abc import ABC
from dataclasses import dataclass

from .exceptions import CurrencyNotFoundError, ValidationError


@dataclass(frozen=True)
class Currency(ABC):
    code: str
    name: str

    def __post_init__(self) -> None:
        if not (2 <= len(self.code) <= 5 and self.code.isascii() and self.code.isalpha() and self.code.isupper()):
            raise ValidationError("Код валюты должен содержать 2–5 заглавных латинских букв.")
        if not self.name.strip():
            raise ValidationError("Название валюты не может быть пустым.")


@dataclass(frozen=True)
class FiatCurrency(Currency):
    pass


@dataclass(frozen=True)
class CryptoCurrency(Currency):
    pass


REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("USD", "US Dollar"),
    "EUR": FiatCurrency("EUR", "Euro"),
    "GBP": FiatCurrency("GBP", "British Pound"),
    "RUB": FiatCurrency("RUB", "Russian Ruble"),
    "BTC": CryptoCurrency("BTC", "Bitcoin"),
    "ETH": CryptoCurrency("ETH", "Ethereum"),
    "SOL": CryptoCurrency("SOL", "Solana"),
}


def get_currency(code: str) -> Currency:
    """Resolve a supported code, case insensitively."""
    normalized = code.strip().upper()
    try:
        return REGISTRY[normalized]
    except KeyError as exc:
        raise CurrencyNotFoundError(f"Валюта {normalized!r} не поддерживается.") from exc
