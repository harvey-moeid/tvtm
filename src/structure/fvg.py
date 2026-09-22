"""Fair Value Gap (FVG) detector - imbalance 3-candle."""
from __future__ import annotations
from typing import List
from src.models import Candle, FairValueGap

def detect_fvgs(candles: List[Candle], min_gap_pct: float = 0.0) -> List[FairValueGap]:
    gaps: List[FairValueGap] = []
    for i in range(len(candles) - 2):
        c0, c1, c2 = candles[i], candles[i + 1], candles[i + 2]
        if c2.low > c0.high:
            top, bottom = c2.low, c0.high
            gap_pct = (top - bottom) / c1.close * 100 if c1.close else 0.0
            if gap_pct >= min_gap_pct:
                gaps.append(FairValueGap("bullish", top, bottom, c1.open_time))
        elif c2.high < c0.low:
            top, bottom = c0.low, c2.high
            gap_pct = (top - bottom) / c1.close * 100 if c1.close else 0.0
            if gap_pct >= min_gap_pct:
                gaps.append(FairValueGap("bearish", top, bottom, c1.open_time))
    return gaps

def mark_mitigated(gaps: List[FairValueGap], candles_after: List[Candle]) -> List[FairValueGap]:
    """Mark an FVG only when a candle AFTER the three-candle formation touches it."""
    result: List[FairValueGap] = []
    for gap in gaps:
        formed_idx = next(
            (i for i, c in enumerate(candles_after) if c.open_time == gap.formed_at_candle_time),
            None,
        )
        # formed_at is the middle candle; index + 2 is the first candle that
        # can legitimately mitigate the completed three-candle gap.
        first_check_idx = formed_idx + 2 if formed_idx is not None else None
        touched = (
            first_check_idx is not None
            and any(gap.is_touched_by(c) for c in candles_after[first_check_idx + 1 :])
        )
        result.append(
            FairValueGap(
                direction=gap.direction,
                top=gap.top,
                bottom=gap.bottom,
                formed_at_candle_time=gap.formed_at_candle_time,
                mitigated=touched,
            )
        )
    return result

def latest_unmitigated(gaps: List[FairValueGap], direction: str) -> FairValueGap | None:
    candidates = [g for g in gaps if g.direction == direction and not g.mitigated]
    return max(candidates, key=lambda g: g.formed_at_candle_time) if candidates else None
