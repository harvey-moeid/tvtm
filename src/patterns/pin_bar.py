"""
Pin bar detection — PRD §12.1 & §12.2, plus anti-noise filter §13.

Catatan desain anti-noise untuk pin bar:
Pin bar secara definisi PASTI punya body kecil (body maksimal ~1/3 range,
karena wick >= 2x body dan body harus berada di sepertiga range). Karena itu
threshold anti-noise untuk pin bar TIDAK memakai `minEngulfingBodyRangeRatio`
(yang didesain untuk candle continuation/engulfing yang butuh body besar),
melainkan `minPinBarBodyRangeRatio` — nilai kecil yang cuma menyaring
doji murni (body mendekati nol), bukan menyaring pin bar itu sendiri.

Bullish pin bar:
  lower_wick >= wick_to_body_ratio * body
  body berada di 1/3 atas range candle
  close > open

Bearish pin bar: mirror (upper_wick, body di 1/3 bawah, close < open).
"""

from __future__ import annotations

from src.models import Candle, PatternResult, PatternType


def _body_top(c: Candle) -> float:
    return max(c.open, c.close)


def _body_bottom(c: Candle) -> float:
    return min(c.open, c.close)


def detect_bullish_pin_bar(
    c: Candle, wick_to_body_ratio: float, min_pin_bar_body_ratio: float
) -> PatternResult:
    ratio = c.body / c.range
    if c.body <= 0:
        return PatternResult(PatternType.NONE, False, ratio)

    body_in_upper_third = _body_bottom(c) >= c.low + (2 / 3) * c.range
    is_valid = (
        c.is_bullish
        and c.lower_wick >= wick_to_body_ratio * c.body
        and body_in_upper_third
        and ratio >= min_pin_bar_body_ratio
    )
    return PatternResult(PatternType.BULLISH_PIN_BAR, is_valid, ratio)


def detect_bearish_pin_bar(
    c: Candle, wick_to_body_ratio: float, min_pin_bar_body_ratio: float
) -> PatternResult:
    ratio = c.body / c.range
    if c.body <= 0:
        return PatternResult(PatternType.NONE, False, ratio)

    body_in_lower_third = _body_top(c) <= c.low + (1 / 3) * c.range
    is_valid = (
        c.is_bearish
        and c.upper_wick >= wick_to_body_ratio * c.body
        and body_in_lower_third
        and ratio >= min_pin_bar_body_ratio
    )
    return PatternResult(PatternType.BEARISH_PIN_BAR, is_valid, ratio)
