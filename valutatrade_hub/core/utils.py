"""Decimal validation and serialization helpers."""

from decimal import Decimal, InvalidOperation

from .exceptions import ValidationError


def parse_amount(value: object) -> Decimal:
    """Return a finite positive decimal; reject booleans and non-numbers."""
    if isinstance(value, bool):
        raise ValidationError("Сумма должна быть положительным конечным числом.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Сумма должна быть положительным конечным числом.") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValidationError("Сумма должна быть положительным конечным числом.")
    return amount


def format_amount(value: Decimal) -> str:
    """Render a Decimal without an exponent or trailing decimal zeroes."""
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
