"""
Average True Range (ATR) - Wilder smoothing.

Dipakai sebagai ukuran volatilitas untuk dua hal di upgrade strategi ini:
1. Toleransi zona yang ADAPTIF (src/strategy/zones.py) - menggantikan
   zoneTolerancePct statis yang gampang basi ketika rezim volatilitas berubah.
2. Buffer stop-loss berbasis risiko riil (src/strategy/risk.py) - supaya SL
   tidak ditempatkan persis di garis swing (gampang kena stop-hunt/noise wick)
   tapi juga tidak arbitrer.
"""

from __future__ import annotations

from typing import List, Optional

from src.models import Candle


def true_range(curr: Candle, prev: Candle) -> float:
    return max(
        curr.high - curr.low,
        abs(curr.high - prev.close),
        abs(curr.low - prev.close),
    )


def compute_atr(candles: List[Candle], period: int = 14) -> Optional[float]:
    """
    ATR Wilder's smoothing standar:
      ATR[0]  = rata-rata TR dari `period` TR pertama
      ATR[i]  = (ATR[i-1] * (period - 1) + TR[i]) / period

    Return None kalau candle historis tidak cukup (butuh minimal period+1 candle)
    supaya caller bisa memutuskan fallback-nya sendiri (mis. skip risk management,
    atau pakai toleransi zona statis) daripada diam-diam mengembalikan 0.
    """
    if period <= 0:
        raise ValueError("period ATR harus > 0")
    if len(candles) < period + 1:
        return None

    trs = [true_range(candles[i], candles[i - 1]) for i in range(1, len(candles))]
    if len(trs) < period:
        return None

    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr
