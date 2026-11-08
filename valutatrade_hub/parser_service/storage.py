"""Cache and append-only history of provider rates."""

from datetime import UTC, datetime
from decimal import Decimal

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ValidationError
from valutatrade_hub.core.utils import MAX_RATE, MIN_RATE
from valutatrade_hub.infra.database import DatabaseManager

from .config import CRYPTO_ID_MAP


class RatesStorage:
    def __init__(self, database: DatabaseManager | None = None) -> None:
        self.database = database or DatabaseManager()

    def read(self) -> dict:
        return self.database.read("rates", {"pairs": {}, "last_refresh": None})

    def history(self) -> list[dict]:
        return self.database.read("exchange_rates", [])

    def save(self, rates: dict[str, Decimal], source: str, updated_at: str | None = None) -> dict:
        stamp = updated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        timestamp = datetime.fromisoformat(stamp)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        for pair, rate in rates.items():
            parts = pair.split("_", 1)
            if len(parts) != 2 or parts[1] != "USD" or get_currency(parts[0]).code != parts[0]:
                raise ValidationError(f"Некорректная пара валют: {pair}.")
            if not isinstance(rate, Decimal) or not rate.is_finite() or not MIN_RATE <= rate <= MAX_RATE:
                raise ValidationError(f"Некорректный курс: {pair}.")
        cache = self.read()
        pairs = cache.setdefault("pairs", {})
        history = self.history()
        names = {"coingecko": "CoinGecko", "exchangerate": "ExchangeRate-API"}
        source_name = names.get(source, source)
        seen_ids = {item["id"] for item in history}
        for pair, rate in rates.items():
            from_code, to_code = pair.split("_", 1)
            record_id = f"{pair}_{stamp}"
            if record_id not in seen_ids:
                history.append(
                    {
                        "id": record_id,
                        "from_currency": from_code,
                        "to_currency": to_code,
                        "rate": str(rate),
                        "timestamp": stamp,
                        "source": source_name,
                        "meta": {"raw_id": CRYPTO_ID_MAP[from_code]} if from_code in CRYPTO_ID_MAP else {},
                    }
                )
                seen_ids.add(record_id)
            current = pairs.get(pair)
            current_time = datetime.fromisoformat(current["updated_at"]) if current else None
            if current_time and current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=UTC)
            if current_time is None or timestamp > current_time:
                pairs[pair] = {"rate": str(rate), "updated_at": stamp, "source": source_name}
        last = cache.get("last_refresh")
        last_time = datetime.fromisoformat(last) if last else None
        if last_time and last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=UTC)
        if last_time is None or timestamp > last_time:
            cache["last_refresh"] = stamp
        self.database.write("rates", cache)
        self.database.write("exchange_rates", history)
        return cache
