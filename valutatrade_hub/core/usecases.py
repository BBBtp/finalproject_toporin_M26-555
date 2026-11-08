"""Rate lookup, authentication and virtual trading use cases."""

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.storage import RatesStorage

from .currencies import get_currency
from .exceptions import AuthenticationError, RateUnavailableError, ValidationError
from .models import Portfolio, User
from .utils import parse_amount


class RateService:
    def __init__(self, storage: RatesStorage | None = None, settings: SettingsLoader | None = None) -> None:
        self.storage = storage or RatesStorage()
        self.settings = settings or SettingsLoader()

    def _usd_price(self, code: str) -> Decimal:
        code = get_currency(code).code
        if code == "USD":
            return Decimal("1")
        entry = self.storage.read().get("pairs", {}).get(f"{code}_USD")
        if not entry:
            raise RateUnavailableError(f"Нет курса {code}/USD. Выполните update-rates.")
        try:
            updated = datetime.fromisoformat(entry["updated_at"])
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=UTC)
            rate = Decimal(str(entry["rate"]))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise RateUnavailableError(f"Курс {code}/USD повреждён. Выполните update-rates.") from exc
        age = (datetime.now(UTC) - updated).total_seconds()
        if age > self.settings.ttl_seconds or age < -60:
            raise RateUnavailableError(f"Курс {code}/USD устарел. Выполните update-rates.")
        if not rate.is_finite() or rate <= 0:
            raise RateUnavailableError(f"Курс {code}/USD повреждён. Выполните update-rates.")
        return rate

    def rate(self, from_code: str, to_code: str) -> Decimal:
        source = get_currency(from_code).code
        target = get_currency(to_code).code
        if source == target:
            return Decimal("1")
        return self._usd_price(source) / self._usd_price(target)


class TradingService:
    def __init__(self, database: DatabaseManager | None = None, rates: RateService | None = None) -> None:
        self.database = database or DatabaseManager()
        self.rates = rates or RateService()
        self.current_user: User | None = None

    @staticmethod
    def _password_hash(password: str, salt: str) -> str:
        return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

    def register(self, username: str, password: str) -> User:
        if not re.fullmatch(r"[A-Za-z0-9_]{3,32}", username):
            raise ValidationError("Имя пользователя: 3–32 латинских буквы, цифры или подчёркивания.")
        if len(password) < 8:
            raise ValidationError("Пароль должен содержать не менее 8 символов.")
        users = self.database.read("users", [])
        if any(item["username"].casefold() == username.casefold() for item in users):
            raise ValidationError(f"Пользователь {username!r} уже зарегистрирован.")
        salt = secrets.token_hex(16)
        user = User(str(uuid.uuid4()), username, self._password_hash(password, salt), salt)
        portfolios = self.database.read("portfolios", {})
        users.append(user.to_dict())
        portfolios[user.id] = Portfolio(user.id).to_dict()
        self.database.write("users", users)
        self.database.write("portfolios", portfolios)
        return user

    def login(self, username: str, password: str) -> User:
        users = self.database.read("users", [])
        for item in users:
            if item["username"].casefold() == username.casefold():
                candidate = self._password_hash(password, item["salt"])
                if hmac.compare_digest(candidate, item["password_hash"]):
                    self.current_user = User(**item)
                    return self.current_user
        raise AuthenticationError("Неверное имя пользователя или пароль.")

    def logout(self) -> None:
        self.current_user = None

    def _require_user(self) -> User:
        if self.current_user is None:
            raise AuthenticationError("Сначала выполните login.")
        return self.current_user

    def _portfolio(self) -> Portfolio:
        user = self._require_user()
        portfolios = self.database.read("portfolios", {})
        return Portfolio.from_dict(portfolios.get(user.id, {"user_id": user.id, "wallets": {}}))

    def _save_portfolio(self, portfolio: Portfolio) -> None:
        portfolios = self.database.read("portfolios", {})
        portfolios[portfolio.user_id] = portfolio.to_dict()
        self.database.write("portfolios", portfolios)

    def deposit(self, amount: object) -> dict[str, Decimal]:
        value = parse_amount(amount)
        portfolio = self._portfolio()
        portfolio.wallet("USD").deposit(value)
        self._save_portfolio(portfolio)
        return {"amount": value, "balance": portfolio.wallet("USD").balance}

    @log_action
    def buy(self, currency: str, amount: object) -> dict[str, Decimal | str]:
        value = parse_amount(amount)
        code = get_currency(currency).code
        if code == "USD":
            raise ValidationError("USD пополняется командой deposit.")
        self._require_user()
        rate = self.rates.rate(code, "USD")
        cost = value * rate
        portfolio = self._portfolio()
        portfolio.wallet("USD").withdraw(cost)
        portfolio.wallet(code).deposit(value)
        self._save_portfolio(portfolio)
        return {"currency": code, "amount": value, "rate": rate, "usd": cost}

    @log_action
    def sell(self, currency: str, amount: object) -> dict[str, Decimal | str]:
        value = parse_amount(amount)
        code = get_currency(currency).code
        if code == "USD":
            raise ValidationError("USD нельзя продать за USD.")
        self._require_user()
        rate = self.rates.rate(code, "USD")
        proceeds = value * rate
        portfolio = self._portfolio()
        portfolio.wallet(code).withdraw(value)
        portfolio.wallet("USD").deposit(proceeds)
        self._save_portfolio(portfolio)
        return {"currency": code, "amount": value, "rate": rate, "usd": proceeds}

    def portfolio(self, base: str = "USD") -> dict[str, object]:
        base = get_currency(base).code
        portfolio = self._portfolio()
        values: dict[str, dict[str, Decimal]] = {}
        total = Decimal("0")
        for code, wallet in sorted(portfolio.wallets.items()):
            if wallet.balance == 0:
                continue
            rate = self.rates.rate(code, base)
            worth = wallet.balance * rate
            values[code] = {"balance": wallet.balance, "rate": rate, "value": worth}
            total += worth
        return {"base": base, "wallets": values, "total": total}
