from __future__ import annotations
from typing import List
from src.models import Candle, FairValueGap

def detect_fvgs(candles: List[Candle], min_gap_pct: float = 0.0) -> List[FairValueGap]:
    gaps=[]
    for i in range(len(candles)-2):
        c0,c1,c2=candles[i],candles[i+1],candles[i+2]
        if c2.low>c0.high:
            top,bottom=c2.low,c0.high; pct=(top-bottom)/c1.close*100 if c1.close else 0
            if pct>=min_gap_pct: gaps.append(FairValueGap("bullish",top,bottom,c1.open_time))
        elif c2.high<c0.low:
            top,bottom=c0.low,c2.high; pct=(top-bottom)/c1.close*100 if c1.close else 0
            if pct>=min_gap_pct: gaps.append(FairValueGap("bearish",top,bottom,c1.open_time))
    return gaps

def mark_mitigated(gaps:List[FairValueGap],candles_after:List[Candle])->List[FairValueGap]:
    result=[]
    for gap in gaps:
        formed_idx=next((i for i,c in enumerate(candles_after) if c.open_time==gap.formed_at_candle_time),None)
        first_later_idx=formed_idx+2 if formed_idx is not None else len(candles_after)
        touched=any(gap.is_touched_by(c) for c in candles_after[first_later_idx:])
        result.append(FairValueGap(gap.direction,gap.top,gap.bottom,gap.formed_at_candle_time,touched))
    return result

def latest_unmitigated(gaps:List[FairValueGap],direction:str)->FairValueGap|None:
    candidates=[g for g in gaps if g.direction==direction and not g.mitigated]
    return max(candidates,key=lambda g:g.formed_at_candle_time) if candidates else None
