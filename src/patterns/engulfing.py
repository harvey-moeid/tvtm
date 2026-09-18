"""
Engulfing detection — PRD §12.3 & §12.4, plus anti-noise filter §13.

Bullish engulfing:
  candle sebelumnya bearish
  candle sekarang bullish
  body candle sekarang menelan penuh body candle sebelumnya
    (open_now <= close_prev AND close_now >= open_prev)

Bearish engulfing: mirror.
"""

from __future__ import annotations

from src.models import Candle, PatternResult, PatternType


def detect_bullish_engulfing(
    prev: Candle, curr: Candle, min_body_range_ratio: float
) -> PatternResult:
    ratio = curr.body / curr.range
    is_valid = (
        prev.is_bearish
        and curr.is_bullish
        and curr.open <= prev.close
        and curr.close >= prev.open
        and ratio >= min_body_range_ratio
    )
    return PatternResult(PatternType.BULLISH_ENGULFING, is_valid, ratio)


def detect_bearish_engulfing(
    prev: Candle, curr: Candle, min_body_range_ratio: float
) -> PatternResult:
    ratio = curr.body / curr.range
    is_valid = (
        prev.is_bullish
        and curr.is_bearish
        and curr.open >= prev.close
        and curr.close <= prev.open
        and ratio >= min_body_range_ratio
    )
    return PatternResult(PatternType.BEARISH_ENGULFING, is_valid, ratio)
