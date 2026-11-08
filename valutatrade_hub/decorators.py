"""Audit trading actions without changing their error semantics."""

import logging
from collections.abc import Callable
from functools import wraps


def log_action(function: Callable) -> Callable:
    @wraps(function)
    def wrapper(self, *args, **kwargs):
        logger = logging.getLogger("valutatrade_hub")
        user = getattr(self, "current_user", None)
        user_id = user.id if user else None
        currency = kwargs.get("currency", args[0] if args else None)
        amount = kwargs.get("amount", args[1] if len(args) > 1 else None)
        try:
            result = function(self, *args, **kwargs)
        except Exception as exc:
            logger.warning(
                "action=%s user_id=%s currency=%s amount=%s status=error error=%s",
                function.__name__,
                user_id,
                currency,
                amount,
                exc,
            )
            raise
        logger.info("action=%s user_id=%s status=ok details=%s", function.__name__, user_id, result)
        return result

    return wrapper
