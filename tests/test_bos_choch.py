from __future__ import annotations

from src.models import StructureEvent, StructureTrend, SwingPoint
from src.structure.bos_choch import detect_structure_event
from tests.conftest import make_candle


def swing(price: float, kind: str, t: int) -> SwingPoint:
    return SwingPoint(index=0, price=price, kind=kind, candle_time=t)


def test_bos_bullish_when_close_breaks_swing_high_in_uptrend():
    swings = [
        swing(100, "low", 0), swing(110, "high", 1),
        swing(105, "low", 2), swing(112, "high", 3),
    ]
    latest = make_candle(10, 112, 116, 111, 115)  # close 115 > last swing high 112
    result = detect_structure_event([latest], swings, prior_trend=StructureTrend.UP)
    assert result.event == StructureEvent.BOS_BULLISH
    assert result.event_level == 112


def test_choch_bullish_when_close_breaks_swing_high_against_down_trend():
    swings = [
        swing(100, "low", 0), swing(110, "high", 1),
        swing(105, "low", 2), swing(112, "high", 3),
    ]
    latest = make_candle(10, 112, 116, 111, 115)
    result = detect_structure_event([latest], swings, prior_trend=StructureTrend.DOWN)
    assert result.event == StructureEvent.CHOCH_BULLISH


def test_bos_bearish_when_close_breaks_swing_low_in_downtrend():
    swings = [
        swing(115, "high", 0), swing(105, "low", 1),
        swing(110, "high", 2), swing(100, "low", 3),
    ]
    latest = make_candle(10, 100, 101, 96, 97)  # close 97 < last swing low 100
    result = detect_structure_event([latest], swings, prior_trend=StructureTrend.DOWN)
    assert result.event == StructureEvent.BOS_BEARISH


def test_no_event_when_close_does_not_break_level():
    swings = [swing(100, "low", 0), swing(110, "high", 1)]
    latest = make_candle(10, 105, 109, 104, 108)  # close 108 < 110
    result = detect_structure_event([latest], swings, prior_trend=StructureTrend.UP)
    assert result.event == StructureEvent.NONE


def test_break_buffer_filters_marginal_breakout():
    swings = [swing(100, "low", 0), swing(110, "high", 1)]
    marginal_close = 110 * 1.0002  # 0.02% di atas level -> marginal
    latest = make_candle(10, 109, marginal_close + 0.5, 108, marginal_close)

    no_buffer = detect_structure_event(
        [latest], swings, prior_trend=StructureTrend.UP, break_buffer_pct=0.0
    )
    with_buffer = detect_structure_event(
        [latest], swings, prior_trend=StructureTrend.UP, break_buffer_pct=0.1
    )
    assert no_buffer.event == StructureEvent.BOS_BULLISH  # perilaku lama: lolos
    assert with_buffer.event == StructureEvent.NONE  # upgrade: ditolak karena marginal


def test_break_buffer_still_allows_clear_breakout():
    swings = [swing(100, "low", 0), swing(110, "high", 1)]
    clear_close = 110 * 1.02  # 2% di atas level -> jelas menembus
    latest = make_candle(10, 109, clear_close + 1, 108, clear_close)
    result = detect_structure_event(
        [latest], swings, prior_trend=StructureTrend.UP, break_buffer_pct=0.1
    )
    assert result.event == StructureEvent.BOS_BULLISH


def test_min_confirmation_propagates_to_prior_trend_fallback():
    swings = [
        swing(100, "low", 0), swing(110, "high", 1),
        swing(105, "low", 2), swing(112, "high", 3),
    ]
    latest = make_candle(10, 112, 116, 111, 115)
    # prior_trend=None -> fallback pakai structure.trend hasil classify_structure
    # dengan min_confirmation yang diteruskan.
    result = detect_structure_event(
        [latest], swings, prior_trend=None, min_confirmation=1
    )
    assert result.event == StructureEvent.BOS_BULLISH


def test_empty_candles_returns_range_no_event():
    result = detect_structure_event([], [], prior_trend=None)
    assert result.trend == StructureTrend.RANGE
    assert result.event == StructureEvent.NONE
