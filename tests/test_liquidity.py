from __future__ import annotations

from src.models import SwingPoint
from src.strategy.liquidity import detect_liquidity_sweep
from tests.conftest import make_candle


def test_bearish_sweep_detected_on_equal_highs():
    c0 = make_candle(0, 105, 110, 104, 109)
    c1 = make_candle(1, 109, 110.02, 108, 109.5)
    swings = [
        SwingPoint(index=0, price=110, kind="high", candle_time=c0.open_time),
        SwingPoint(index=1, price=110.02, kind="high", candle_time=c1.open_time),
    ]
    latest = make_candle(5, 109, 111, 108.5, 109.5)  # wick tembus, close balik di bawah
    sweep = detect_liquidity_sweep([c0, c1, latest], swings, equal_tolerance_pct=0.05)
    assert sweep is not None
    assert sweep.direction == "bearish"
    assert sweep.swept_level == 110.02


def test_bullish_sweep_detected_on_equal_lows():
    c0 = make_candle(0, 95, 96, 90, 91)
    c1 = make_candle(1, 91, 92, 89.98, 90.5)
    swings = [
        SwingPoint(index=0, price=90, kind="low", candle_time=c0.open_time),
        SwingPoint(index=1, price=89.98, kind="low", candle_time=c1.open_time),
    ]
    latest = make_candle(5, 90, 91, 89, 90.5)  # wick tembus ke bawah, close balik di atas
    sweep = detect_liquidity_sweep([c0, c1, latest], swings, equal_tolerance_pct=0.05)
    assert sweep is not None
    assert sweep.direction == "bullish"
    assert sweep.swept_level == 89.98


def test_no_sweep_when_real_breakout_closes_beyond_level():
    c0 = make_candle(0, 105, 110, 104, 109)
    c1 = make_candle(1, 109, 110.02, 108, 109.5)
    swings = [
        SwingPoint(index=0, price=110, kind="high", candle_time=c0.open_time),
        SwingPoint(index=1, price=110.02, kind="high", candle_time=c1.open_time),
    ]
    latest = make_candle(5, 109, 112, 108.5, 111)  # close 111 > pool level -> breakout asli
    assert detect_liquidity_sweep([c0, c1, latest], swings) is None


def test_no_pool_when_only_single_swing():
    c0 = make_candle(0, 105, 110, 104, 109)
    swings = [SwingPoint(index=0, price=110, kind="high", candle_time=c0.open_time)]
    latest = make_candle(5, 109, 112, 108, 109)
    assert detect_liquidity_sweep([c0, latest], swings) is None


def test_tolerance_excludes_distant_levels_from_pool():
    c0 = make_candle(0, 100, 110, 99, 105)
    c1 = make_candle(1, 105, 120, 104, 115)  # 9% dari 110, jauh di luar tolerance
    swings = [
        SwingPoint(index=0, price=110, kind="high", candle_time=c0.open_time),
        SwingPoint(index=1, price=120, kind="high", candle_time=c1.open_time),
    ]
    latest = make_candle(5, 115, 125, 114, 116)
    assert detect_liquidity_sweep([c0, c1, latest], swings, equal_tolerance_pct=0.05) is None
