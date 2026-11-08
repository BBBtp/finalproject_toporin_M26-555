"""Audit trading actions without changing their error semantics."""

import logging
from collections.abc import Callable
from functools import wraps


def log_action(function: Callable | None = None, *, verbose: bool = False) -> Callable:
    """Audit a use case and re-raise its errors; verbose adds wallet changes."""

    def decorate(action: Callable) -> Callable:
        @wraps(action)
        def wrapper(self, *args, **kwargs):
            logger = logging.getLogger("valutatrade_hub")
            user = getattr(self, "current_user", None)
            user_id = user.id if user else None
            currency = kwargs.get("currency", args[0] if args else None)
            amount = kwargs.get("amount", args[1] if len(args) > 1 else None)
            try:
                result = action(self, *args, **kwargs)
            except Exception as exc:
                logger.warning(
                    "action=%s user_id=%s currency=%s amount=%s base=USD result=ERROR error_type=%s error_message=%s",
                    action.__name__.upper(),
                    user_id,
                    currency,
                    amount,
                    type(exc).__name__,
                    exc,
                )
                raise
            context = ""
            if verbose:
                context = f" balance_before={result['balance_before']} balance_after={result['balance_after']}"
            logger.info(
                "action=%s user_id=%s currency=%s amount=%s rate=%s base=USD result=OK%s",
                action.__name__.upper(),
                user_id,
                result["currency"],
                result["amount"],
                result["rate"],
                context,
            )
            return result

        return wrapper

    return decorate(function) if function is not None else decorate
