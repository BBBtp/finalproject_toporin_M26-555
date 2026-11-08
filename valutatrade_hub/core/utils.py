"""Decimal validation and serialization helpers."""

from decimal import Decimal, InvalidOperation

from .exceptions import ValidationError

MAX_BALANCE = Decimal("999999999999.99999999")
MIN_CHANGE = Decimal("0.000000000000000000000001")
MIN_RATE = Decimal("0.000000000001")
MAX_RATE = Decimal("1000000000000")
AMOUNT_STEP = Decimal("0.00000001")


def positive_change(value: object) -> Decimal:
    """Validate a finite internal wallet change, including calculated prices."""
    if isinstance(value, bool):
        raise ValidationError("Сумма должна быть положительным конечным числом.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Сумма должна быть положительным конечным числом.") from exc
    if not amount.is_finite() or amount < MIN_CHANGE or amount > MAX_BALANCE:
        raise ValidationError("Сумма вне допустимого диапазона.")
    return amount


def parse_amount(value: object) -> Decimal:
    """Validate a user-entered positive amount with at most eight decimals."""
    amount = positive_change(value)
    try:
        exact = amount.quantize(AMOUNT_STEP)
    except InvalidOperation as exc:
        raise ValidationError("Сумма должна иметь не более 8 знаков после запятой.") from exc
    if amount < AMOUNT_STEP or amount != exact:
        raise ValidationError("Сумма должна иметь не более 8 знаков после запятой.")
    return amount


def format_amount(value: Decimal) -> str:
    """Render a Decimal without an exponent or trailing decimal zeroes."""
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
