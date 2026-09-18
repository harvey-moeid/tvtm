"""
Adapter exchange/provider market data.
Memisahkan simbol internal (BTCUSDT, GOLDUSDT) dari simbol exchange aktual
(BTCUSDT futures, PAXGUSDT spot) sesuai PRD §1 & §7.

Setiap adapter wajib:
- return list[Candle] terurut ascending berdasarkan open_time
- HANYA mengembalikan candle yang sudah closed/final (PRD §5)
- retry ringan di level fetch_candles.py, bukan di sini
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import List

import requests

from src.models import Candle

BINANCE_FUTURES_BASE = "https://fapi.binance.com"
BINANCE_SPOT_BASE = "https://api.binance.com"

_INTERVAL_MS = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
}


class ExchangeAdapter(ABC):
    name: str

    @abstractmethod
    def fetch_klines(self, exchange_symbol: str, timeframe: str, limit: int) -> List[Candle]:
        raise NotImplementedError


class BinanceFuturesAdapter(ExchangeAdapter):
    """USDT-M Futures public klines (dipakai untuk BTCUSDT)."""

    name = "binance_futures"

    def fetch_klines(self, exchange_symbol: str, timeframe: str, limit: int) -> List[Candle]:
        url = f"{BINANCE_FUTURES_BASE}/fapi/v1/klines"
        return _fetch_binance_style(url, exchange_symbol, timeframe, limit)


class BinanceSpotAdapter(ExchangeAdapter):
    """Spot public klines (dipakai untuk PAXGUSDT sebagai proxy GOLDUSDT)."""

    name = "binance_spot"

    def fetch_klines(self, exchange_symbol: str, timeframe: str, limit: int) -> List[Candle]:
        url = f"{BINANCE_SPOT_BASE}/api/v3/klines"
        return _fetch_binance_style(url, exchange_symbol, timeframe, limit)


def _fetch_binance_style(url: str, symbol: str, timeframe: str, limit: int) -> List[Candle]:
    params = {"symbol": symbol, "interval": timeframe, "limit": limit}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    raw = resp.json()

    now_ms = int(time.time() * 1000)
    interval_ms = _INTERVAL_MS.get(timeframe, 0)

    candles: List[Candle] = []
    for row in raw:
        open_time, o, h, l, c, v, close_time = (
            row[0], row[1], row[2], row[3], row[4], row[5], row[6]
        )
        # Candle dianggap closed hanya jika close_time sudah lewat DAN
        # sudah melewati open_time + interval penuh (double-check terhadap jam server).
        is_closed = close_time < now_ms and (open_time + interval_ms) <= now_ms
        candles.append(
            Candle(
                open_time=int(open_time),
                close_time=int(close_time),
                open=float(o),
                high=float(h),
                low=float(l),
                close=float(c),
                volume=float(v),
                is_closed=is_closed,
            )
        )
    return candles


ADAPTERS = {
    "binance_futures": BinanceFuturesAdapter(),
    "binance_spot": BinanceSpotAdapter(),
}


def get_adapter(name: str) -> ExchangeAdapter:
    if name not in ADAPTERS:
        raise ValueError(f"Exchange adapter tidak dikenal: {name}")
    return ADAPTERS[name]
