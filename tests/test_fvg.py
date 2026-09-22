from __future__ import annotations
from src.models import FairValueGap
from src.structure.fvg import detect_fvgs, latest_unmitigated, mark_mitigated
from tests.conftest import make_candle

def test_bullish_fvg_detected():
    c0=make_candle(0,100,101,99,100.5); c1=make_candle(1,100.5,110,100,109); c2=make_candle(2,109,112,103,111)
    g=detect_fvgs([c0,c1,c2])[0]
    assert g.direction=="bullish" and g.bottom==101 and g.top==103 and g.formed_at_candle_time==c1.open_time

def test_bearish_fvg_detected():
    c0=make_candle(0,100,101,99,99.5); c1=make_candle(1,99.5,99,90,91); c2=make_candle(2,91,92,88,89)
    g=detect_fvgs([c0,c1,c2])[0]
    assert g.direction=="bearish" and g.top==99 and g.bottom==92

def test_no_gap_when_ranges_overlap():
    c0=make_candle(0,100,101,99,100); c1=make_candle(1,100,102,98,101); c2=make_candle(2,101,101.5,99.5,100.5)
    assert detect_fvgs([c0,c1,c2])==[]

def test_min_gap_pct_filters_small_gap():
    c0=make_candle(0,100,100.1,99,100); c1=make_candle(1,100,100.2,99.9,100.15); c2=make_candle(2,100.15,100.3,100.11,100.2)
    assert len(detect_fvgs([c0,c1,c2],0.0))==1 and detect_fvgs([c0,c1,c2],1.0)==[]

def test_formation_candle_does_not_mitigate_own_fvg():
    c0=make_candle(0,100,101,99,100.5); c1=make_candle(1,100.5,110,100,109); c2=make_candle(2,109,112,103,111)
    g=mark_mitigated(detect_fvgs([c0,c1,c2]),[c0,c1,c2])[0]
    assert g.mitigated is False

def test_later_candle_mitigates_fvg():
    c0=make_candle(0,100,101,99,100.5); c1=make_candle(1,100.5,110,100,109); c2=make_candle(2,109,112,103,111)
    touch=make_candle(3,111,111,102,102)
    assert mark_mitigated(detect_fvgs([c0,c1,c2]),[c0,c1,c2,touch])[0].mitigated is True

def test_latest_unmitigated_picks_most_recent_matching_direction():
    g1=FairValueGap("bullish",105,100,1000); g2=FairValueGap("bullish",115,110,2000); g3=FairValueGap("bearish",95,90,3000)
    assert latest_unmitigated([g1,g2,g3],"bullish") is g2

def test_latest_unmitigated_returns_none_when_no_match():
    assert latest_unmitigated([FairValueGap("bearish",95,90,1000)],"bullish") is None
