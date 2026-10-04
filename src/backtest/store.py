"""In-memory cooldown store using the simulated candle clock."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class InMemorySignalStore:
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _rows: list = field(default_factory=list)

    def advance_to(self, ts: datetime) -> None:
        self.now = ts

    def record_notified(self, *, cooldown_key, symbol, timeframe, direction, created_at):
        self._rows.append({
            "cooldown_key": cooldown_key, "symbol": symbol,
            "timeframe": timeframe, "direction": direction, "created_at": created_at,
        })

    def has_notified_cooldown(self, key):
        return any(row["cooldown_key"] == key for row in self._rows)

    def was_notified_recently(self, symbol, timeframe, direction, minutes):
        cutoff = self.now - timedelta(minutes=minutes)
        return any(
            row["symbol"] == symbol and row["timeframe"] == timeframe
            and row["direction"] == direction and row["created_at"] >= cutoff
            for row in self._rows
        )
