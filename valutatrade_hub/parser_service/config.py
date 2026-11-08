"""Central Parser Service settings and provider identifiers."""

from dataclasses import dataclass, field
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
EXCHANGE_RATE_URL = "https://v6.exchangerate-api.com/v6/{key}/latest/USD"
BASE_FIAT_CURRENCY = "USD"
REQUEST_TIMEOUT = 10
CRYPTO_ID_MAP = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
CRYPTO_CURRENCIES = tuple(CRYPTO_ID_MAP)
FIAT_CURRENCIES = ("EUR", "GBP", "RUB")


@dataclass(frozen=True)
class ParserConfig:
    """Configuration shared by all rate clients and the updater."""

    api_key: str = field(default_factory=lambda: SettingsLoader().api_key)
    coingecko_url: str = COINGECKO_URL
    exchangerate_url: str = EXCHANGE_RATE_URL
    base_currency: str = BASE_FIAT_CURRENCY
    fiat_currencies: tuple[str, ...] = FIAT_CURRENCIES
    crypto_currencies: tuple[str, ...] = CRYPTO_CURRENCIES
    crypto_id_map: dict[str, str] = field(default_factory=lambda: CRYPTO_ID_MAP.copy())
    request_timeout: int = REQUEST_TIMEOUT
    rates_file_path: Path = field(default_factory=lambda: SettingsLoader().data_dir / "rates.json")
    history_file_path: Path = field(default_factory=lambda: SettingsLoader().data_dir / "exchange_rates.json")
