"""Supported fiat and crypto currencies."""

from abc import ABC, abstractmethod
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

    @abstractmethod
    def get_display_info(self) -> str:
        """Describe the currency for a user-facing table or log."""


@dataclass(frozen=True)
class FiatCurrency(Currency):
    issuing_country: str

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


@dataclass(frozen=True)
class CryptoCurrency(Currency):
    algorithm: str
    market_cap: float

    def get_display_info(self) -> str:
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"


REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("USD", "US Dollar", "United States"),
    "EUR": FiatCurrency("EUR", "Euro", "Eurozone"),
    "GBP": FiatCurrency("GBP", "British Pound", "United Kingdom"),
    "RUB": FiatCurrency("RUB", "Russian Ruble", "Russia"),
    "BTC": CryptoCurrency("BTC", "Bitcoin", "SHA-256", 0.0),
    "ETH": CryptoCurrency("ETH", "Ethereum", "Proof of Stake", 0.0),
    "SOL": CryptoCurrency("SOL", "Solana", "Proof of History", 0.0),
}


def get_currency(code: str) -> Currency:
    """Resolve a supported code, case insensitively."""
    normalized = code.strip().upper()
    try:
        return REGISTRY[normalized]
    except KeyError as exc:
        raise CurrencyNotFoundError(f"Неизвестная валюта {normalized!r}.") from exc
