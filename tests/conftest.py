"""Isolate every test from checked-in application data."""

import pytest

from valutatrade_hub.infra.settings import SettingsLoader


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setenv("VALUTATRADE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VALUTATRADE_RATE_TTL", "300")
    monkeypatch.delenv("EXCHANGERATE_API_KEY", raising=False)
    SettingsLoader().reload()
    yield
    SettingsLoader().reload()
