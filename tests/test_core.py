"""Core validation and local storage tests."""

from decimal import Decimal

import pytest

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import InsufficientFundsError, ValidationError
from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import parse_amount
from valutatrade_hub.infra.database import DatabaseManager


@pytest.mark.parametrize(
    "value",
    ["0", "-2", "NaN", "Infinity", "-Infinity", "abc", True, "1e999999", "1e-999999", "0.123456789"],
)
def test_invalid_amounts(value):
    with pytest.raises(ValidationError):
        parse_amount(value)


def test_wallet_never_goes_negative():
    wallet = Wallet("USD")
    wallet.deposit("10.50")
    with pytest.raises(InsufficientFundsError):
        wallet.withdraw("10.51")
    assert wallet.balance == Decimal("10.50")


def test_tiny_internal_change_is_not_lost_to_decimal_rounding():
    wallet = Wallet("USD", Decimal("1000000000"))
    wallet.deposit(Decimal("1e-24"))
    assert wallet.balance == Decimal("1000000000.000000000000000000000001")


def test_json_write_replaces_previous_snapshot():
    database = DatabaseManager()
    database.write("portfolios", {"one": {"balance": "1"}})
    database.write("portfolios", {"one": {"balance": "2"}})
    assert database.read("portfolios", {})["one"]["balance"] == "2"
    assert not list(database.data_dir.glob("*.tmp"))


def test_initialization_creates_empty_stores_without_overwriting_existing_data():
    database = DatabaseManager()
    database.write("users", [{"username": "existing"}])
    database.ensure_files()
    assert database.read("users", []) == [{"username": "existing"}]
    assert database.read("portfolios", None) == {}
    assert database.read("rates", None) == {"pairs": {}, "last_refresh": None}
    assert database.read("exchange_rates", None) == []


def test_user_matches_assignment_schema_and_can_change_password():
    user = User(1, "alice", password="1234")
    stored = user.to_dict()
    assert set(stored) == {"user_id", "username", "hashed_password", "salt", "registration_date"}
    assert user.get_user_info() == {key: stored[key] for key in ("user_id", "username", "registration_date")}
    assert user.verify_password("1234")
    user.change_password("5678")
    assert not user.verify_password("1234")
    assert User.from_dict(user.to_dict()).verify_password("5678")


def test_wallet_and_portfolio_public_interfaces():
    user = User(1, "alice", password="1234")
    portfolio = Portfolio(user.user_id, user=user)
    wallet = portfolio.add_currency("USD")
    wallet.deposit(10)
    assert portfolio.user is user
    assert portfolio.get_wallet("USD") is wallet
    assert portfolio.get_total_value() == Decimal("10")
    assert wallet.get_balance_info() == "USD: 10"
    portfolio.wallets.clear()
    assert portfolio.get_wallet("USD") is wallet
    with pytest.raises(ValidationError):
        wallet.balance = "-1"


def test_currency_polymorphic_display():
    assert get_currency("USD").get_display_info() == "[FIAT] USD — US Dollar (Issuing: United States)"
    assert "[CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP:" in get_currency("BTC").get_display_info()
