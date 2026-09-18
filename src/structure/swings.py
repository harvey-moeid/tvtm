"""
Swing detection — fractal 5-candle, PRD §8.1.

Swing High di index i jika:
  high[i] > high[i-2], high[i] > high[i-1], high[i] > high[i+1], high[i] > high[i+2]
Swing Low adalah kebalikannya.

`lookback` (default 2) dibuat configurable via strategy.json (swingLookback)
supaya fractal bisa diperlebar (mis. 3-candle tiap sisi) saat tuning.
"""

from __future__ import annotations

from typing import List

from src.models import Candle, SwingPoint


def detect_swings(candles: List[Candle], lookback: int = 2) -> List[SwingPoint]:
    swings: List[SwingPoint] = []
    n = len(candles)
    if n < (2 * lookback + 1):
        return swings

    for i in range(lookback, n - lookback):
        c = candles[i]
        window = candles[i - lookback: i + lookback + 1]

        is_high = all(c.high >= o.high for o in window) and any(
            c.high > o.high for o in window if o is not c
        )
        is_low = all(c.low <= o.low for o in window) and any(
            c.low < o.low for o in window if o is not c
        )

        if is_high:
            swings.append(SwingPoint(index=i, price=c.high, kind="high", candle_time=c.open_time))
        if is_low:
            swings.append(SwingPoint(index=i, price=c.low, kind="low", candle_time=c.open_time))

    return swings
