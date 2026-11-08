"""Rate lookup, authentication and virtual trading use cases."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.storage import RatesStorage

from .currencies import get_currency
from .exceptions import AuthenticationError, RateUnavailableError, ValidationError
from .models import Portfolio, User
from .utils import MAX_RATE, MIN_RATE, parse_amount


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
        if not rate.is_finite() or rate < MIN_RATE or rate > MAX_RATE:
            raise RateUnavailableError(f"Курс {code}/USD повреждён. Выполните update-rates.")
        return rate

    def rate(self, from_code: str, to_code: str) -> Decimal:
        source = get_currency(from_code).code
        target = get_currency(to_code).code
        if source == target:
            self._usd_price(source)
            return Decimal("1")
        return self._usd_price(source) / self._usd_price(target)

    def quote(self, from_code: str, to_code: str) -> dict[str, Decimal | str]:
        """Return a fresh cross-rate together with its oldest source timestamp."""
        rate = self.rate(from_code, to_code)
        pairs = self.storage.read().get("pairs", {})
        stamps = [
            pairs[f"{code}_USD"]["updated_at"]
            for code in {get_currency(from_code).code, get_currency(to_code).code}
            if code != "USD"
        ]
        return {"rate": rate, "updated_at": min(stamps) if stamps else datetime.now(UTC).isoformat()}


class TradingService:
    def __init__(self, database: DatabaseManager | None = None, rates: RateService | None = None) -> None:
        self.database = database or DatabaseManager()
        self.rates = rates or RateService()
        self.current_user: User | None = None

    def register(self, username: str, password: str) -> User:
        if not isinstance(username, str) or not username.strip():
            raise ValidationError("Имя пользователя не может быть пустым.")
        if not isinstance(password, str) or len(password) < 4:
            raise ValidationError("Пароль должен быть не короче 4 символов.")
        username = username.strip()
        users = self.database.read("users", [])
        if any(item["username"].casefold() == username.casefold() for item in users):
            raise ValidationError(f"Имя пользователя {username!r} уже занято.")
        next_id = max((item["user_id"] for item in users), default=0) + 1
        user = User(next_id, username, password=password)
        portfolios = self.database.read("portfolios", {})
        portfolios[str(user.id)] = Portfolio(user.id).to_dict()
        users.append(user.to_dict())
        self.database.write_accounts(users, portfolios)
        return user

    def login(self, username: str, password: str) -> User:
        self.current_user = None
        users = self.database.read("users", [])
        for item in users:
            if item["username"].casefold() == username.casefold():
                user = User.from_dict(item)
                if not user.verify_password(password):
                    raise AuthenticationError("Неверный пароль.")
                self.current_user = user
                return user
        raise AuthenticationError(f"Пользователь {username!r} не найден.")

    def logout(self) -> None:
        self.current_user = None

    def _require_user(self) -> User:
        if self.current_user is None:
            raise AuthenticationError("Сначала выполните login.")
        return self.current_user

    def _portfolio(self) -> Portfolio:
        user = self._require_user()
        portfolios = self.database.read("portfolios", {})
        return Portfolio.from_dict(portfolios.get(str(user.id), {"user_id": user.id, "wallets": {}}), user=user)

    def _save_portfolio(self, portfolio: Portfolio) -> None:
        portfolios = self.database.read("portfolios", {})
        portfolios[str(portfolio.user_id)] = portfolio.to_dict()
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
        before = portfolio.wallet(code).balance
        portfolio.wallet("USD").withdraw(cost)
        portfolio.wallet(code).deposit(value)
        self._save_portfolio(portfolio)
        return {
            "currency": code,
            "amount": value,
            "rate": rate,
            "usd": cost,
            "balance_before": before,
            "balance_after": portfolio.wallet(code).balance,
        }

    @log_action
    def sell(self, currency: str, amount: object) -> dict[str, Decimal | str]:
        value = parse_amount(amount)
        code = get_currency(currency).code
        if code == "USD":
            raise ValidationError("USD нельзя продать за USD.")
        self._require_user()
        portfolio = self._portfolio()
        wallet = portfolio.get_wallet(code)
        if wallet is None:
            raise ValidationError(f"У вас нет кошелька {code!r}. Он создаётся при первой покупке.")
        rate = self.rates.rate(code, "USD")
        proceeds = value * rate
        before = wallet.balance
        wallet.withdraw(value)
        portfolio.wallet("USD").deposit(proceeds)
        self._save_portfolio(portfolio)
        return {
            "currency": code,
            "amount": value,
            "rate": rate,
            "usd": proceeds,
            "balance_before": before,
            "balance_after": wallet.balance,
        }

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
