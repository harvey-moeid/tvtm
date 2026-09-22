from __future__ import annotations

from src.models import FairValueGap
from src.structure.fvg import detect_fvgs, latest_unmitigated, mark_mitigated
from tests.conftest import make_candle


def test_bullish_fvg_detected():
    c0 = make_candle(0, 100, 101, 99, 100.5)  # high=101
    c1 = make_candle(1, 100.5, 110, 100, 109)  # candle impulsif
    c2 = make_candle(2, 109, 112, 103, 111)  # low=103 > c0.high=101
    gaps = detect_fvgs([c0, c1, c2])
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.direction == "bullish"
    assert gap.bottom == 101
    assert gap.top == 103
    assert gap.formed_at_candle_time == c1.open_time


def test_bearish_fvg_detected():
    c0 = make_candle(0, 100, 101, 99, 99.5)  # low=99
    c1 = make_candle(1, 99.5, 99, 90, 91)  # candle impulsif turun
    c2 = make_candle(2, 91, 92, 88, 89)  # high=92 < c0.low=99
    gaps = detect_fvgs([c0, c1, c2])
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.direction == "bearish"
    assert gap.top == 99
    assert gap.bottom == 92


def test_no_gap_when_ranges_overlap():
    c0 = make_candle(0, 100, 101, 99, 100)
    c1 = make_candle(1, 100, 102, 98, 101)
    c2 = make_candle(2, 101, 101.5, 99.5, 100.5)  # overlap dengan c0
    assert detect_fvgs([c0, c1, c2]) == []


def test_min_gap_pct_filters_small_gap_but_not_no_filter():
    c0 = make_candle(0, 100, 100.1, 99, 100)
    c1 = make_candle(1, 100, 100.2, 99.9, 100.15)
    c2 = make_candle(2, 100.15, 100.3, 100.11, 100.2)  # gap kecil ~0.01%
    assert len(detect_fvgs([c0, c1, c2], min_gap_pct=0.0)) == 1
    assert detect_fvgs([c0, c1, c2], min_gap_pct=1.0) == []


def test_mark_mitigated_true_when_later_candle_touches_gap():
    c0 = make_candle(0, 100, 101, 99, 100.5)
    c1 = make_candle(1, 100.5, 110, 100, 109)
    c2 = make_candle(2, 109, 112, 103, 111)
    gaps = detect_fvgs([c0, c1, c2])
    touch = make_candle(3, 111, 111, 102, 102)  # low=102 masuk zona [101,103]
    result = mark_mitigated(gaps, [c0, c1, c2, touch])
    assert result[0].mitigated is True


def test_mark_mitigated_false_when_no_candle_touches():
    c0 = make_candle(0, 100, 101, 99, 100.5)
    c1 = make_candle(1, 100.5, 110, 100, 109)
    c2 = make_candle(2, 109, 112, 103, 111)
    gaps = detect_fvgs([c0, c1, c2])
    far = make_candle(3, 120, 125, 118, 122)
    result = mark_mitigated(gaps, [c0, c1, c2, far])
    assert result[0].mitigated is False


def test_latest_unmitigated_picks_most_recent_matching_direction():
    g1 = FairValueGap(direction="bullish", top=105, bottom=100, formed_at_candle_time=1000)
    g2 = FairValueGap(direction="bullish", top=115, bottom=110, formed_at_candle_time=2000)
    g3 = FairValueGap(direction="bearish", top=95, bottom=90, formed_at_candle_time=3000)
    assert latest_unmitigated([g1, g2, g3], "bullish") is g2


def test_latest_unmitigated_returns_none_when_no_match():
    g1 = FairValueGap(direction="bearish", top=95, bottom=90, formed_at_candle_time=1000)
    assert latest_unmitigated([g1], "bullish") is None
