"""
BOS (Break of Structure) & CHoCH (Change of Character) — PRD §9.

BOS   : breakout searah trend berjalan (continuation)
CHoCH : breakout berlawanan trend berjalan (potensi reversal)

Logika:
- close candle terakhir menembus last_swing_high  -> breakout arah bullish
  - kalau trend sebelumnya UP   -> BOS_BULLISH (lanjutan)
  - kalau trend sebelumnya DOWN/RANGE -> CHOCH_BULLISH (perubahan karakter)
- close candle terakhir menembus last_swing_low   -> breakout arah bearish
  - kalau trend sebelumnya DOWN -> BOS_BEARISH (lanjutan)
  - kalau trend sebelumnya UP/RANGE -> CHOCH_BEARISH (perubahan karakter)

Catatan implementasi: nilai ambang breakout memakai `close` (bukan wick) agar
lebih tahan noise, sejalan dengan filter anti-noise di §13.
"""

from __future__ import annotations

from typing import List, Optional

from src.models import Candle, StructureEvent, StructureResult, StructureTrend, SwingPoint
from src.structure.market_structure import classify_structure


def detect_structure_event(
    candles: List[Candle],
    swings: List[SwingPoint],
    prior_trend: Optional[StructureTrend],
) -> StructureResult:
    if not candles:
        return StructureResult(trend=StructureTrend.RANGE, last_swing_high=None, last_swing_low=None)

    # swing yang dipakai sebagai acuan level harus TERBENTUK SEBELUM candle terakhir,
    # supaya tidak "membandingkan candle dengan dirinya sendiri".
    latest = candles[-1]
    reference_swings = [s for s in swings if s.candle_time < latest.open_time]
    structure = classify_structure(reference_swings)

    prior_trend = prior_trend or structure.trend

    event = StructureEvent.NONE
    event_level: Optional[float] = None
    event_candle_time: Optional[int] = None

    if structure.last_swing_high and latest.close > structure.last_swing_high.price:
        event = (
            StructureEvent.BOS_BULLISH
            if prior_trend == StructureTrend.UP
            else StructureEvent.CHOCH_BULLISH
        )
        event_level = structure.last_swing_high.price
        event_candle_time = latest.open_time
    elif structure.last_swing_low and latest.close < structure.last_swing_low.price:
        event = (
            StructureEvent.BOS_BEARISH
            if prior_trend == StructureTrend.DOWN
            else StructureEvent.CHOCH_BEARISH
        )
        event_level = structure.last_swing_low.price
        event_candle_time = latest.open_time

    structure.event = event
    structure.event_level = event_level
    structure.event_candle_time = event_candle_time
    # trend efektif setelah event: BOS/CHoCH bullish -> UP, bearish -> DOWN
    if event in (StructureEvent.BOS_BULLISH, StructureEvent.CHOCH_BULLISH):
        structure.trend = StructureTrend.UP
    elif event in (StructureEvent.BOS_BEARISH, StructureEvent.CHOCH_BEARISH):
        structure.trend = StructureTrend.DOWN

    return structure
