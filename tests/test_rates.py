"""Rate normalization, freshness and provider failure tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from valutatrade_hub.core.exceptions import ApiRequestError, RateUnavailableError
from valutatrade_hub.core.usecases import RateService
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


def test_cross_rate_uses_usd_prices():
    storage = RatesStorage()
    storage.save({"BTC_USD": Decimal("60000"), "EUR_USD": Decimal("1.25")}, "fixture")
    rates = RateService(storage)
    assert rates.rate("BTC", "EUR") == Decimal("48000")
    assert rates.rate("EUR", "USD") == Decimal("1.25")


def test_stale_and_missing_rate_fail():
    storage = RatesStorage()
    old = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    storage.save({"BTC_USD": Decimal("60000")}, "fixture", updated_at=old)
    with pytest.raises(RateUnavailableError, match="устарел"):
        RateService(storage).rate("BTC", "USD")
    with pytest.raises(RateUnavailableError, match="Нет курса"):
        RateService(storage).rate("ETH", "USD")
    with pytest.raises(RateUnavailableError, match="устарел"):
        RateService(storage).rate("BTC", "BTC")


def test_coingecko_response(monkeypatch):
    payload = {"bitcoin": {"usd": 60000}, "ethereum": {"usd": 3000}, "solana": {"usd": 120}}
    monkeypatch.setattr(
        "requests.get", lambda *args, **kwargs: Mock(json=lambda: payload, raise_for_status=lambda: None)
    )
    assert CoinGeckoClient().fetch_rates()["BTC_USD"] == Decimal("60000")


def test_exchangerate_response_is_inverted(monkeypatch):
    monkeypatch.setenv("EXCHANGERATE_API_KEY", "test-key")
    SettingsLoader().reload()
    payload = {"result": "success", "base_code": "USD", "conversion_rates": {"EUR": 0.8, "GBP": 0.5, "RUB": 100}}
    monkeypatch.setattr(
        "requests.get", lambda *args, **kwargs: Mock(json=lambda: payload, raise_for_status=lambda: None)
    )
    rates = ExchangeRateApiClient().fetch_rates()
    assert rates["EUR_USD"] == Decimal("1.25")
    assert rates["GBP_USD"] == Decimal("2")
    assert rates["RUB_USD"] == Decimal("0.01")


def test_exchangerate_http_error_hides_api_key(monkeypatch):
    key = "private-test-key"
    monkeypatch.setenv("EXCHANGERATE_API_KEY", key)
    SettingsLoader().reload()

    def fail_request(*args, **kwargs):
        raise requests.HTTPError(f"HTTP error at {args[0]}")

    monkeypatch.setattr("requests.get", fail_request)
    with pytest.raises(ApiRequestError) as error:
        ExchangeRateApiClient().fetch_rates()
    assert key not in str(error.value)


def test_parser_config_reads_key_from_environment(monkeypatch):
    monkeypatch.setenv("EXCHANGERATE_API_KEY", "test-key")
    SettingsLoader().reload()
    config = ParserConfig()
    assert config.api_key == "test-key"
    assert config.request_timeout == 10
    assert config.rates_file_path.name == "rates.json"


def test_fiat_client_requires_key():
    with pytest.raises(ApiRequestError, match="EXCHANGERATE_API_KEY"):
        ExchangeRateApiClient().fetch_rates()


def test_malformed_fiat_payload_is_provider_error(monkeypatch):
    monkeypatch.setenv("EXCHANGERATE_API_KEY", "test-key")
    SettingsLoader().reload()
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: Mock(json=lambda: [], raise_for_status=lambda: None))
    with pytest.raises(ApiRequestError, match="неверные данные"):
        ExchangeRateApiClient().fetch_rates()


def test_lesson_fiat_response_shape_is_supported(monkeypatch):
    monkeypatch.setenv("EXCHANGERATE_API_KEY", "test-key")
    SettingsLoader().reload()
    payload = {"result": "success", "base_code": "USD", "rates": {"EUR": 0.8, "GBP": 0.5, "RUB": 100}}
    monkeypatch.setattr(
        "requests.get", lambda *args, **kwargs: Mock(json=lambda: payload, raise_for_status=lambda: None)
    )
    assert ExchangeRateApiClient().fetch_rates()["EUR_USD"] == Decimal("1.25")


def test_rate_history_schema_deduplicates_and_old_data_does_not_replace_latest():
    storage = RatesStorage()
    newer = datetime.now(UTC).isoformat()
    older = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    storage.save({"BTC_USD": Decimal("60000")}, "coingecko", updated_at=newer)
    storage.save({"BTC_USD": Decimal("50000")}, "coingecko", updated_at=older)
    storage.save({"BTC_USD": Decimal("50000")}, "coingecko", updated_at=older)
    assert storage.read()["pairs"]["BTC_USD"]["rate"] == "60000"
    assert storage.read()["last_refresh"] == newer
    assert len(storage.history()) == 2
    assert set(storage.history()[0]) == {"id", "from_currency", "to_currency", "rate", "timestamp", "source", "meta"}
    assert storage.history()[0]["meta"]["raw_id"] == "bitcoin"


def test_partial_provider_failure_keeps_successful_rates():
    good = SimpleNamespace(name="coingecko", fetch_rates=lambda: {"BTC_USD": Decimal("60000")})
    bad = SimpleNamespace(name="exchangerate", fetch_rates=Mock(side_effect=ApiRequestError("key missing")))
    result = RatesUpdater(clients=[good, bad]).run_update()
    assert result["updated"] == {"BTC_USD": Decimal("60000")}
    assert "exchangerate" in result["errors"]
    assert "BTC_USD" in RatesStorage().read()["pairs"]
