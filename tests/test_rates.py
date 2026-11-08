"""Rate normalization, freshness and provider failure tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from valutatrade_hub.core.exceptions import ApiRequestError, RateUnavailableError
from valutatrade_hub.core.usecases import RateService
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


def test_cross_rate_uses_usd_prices():
    storage = RatesStorage()
    storage.save({"BTC": Decimal("60000"), "EUR": Decimal("1.25")}, "fixture")
    rates = RateService(storage)
    assert rates.rate("BTC", "EUR") == Decimal("48000")
    assert rates.rate("EUR", "USD") == Decimal("1.25")


def test_stale_and_missing_rate_fail():
    storage = RatesStorage()
    old = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    storage.save({"BTC": Decimal("60000")}, "fixture", updated_at=old)
    with pytest.raises(RateUnavailableError, match="устарел"):
        RateService(storage).rate("BTC", "USD")
    with pytest.raises(RateUnavailableError, match="Нет курса"):
        RateService(storage).rate("ETH", "USD")


def test_coingecko_response(monkeypatch):
    payload = {"bitcoin": {"usd": 60000}, "ethereum": {"usd": 3000}, "solana": {"usd": 120}}
    monkeypatch.setattr(
        "requests.get", lambda *args, **kwargs: Mock(json=lambda: payload, raise_for_status=lambda: None)
    )
    assert CoinGeckoClient().fetch_rates()["BTC"] == Decimal("60000")


def test_exchangerate_response_is_inverted(monkeypatch):
    monkeypatch.setenv("EXCHANGERATE_API_KEY", "test-key")
    SettingsLoader().reload()
    payload = {"result": "success", "base_code": "USD", "conversion_rates": {"EUR": 0.8, "GBP": 0.5, "RUB": 100}}
    monkeypatch.setattr(
        "requests.get", lambda *args, **kwargs: Mock(json=lambda: payload, raise_for_status=lambda: None)
    )
    rates = ExchangeRateApiClient().fetch_rates()
    assert rates["EUR"] == Decimal("1.25")
    assert rates["GBP"] == Decimal("2")
    assert rates["RUB"] == Decimal("0.01")


def test_partial_provider_failure_keeps_successful_rates():
    good = SimpleNamespace(name="coingecko", fetch_rates=lambda: {"BTC": Decimal("60000")})
    bad = SimpleNamespace(name="exchangerate", fetch_rates=Mock(side_effect=ApiRequestError("key missing")))
    result = RatesUpdater(clients=[good, bad]).run_update()
    assert result["updated"] == {"BTC": Decimal("60000")}
    assert "exchangerate" in result["errors"]
    assert "BTC_USD" in RatesStorage().read()["pairs"]
