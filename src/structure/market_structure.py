"""
Market structure classification — PRD §8.2.

UP   : swing high & swing low terbaru sama-sama lebih tinggi dari sebelumnya (HH + HL)
DOWN : swing high & swing low terbaru sama-sama lebih rendah dari sebelumnya (LH + LL)
RANGE: selain kondisi di atas (mis. HH+LL, LH+HL, atau data swing belum cukup)
"""

from __future__ import annotations

from typing import List, Optional

from src.models import StructureResult, StructureTrend, SwingPoint


def classify_structure(swings: List[SwingPoint]) -> StructureResult:
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]

    last_high = highs[-1] if highs else None
    last_low = lows[-1] if lows else None
    prev_high = highs[-2] if len(highs) >= 2 else None
    prev_low = lows[-2] if len(lows) >= 2 else None

    if not (last_high and last_low and prev_high and prev_low):
        return StructureResult(
            trend=StructureTrend.RANGE,
            last_swing_high=last_high,
            last_swing_low=last_low,
            swings=swings,
        )

    higher_high = last_high.price > prev_high.price
    higher_low = last_low.price > prev_low.price
    lower_high = last_high.price < prev_high.price
    lower_low = last_low.price < prev_low.price

    if higher_high and higher_low:
        trend = StructureTrend.UP
    elif lower_high and lower_low:
        trend = StructureTrend.DOWN
    else:
        trend = StructureTrend.RANGE

    return StructureResult(
        trend=trend,
        last_swing_high=last_high,
        last_swing_low=last_low,
        swings=swings,
    )
