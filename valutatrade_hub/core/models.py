"""Users, wallets and portfolios."""

from dataclasses import dataclass, field
from decimal import Decimal, localcontext

from .currencies import get_currency
from .exceptions import InsufficientFundsError, ValidationError
from .utils import MAX_BALANCE, format_amount, positive_change


@dataclass
class User:
    id: str
    username: str
    password_hash: str
    salt: str

    def to_dict(self) -> dict[str, str]:
        return vars(self).copy()


@dataclass
class Wallet:
    currency_code: str
    balance: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        self.currency_code = get_currency(self.currency_code).code
        self.balance = Decimal(str(self.balance))
        if not self.balance.is_finite() or self.balance < 0 or self.balance > MAX_BALANCE:
            raise ValidationError("Баланс кошелька вне допустимого диапазона.")

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
                f"нужно {format_amount(value)} {self.currency_code}."
            )
        with localcontext() as context:
            context.prec = 80
            self.balance -= value

    def to_dict(self) -> dict[str, str]:
        return {"currency_code": self.currency_code, "balance": str(self.balance)}


@dataclass
class Portfolio:
    user_id: str
    wallets: dict[str, Wallet] = field(default_factory=dict)

    def wallet(self, code: str) -> Wallet:
        normalized = get_currency(code).code
        if normalized not in self.wallets:
            self.wallets[normalized] = Wallet(normalized)
        return self.wallets[normalized]

    def to_dict(self) -> dict[str, object]:
        return {"user_id": self.user_id, "wallets": {code: wallet.to_dict() for code, wallet in self.wallets.items()}}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Portfolio":
        wallets = {code: Wallet(code, entry["balance"]) for code, entry in data.get("wallets", {}).items()}
        return cls(user_id=data["user_id"], wallets=wallets)
