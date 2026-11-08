"""Argparse commands and an interactive shell."""

import argparse
import shlex
import sys
from decimal import Decimal

from prettytable import PrettyTable

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ValidationError, ValutaTradeError
from valutatrade_hub.core.usecases import TradingService
from valutatrade_hub.core.utils import format_amount
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


class CommandParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValidationError(f"Неверная команда: {message}")


def build_parser() -> CommandParser:
    parser = CommandParser(prog="valutatrade", description="Учебный симулятор торговли валютами")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=CommandParser)
    register = sub.add_parser("register", help="Зарегистрировать пользователя")
    register.add_argument("--username", required=True)
    register.add_argument("--password", required=True)
    login = sub.add_parser("login", help="Войти в текущей сессии")
    login.add_argument("--username", required=True)
    login.add_argument("--password", required=True)
    deposit = sub.add_parser("deposit", help="Пополнить виртуальный USD-кошелёк")
    deposit.add_argument("--amount", required=True)
    portfolio = sub.add_parser("show-portfolio", help="Показать портфель")
    portfolio.add_argument("--base", default="USD")
    for name in ("buy", "sell"):
        trade = sub.add_parser(name, help="Купить или продать валюту")
        trade.add_argument("--currency", required=True)
        trade.add_argument("--amount", required=True)
    rate = sub.add_parser("get-rate", help="Получить текущий курс")
    rate.add_argument("--from", dest="source", required=True)
    rate.add_argument("--to", dest="target", required=True)
    update = sub.add_parser("update-rates", help="Обновить курсы через API")
    update.add_argument("--source", choices=("coingecko", "exchangerate"))
    rates = sub.add_parser("show-rates", help="Показать сохранённые курсы")
    rates.add_argument("--currency")
    rates.add_argument("--top", type=int)
    rates.add_argument("--base", default="USD")
    sub.add_parser("logout", help="Завершить сеанс пользователя")
    sub.add_parser("exit", help="Выйти из интерактивного режима")
    return parser


class CLI:
    def __init__(self, service: TradingService | None = None, updater: RatesUpdater | None = None) -> None:
        self.service = service or TradingService()
        self.updater = updater or RatesUpdater()
        self.parser = build_parser()

    def execute(self, tokens: list[str]) -> str:
        if not tokens or tokens[0] == "help":
            return self.parser.format_help()
        args = self.parser.parse_args(tokens)
        command = args.command
        if command == "register":
            user = self.service.register(args.username, args.password)
            return f"Пользователь {user.username} зарегистрирован. Выполните login."
        if command == "login":
            user = self.service.login(args.username, args.password)
            return f"Вход выполнен: {user.username}."
        if command == "logout":
            self.service.logout()
            return "Вы вышли из системы."
        if command == "deposit":
            result = self.service.deposit(args.amount)
            return f"Пополнено {format_amount(result['amount'])} USD. Баланс: {format_amount(result['balance'])} USD."
        if command == "buy":
            result = self.service.buy(args.currency, args.amount)
            return (
                f"Куплено {format_amount(result['amount'])} {result['currency']} "
                f"за {format_amount(result['usd'])} USD (курс {format_amount(result['rate'])})."
            )
        if command == "sell":
            result = self.service.sell(args.currency, args.amount)
            return (
                f"Продано {format_amount(result['amount'])} {result['currency']} "
                f"за {format_amount(result['usd'])} USD (курс {format_amount(result['rate'])})."
            )
        if command == "get-rate":
            rate = self.service.rates.rate(args.source, args.target)
            return f"1 {get_currency(args.source).code} = {format_amount(rate)} {get_currency(args.target).code}"
        if command == "show-portfolio":
            result = self.service.portfolio(args.base)
            table = PrettyTable(["Валюта", "Баланс", f"Курс к {result['base']}", f"Стоимость, {result['base']}"])
            for code, entry in result["wallets"].items():
                table.add_row(
                    [code, format_amount(entry["balance"]), format_amount(entry["rate"]), format_amount(entry["value"])]
                )
            return f"{table}\nИтого: {format_amount(result['total'])} {result['base']}"
        if command == "update-rates":
            result = self.updater.run_update(args.source)
            currencies = ", ".join(sorted(result["updated"]))
            warning = "; ".join(result["errors"].values())
            return f"Обновлены курсы: {currencies}." + (f" Предупреждение: {warning}" if warning else "")
        if command == "show-rates":
            if args.top is not None and args.top <= 0:
                raise ValidationError("--top должен быть положительным целым числом.")
            base = get_currency(args.base).code
            filter_code = get_currency(args.currency).code if args.currency else None
            pairs = RatesStorage().read().get("pairs", {})
            if base == "USD":
                base_price = Decimal("1")
            else:
                base_entry = pairs.get(f"{base}_USD")
                if not base_entry:
                    raise ValidationError(f"Нет сохранённого курса {base}/USD.")
                base_price = Decimal(str(base_entry["rate"]))
            table = PrettyTable(["Пара", "Курс", "Источник", "Обновлено"])
            rows = []
            for pair, entry in pairs.items():
                code = pair.removesuffix("_USD")
                if filter_code and filter_code != code:
                    continue
                price = Decimal(str(entry["rate"])) / base_price
                rows.append((code, price, entry))
            for code, price, entry in sorted(rows, key=lambda row: row[1], reverse=True)[: args.top]:
                table.add_row([f"{code}/{base}", format_amount(price), entry["source"], entry["updated_at"]])
            return str(table)
        return "До свидания."


def run_repl(cli: CLI | None = None) -> None:
    cli = cli or CLI()
    print("ValutaTrade Hub. Введите help для списка команд, exit для выхода.")
    while True:
        try:
            line = input("valutatrade> ")
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания.")
            return
        try:
            tokens = shlex.split(line)
            if not tokens:
                continue
            if tokens[0] == "exit":
                print("До свидания.")
                return
            print(cli.execute(tokens))
        except (ValutaTradeError, ValueError) as exc:
            print(f"Ошибка: {exc}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        run_repl()
        return 0
    try:
        print(CLI().execute(argv))
        return 0
    except ValutaTradeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
