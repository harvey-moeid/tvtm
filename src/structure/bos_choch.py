"""
BOS (Break of Structure) & CHoCH (Change of Character) - PRD 9, + upgrade
structure_break_buffer_pct.

BOS   : breakout searah trend berjalan (continuation)
CHoCH : breakout berlawanan trend berjalan (potensi reversal)

Logika dasar (tidak berubah dari versi awal):
- close candle terakhir menembus last_swing_high -> breakout arah bullish
  (BOS kalau prior trend UP, CHOCH kalau bukan)
- close candle terakhir menembus last_swing_low  -> breakout arah bearish
  (BOS kalau prior trend DOWN, CHOCH kalau bukan)
- ambang breakout memakai `close` (bukan wick) agar lebih tahan noise.

UPGRADE: `break_buffer_pct` (default 0.0 = identik perilaku lama, breakout
sekecil apapun tetap valid). Kalau > 0, breakout hanya dianggap valid jika
`close` menembus level swing acuan LEBIH JAUH dari buffer (persentase dari
harga level itu sendiri), bukan cuma marginal (mis. close cuma 0,001% di
atas level lalu balik lagi). Ini menyaring BOS/CHoCH palsu yang terbentuk
dari noise close yang cuma "numpang lewat" tipis di atas/bawah level swing,
salah satu penyebab whipsaw paling umum di strategi structure-break.
"""

from __future__ import annotations

from typing import List, Optional

from src.models import Candle, StructureEvent, StructureResult, StructureTrend, SwingPoint
from src.structure.market_structure import classify_structure


def detect_structure_event(
    candles: List[Candle],
    swings: List[SwingPoint],
    prior_trend: Optional[StructureTrend],
    min_confirmation: int = 1,
    break_buffer_pct: float = 0.0,
) -> StructureResult:
    if not candles:
        return StructureResult(trend=StructureTrend.RANGE, last_swing_high=None, last_swing_low=None)

    # swing acuan level harus TERBENTUK SEBELUM candle terakhir, supaya tidak
    # "membandingkan candle dengan dirinya sendiri".
    latest = candles[-1]
    reference_swings = [s for s in swings if s.candle_time < latest.open_time]
    structure = classify_structure(reference_swings, min_confirmation=min_confirmation)

    prior_trend = prior_trend or structure.trend

    event = StructureEvent.NONE
    event_level: Optional[float] = None
    event_candle_time: Optional[int] = None

    if structure.last_swing_high is not None:
        bullish_threshold = structure.last_swing_high.price * (1 + break_buffer_pct / 100)
        if latest.close > bullish_threshold:
            event = (
                StructureEvent.BOS_BULLISH
                if prior_trend == StructureTrend.UP
                else StructureEvent.CHOCH_BULLISH
            )
            event_level = structure.last_swing_high.price
            event_candle_time = latest.open_time

    if event == StructureEvent.NONE and structure.last_swing_low is not None:
        bearish_threshold = structure.last_swing_low.price * (1 - break_buffer_pct / 100)
        if latest.close < bearish_threshold:
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
    if event in (StructureEvent.BOS_BULLISH, StructureEvent.CHOCH_BULLISH):
        structure.trend = StructureTrend.UP
    elif event in (StructureEvent.BOS_BEARISH, StructureEvent.CHOCH_BEARISH):
        structure.trend = StructureTrend.DOWN

    return structure
