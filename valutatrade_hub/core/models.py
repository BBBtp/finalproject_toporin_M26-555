"""Users, wallets and portfolios."""

import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, localcontext

from .currencies import get_currency
from .exceptions import InsufficientFundsError, ValidationError
from .utils import MAX_BALANCE, format_amount, positive_change


class User:
    """A registered user with private identity and password state."""

    def __init__(
        self,
        user_id: int,
        username: str,
        password: str | None = None,
        hashed_password: str | None = None,
        salt: str | None = None,
        registration_date: datetime | str | None = None,
    ) -> None:
        if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id < 1:
            raise ValidationError("Идентификатор пользователя должен быть положительным целым числом.")
        self._user_id = user_id
        self.username = username
        self._salt = salt or secrets.token_hex(16)
        if isinstance(registration_date, str):
            registration_date = datetime.fromisoformat(registration_date)
        self._registration_date = registration_date or datetime.now(UTC)
        if password is not None:
            self.change_password(password)
        elif hashed_password is not None:
            self._hashed_password = hashed_password
        else:
            raise ValidationError("Не задан пароль пользователя.")

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def id(self) -> int:
        """Compatibility alias for audit logging and session references."""
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("Имя пользователя не может быть пустым.")
        self._username = value.strip()

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def change_password(self, new_password: str) -> None:
        """Replace the stored password digest with salted SHA-256."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValidationError("Пароль должен быть не короче 4 символов.")
        self._salt = secrets.token_hex(16)
        self._hashed_password = hashlib.sha256((new_password + self._salt).encode()).hexdigest()

    def verify_password(self, password: str) -> bool:
        digest = hashlib.sha256((password + self._salt).encode()).hexdigest()
        return hmac.compare_digest(digest, self._hashed_password)

    def get_user_info(self) -> dict[str, object]:
        """Return public fields only, without password material."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.get_user_info(), "hashed_password": self._hashed_password, "salt": self._salt}

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "User":
        return cls(**value)


class Wallet:
    """Balance for one supported currency."""

    def __init__(self, currency_code: str, balance: Decimal | int | float = Decimal("0")) -> None:
        self.currency_code = get_currency(currency_code).code
        self.balance = balance

    @property
    def balance(self) -> Decimal:
        return self._balance

    @balance.setter
    def balance(self, value: Decimal | int | float) -> None:
        if isinstance(value, bool) or not isinstance(value, (Decimal, int, float)):
            raise ValidationError("Баланс должен быть числом.")
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > MAX_BALANCE:
            raise ValidationError("Баланс кошелька вне допустимого диапазона.")
        self._balance = amount

    def deposit(self, amount: object) -> None:
        value = positive_change(amount)
        with localcontext() as context:
            context.prec = 80
            new_balance = self.balance + value
        if new_balance > MAX_BALANCE:
            raise ValidationError("Баланс кошелька превысит допустимый предел.")
        if new_balance <= self.balance:
            raise ValidationError("Сумма слишком мала для изменения баланса.")
        self.balance = new_balance

    def withdraw(self, amount: object) -> None:
        value = positive_change(amount)
        if self.balance < value:
            raise InsufficientFundsError(
                f"Недостаточно средств: доступно {format_amount(self.balance)} {self.currency_code}, "
                f"требуется {format_amount(value)} {self.currency_code}."
            )
        with localcontext() as context:
            context.prec = 80
            self.balance -= value

    def to_dict(self) -> dict[str, str]:
        return {"currency_code": self.currency_code, "balance": str(self.balance)}

    def get_balance_info(self) -> str:
        return f"{self.currency_code}: {format_amount(self.balance)}"


class Portfolio:
    """Wallet collection owned by one user."""

    def __init__(self, user_id: int, wallets: dict[str, Wallet] | None = None, user: User | None = None) -> None:
        self._user_id = user_id
        self._user = user
        self._wallets = dict(wallets or {})

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def user(self) -> User | None:
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> Wallet:
        code = get_currency(currency_code).code
        if code not in self._wallets:
            self._wallets[code] = Wallet(code)
        return self._wallets[code]

    def get_wallet(self, currency_code: str) -> Wallet | None:
        return self._wallets.get(get_currency(currency_code).code)

    def wallet(self, code: str) -> Wallet:
        """Get or create a wallet for trading."""
        return self.add_currency(code)

    def get_total_value(
        self, base_currency: str = "USD", rate_provider: Callable[[str, str], Decimal] | None = None
    ) -> Decimal:
        """Value the portfolio using supplied rates or a USD-only identity."""
        base = get_currency(base_currency).code
        total = Decimal("0")
        for code, wallet in self._wallets.items():
            if wallet.balance == 0:
                continue
            if rate_provider is None and code != base:
                raise ValidationError("Для оценки портфеля нужен источник курсов.")
            rate = rate_provider(code, base) if rate_provider is not None else Decimal("1")
            total += wallet.balance * rate
        return total

    def to_dict(self) -> dict[str, object]:
        return {"user_id": self.user_id, "wallets": {code: wallet.to_dict() for code, wallet in self._wallets.items()}}

    @classmethod
    def from_dict(cls, data: dict[str, object], user: User | None = None) -> "Portfolio":
        wallets = {
            code: Wallet(code, Decimal(str(entry["balance"]))) for code, entry in data.get("wallets", {}).items()
        }
        return cls(user_id=data["user_id"], wallets=wallets, user=user)
