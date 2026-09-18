"""
M15 Bias Engine — PRD §10.

BULLISH : struktur M15 UP  (hasil BOS/CHoCH bullish menjadi trend UP)
BEARISH : struktur M15 DOWN
NEUTRAL : struktur M15 RANGE atau struktur belum cukup jelas
          -> M5 DILARANG membuat signal MTF ketika bias ini.
"""

from __future__ import annotations

from typing import List, Optional

from src.models import Bias, BiasResult, Candle, StructureTrend
from src.structure.bos_choch import detect_structure_event
from src.structure.swings import detect_swings


def compute_m15_bias(
    candles: List[Candle], swing_lookback: int, prior_trend: Optional[StructureTrend] = None
) -> BiasResult:
    swings = detect_swings(candles, lookback=swing_lookback)
    structure = detect_structure_event(candles, swings, prior_trend)

    if structure.trend == StructureTrend.UP:
        bias = Bias.BULLISH
    elif structure.trend == StructureTrend.DOWN:
        bias = Bias.BEARISH
    else:
        bias = Bias.NEUTRAL

    return BiasResult(bias=bias, structure=structure)
