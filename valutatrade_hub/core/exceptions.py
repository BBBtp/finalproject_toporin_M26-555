"""User-facing domain errors."""


class ValutaTradeError(Exception):
    """Base exception for expected application errors."""


class ValidationError(ValutaTradeError):
    """An input value violates a business rule."""


class AuthenticationError(ValutaTradeError):
    """Credentials or session are invalid."""


class InsufficientFundsError(ValutaTradeError):
    """The wallet cannot cover a withdrawal."""


class CurrencyNotFoundError(ValutaTradeError):
    """A currency code is not supported."""


class RateUnavailableError(ValutaTradeError):
    """No usable rate is in the local cache."""


class ApiRequestError(ValutaTradeError):
    """An upstream rate provider failed."""


class StorageError(ValutaTradeError):
    """Persistent data could not be read or written."""
