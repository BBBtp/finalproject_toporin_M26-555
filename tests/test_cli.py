"""User-visible trading scenarios."""

from decimal import Decimal

import pytest

from valutatrade_hub.cli.interface import CLI, run_repl
from valutatrade_hub.core.exceptions import AuthenticationError, InsufficientFundsError, StorageError, ValidationError
from valutatrade_hub.core.usecases import TradingService
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.storage import RatesStorage


def _logged_in_service():
    service = TradingService()
    service.register("toporin", "secret123")
    service.login("toporin", "secret123")
    return service


def test_deposit_buy_sell_and_portfolio():
    service = _logged_in_service()
    RatesStorage().save({"EUR": Decimal("1.25")}, "fixture")
    service.deposit("100")
    service.buy("EUR", "20")
    portfolio = service.portfolio()
    assert portfolio["wallets"]["USD"]["balance"] == Decimal("75")
    assert portfolio["wallets"]["EUR"]["balance"] == Decimal("20")
    assert portfolio["total"] == Decimal("100")
    service.sell("EUR", "5")
    assert service.portfolio()["wallets"]["USD"]["balance"] == Decimal("81.25")


def test_insufficient_balance_leaves_portfolio_intact():
    service = _logged_in_service()
    RatesStorage().save({"EUR": Decimal("1.25")}, "fixture")
    service.deposit("10")
    with pytest.raises(InsufficientFundsError):
        service.buy("EUR", "20")
    assert service.portfolio()["wallets"]["USD"]["balance"] == Decimal("10")
    with pytest.raises(InsufficientFundsError):
        service.sell("EUR", "1")
    assert service.portfolio()["wallets"]["USD"]["balance"] == Decimal("10")


def test_authentication_and_duplicate_name():
    service = TradingService()
    service.register("toporin", "secret123")
    with pytest.raises(ValidationError, match="уже зарегистрирован"):
        service.register("TOPORIN", "secret123")
    with pytest.raises(AuthenticationError):
        service.login("toporin", "wrong123")
    with pytest.raises(AuthenticationError):
        service.deposit("10")


def test_failed_login_clears_existing_session():
    service = _logged_in_service()
    with pytest.raises(AuthenticationError):
        service.login("toporin", "wrong123")
    with pytest.raises(AuthenticationError):
        service.deposit("10")


def test_registration_recovers_if_user_write_fails(monkeypatch):
    database = DatabaseManager()
    original_write = database.write

    def fail_user_write(name, payload):
        if name == "users":
            raise StorageError("simulated write failure")
        return original_write(name, payload)

    monkeypatch.setattr(database, "write", fail_user_write)
    with pytest.raises(StorageError):
        TradingService(database=database).register("toporin", "secret123")
    assert database.read("users", []) == []
    assert database.read("portfolios", {}) == {}
    monkeypatch.setattr(database, "write", original_write)
    assert TradingService(database=database).register("toporin", "secret123").username == "toporin"


def test_cli_deposit_command_and_errors():
    cli = CLI()
    cli.execute(["register", "--username", "toporin", "--password", "secret123"])
    cli.execute(["login", "--username", "toporin", "--password", "secret123"])
    assert cli.execute(["deposit", "--amount", "15.5"]) == "Пополнено 15.5 USD. Баланс: 15.5 USD."
    with pytest.raises(ValidationError):
        cli.execute(["deposit", "--amount", "NaN"])


def test_subcommand_help_keeps_interactive_session_open(monkeypatch, capsys):
    commands = iter(["buy --help", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(commands))
    run_repl(CLI())
    output = capsys.readouterr().out
    assert "--currency" in output
    assert "До свидания." in output
