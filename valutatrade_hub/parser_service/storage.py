"""Cache and append-only history of provider rates."""

from datetime import UTC, datetime
from decimal import Decimal

from valutatrade_hub.infra.database import DatabaseManager


class RatesStorage:
    def __init__(self, database: DatabaseManager | None = None) -> None:
        self.database = database or DatabaseManager()

    def read(self) -> dict:
        return self.database.read("rates", {"pairs": {}, "last_refresh": None})

    def history(self) -> list[dict]:
        return self.database.read("exchange_rates", [])

    def save(self, rates: dict[str, Decimal], source: str, updated_at: str | None = None) -> dict:
        stamp = updated_at or datetime.now(UTC).isoformat()
        cache = self.read()
        pairs = cache.setdefault("pairs", {})
        history = self.history()
        for code, rate in rates.items():
            pair = f"{code}_USD"
            pairs[pair] = {"rate": str(rate), "updated_at": stamp, "source": source}
            history.append(
                {
                    "id": f"{pair}_{stamp}",
                    "from": code,
                    "to": "USD",
                    "rate": str(rate),
                    "updated_at": stamp,
                    "source": source,
                }
            )
        cache["last_refresh"] = stamp
        self.database.write("rates", cache)
        self.database.write("exchange_rates", history)
        return cache
