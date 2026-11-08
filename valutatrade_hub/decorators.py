"""Audit trading actions without changing their error semantics."""

import logging
from collections.abc import Callable
from functools import wraps


def log_action(function: Callable) -> Callable:
    @wraps(function)
    def wrapper(self, *args, **kwargs):
        logger = logging.getLogger("valutatrade_hub")
        user = getattr(self, "current_user", None)
        context = {"action": function.__name__, "user_id": user.id if user else None, "args": args, "kwargs": kwargs}
        try:
            result = function(self, *args, **kwargs)
        except Exception as exc:
            logger.warning("action=%s user_id=%s status=error error=%s", context["action"], context["user_id"], exc)
            raise
        logger.info("action=%s user_id=%s status=ok details=%s", context["action"], context["user_id"], result)
        return result

    return wrapper
