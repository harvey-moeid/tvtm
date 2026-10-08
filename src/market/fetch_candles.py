"""
Layer fetch dengan retry + isolasi kegagalan per PRD §20.
retry 1 -> retry 2 -> skip symbol/timeframe (tidak menghentikan market lain).
"""

from __future__ import annotations

import logging
import time

_INTERVAL_MS = {"5m": 300000, "15m": 900000}
from typing import List, Optional

from src.market.exchange_adapter import get_adapter
from src.models import Candle

log = logging.getLogger("fetch_candles")

MAX_RETRY = 2
RETRY_DELAY_SEC = 2


def fetch_closed_candles(
    exchange: str, exchange_symbol: str, timeframe: str, min_history: int
) -> Optional[List[Candle]]:
    """
    Ambil candle historis + filter hanya yang closed.
    Return None kalau gagal setelah retry (caller wajib skip, bukan crash).
    """
    adapter = get_adapter(exchange)
    # minta lebih banyak dari min_history karena candle terakhir kemungkinan belum closed
    limit = min(1500, min_history + 5)

    last_err = None
    for attempt in range(MAX_RETRY + 1):
        try:
            raw = adapter.fetch_klines(exchange_symbol, timeframe, limit)
            closed = [c for c in raw if c.is_closed]
            closed.sort(key=lambda c: c.open_time)
            if len(closed) < min_history:
                raise ValueError(f"Data candle kurang: {len(closed)}/{min_history}")
            interval = _INTERVAL_MS[timeframe]
            if int(time.time() * 1000) - closed[-1].close_time > interval * 3:
                raise ValueError(f"Candle {timeframe} stale: {closed[-1].candle_time_iso}")
            if any(b.open_time - a.open_time != interval for a, b in zip(closed[-5:-1], closed[-4:])):
                raise ValueError(f"Candle {timeframe} mengandung gap terbaru")
            return closed
        except Exception as e:  # noqa: BLE001 - sengaja luas, ini boundary I/O eksternal
            last_err = e
            log.warning(
                "Fetch gagal (attempt %d/%d) %s %s %s: %s",
                attempt + 1, MAX_RETRY + 1, exchange, exchange_symbol, timeframe, e,
            )
            if attempt < MAX_RETRY:
                time.sleep(RETRY_DELAY_SEC)

    log.error(
        "Fetch %s %s %s gagal permanen setelah %d percobaan: %s. Symbol/timeframe di-skip.",
        exchange, exchange_symbol, timeframe, MAX_RETRY + 1, last_err,
    )
    return None
