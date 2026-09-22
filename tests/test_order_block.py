from __future__ import annotations

from src.models import OrderBlock, StructureEvent
from src.structure.order_block import detect_order_block, mark_mitigated
from tests.conftest import make_candle


def test_bullish_order_block_finds_nearest_bearish_candle():
    candles = [
        make_candle(0, 100, 102, 99, 101),   # bullish
        make_candle(1, 101, 103, 100, 102),  # bullish
        make_candle(2, 102, 104, 101, 103),  # bullish
        make_candle(3, 103, 104, 100, 101),  # bearish - paling dekat ke event
        make_candle(4, 101, 110, 100, 109),  # candle event (displacement)
    ]
    ob = detect_order_block(candles, StructureEvent.BOS_BULLISH, candles[4].open_time, lookback=10)
    assert ob is not None
    assert ob.direction == "bullish"
    assert ob.top == candles[3].high
    assert ob.bottom == candles[3].low
    assert ob.formed_at_candle_time == candles[3].open_time


def test_bearish_order_block_finds_nearest_bullish_candle():
    candles = [
        make_candle(0, 103, 104, 101, 102),  # bearish
        make_candle(1, 102, 103, 100, 101),  # bearish
        make_candle(2, 101, 102, 99, 100),   # bearish
        make_candle(3, 100, 103, 99, 102),   # bullish - paling dekat ke event
        make_candle(4, 102, 103, 90, 91),    # candle event (displacement turun)
    ]
    ob = detect_order_block(candles, StructureEvent.BOS_BEARISH, candles[4].open_time, lookback=10)
    assert ob is not None
    assert ob.direction == "bearish"
    assert ob.formed_at_candle_time == candles[3].open_time


def test_returns_none_for_none_event():
    candles = [make_candle(0, 100, 101, 99, 100)]
    assert detect_order_block(candles, StructureEvent.NONE, candles[0].open_time) is None


def test_returns_none_when_event_candle_time_missing():
    candles = [make_candle(0, 100, 101, 99, 100)]
    assert detect_order_block(candles, StructureEvent.BOS_BULLISH, None) is None


def test_returns_none_when_event_candle_time_not_found():
    candles = [make_candle(0, 100, 101, 99, 100)]
    assert detect_order_block(candles, StructureEvent.BOS_BULLISH, 999_999_999_999) is None


def test_lookback_excludes_opposite_candle_outside_window():
    candles = [make_candle(0, 103, 104, 99, 100)]  # bearish, jauh di belakang
    for i in range(1, 6):
        candles.append(make_candle(i, 100 + i, 101 + i, 99 + i, 100.5 + i))  # bullish berturut
    candles.append(make_candle(6, 106, 115, 105, 114))  # candle event
    event_time = candles[6].open_time
    ob = detect_order_block(candles, StructureEvent.BOS_BULLISH, event_time, lookback=2)
    assert ob is None  # candle bearish di index 0 ada, tapi di luar jendela lookback=2


def test_mark_mitigated_flags_touch():
    ob = OrderBlock(
        direction="bullish", top=101, bottom=100, formed_at_candle_time=1000,
        structure_event=StructureEvent.BOS_BULLISH,
    )
    touch = make_candle(0, 105, 105, 100.5, 104)  # low=100.5 masuk zona [100,101]
    result = mark_mitigated(ob, [touch])
    assert result.mitigated is True


def test_mark_mitigated_none_when_ob_is_none():
    assert mark_mitigated(None, []) is None
