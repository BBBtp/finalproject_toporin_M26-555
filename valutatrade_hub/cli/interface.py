"""Argparse commands and an interactive shell."""

import argparse
import shlex
import sys
from decimal import Decimal

from prettytable import PrettyTable

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, RateUnavailableError, ValidationError, ValutaTradeError
from valutatrade_hub.core.usecases import TradingService
from valutatrade_hub.core.utils import format_amount
from valutatrade_hub.parser_service.config import CRYPTO_CURRENCIES, FIAT_CURRENCIES
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
            return f"Пользователь {user.username!r} зарегистрирован (id={user.id}). Выполните login."
        if command == "login":
            user = self.service.login(args.username, args.password)
            return f"Вы вошли как {user.username!r}."
        if command == "logout":
            self.service.logout()
            return "Вы вышли из системы."
        if command == "deposit":
            result = self.service.deposit(args.amount)
            return f"Пополнено {format_amount(result['amount'])} USD. Баланс: {format_amount(result['balance'])} USD."
        if command == "buy":
            result = self.service.buy(args.currency, args.amount)
            return (
                f"Покупка выполнена: {format_amount(result['amount'])} {result['currency']} "
                f"по курсу {format_amount(result['rate'])} USD/{result['currency']}.\n"
                f"Баланс {result['currency']}: {format_amount(result['balance_before'])} → "
                f"{format_amount(result['balance_after'])}. Списано {format_amount(result['usd'])} USD."
            )
        if command == "sell":
            result = self.service.sell(args.currency, args.amount)
            return (
                f"Продажа выполнена: {format_amount(result['amount'])} {result['currency']} "
                f"по курсу {format_amount(result['rate'])} USD/{result['currency']}.\n"
                f"Баланс {result['currency']}: {format_amount(result['balance_before'])} → "
                f"{format_amount(result['balance_after'])}. Начислено {format_amount(result['usd'])} USD."
            )
        if command == "get-rate":
            source = get_currency(args.source).code
            target = get_currency(args.target).code
            try:
                quote = self.service.rates.quote(source, target)
            except RateUnavailableError:
                needed = {source, target} - {"USD"}
                if needed.issubset(CRYPTO_CURRENCIES):
                    provider = "coingecko"
                elif needed.issubset(FIAT_CURRENCIES):
                    provider = "exchangerate"
                else:
                    provider = None
                self.updater.run_update(provider)
                quote = self.service.rates.quote(source, target)
            reverse = Decimal("1") / quote["rate"]
            return (
                f"Курс {source}→{target}: {format_amount(quote['rate'])} "
                f"(обновлено: {quote['updated_at']})\n"
                f"Обратный курс {target}→{source}: {format_amount(reverse)}"
            )
        if command == "show-portfolio":
            result = self.service.portfolio(args.base)
            if not result["wallets"]:
                return f"Портфель пользователя {self.service.current_user.username!r} пуст."
            table = PrettyTable(["Валюта", "Баланс", f"Курс к {result['base']}", f"Стоимость, {result['base']}"])
            for code, entry in result["wallets"].items():
                table.add_row(
                    [code, format_amount(entry["balance"]), format_amount(entry["rate"]), format_amount(entry["value"])]
                )
            return (
                f"Портфель пользователя {self.service.current_user.username!r} (база: {result['base']}):\n"
                f"{table}\nИТОГО: {format_amount(result['total'])} {result['base']}"
            )
        if command == "update-rates":
            result = self.updater.run_update(args.source)
            warning = "; ".join(result["errors"].values())
            return (
                f"Обновление завершено. Курсов: {len(result['updated'])}. "
                f"Последнее обновление: {result['last_refresh']}." + (f" Предупреждение: {warning}" if warning else "")
            )
        if command == "show-rates":
            if args.top is not None and args.top <= 0:
                raise ValidationError("--top должен быть положительным целым числом.")
            base = get_currency(args.base).code
            filter_code = args.currency.strip().upper() if args.currency else None
            pairs = RatesStorage().read().get("pairs", {})
            if not pairs:
                return "Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные."
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
                if args.top is not None and code not in CRYPTO_CURRENCIES:
                    continue
                price = Decimal(str(entry["rate"])) / base_price
                rows.append((code, price, entry))
            if filter_code and not rows:
                return f"Курс для {filter_code!r} не найден в кеше."
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
            print(str(exc) if isinstance(exc, ApiRequestError) else f"Ошибка: {exc}")
        except SystemExit as exc:
            if exc.code != 0:
                print("Ошибка: не удалось показать справку.")


def main(argv: list[str] | None = None) -> int:
    from valutatrade_hub.logging_config import configure_logging

    configure_logging()
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        run_repl()
        return 0
    try:
        print(CLI().execute(argv))
        return 0
    except ValutaTradeError as exc:
        print(str(exc) if isinstance(exc, ApiRequestError) else f"Ошибка: {exc}", file=sys.stderr)
        return 1
