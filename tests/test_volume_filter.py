from __future__ import annotations

from src.strategy.volume_filter import passes_volume_filter
from tests.conftest import make_candle


def test_passes_when_filter_disabled():
    candles = [make_candle(i, 100, 101, 99, 100, v=1.0) for i in range(5)]
    assert passes_volume_filter(candles, {"requireVolumeConfirmation": False}) is True


def test_passes_when_history_too_short():
    candles = [make_candle(i, 100, 101, 99, 100, v=1.0) for i in range(5)]
    cfg = {"requireVolumeConfirmation": True, "volumeLookbackCandles": 20, "minVolumeMultiplier": 1.0}
    assert passes_volume_filter(candles, cfg) is True


def test_fails_when_trigger_volume_below_average():
    baseline = [make_candle(i, 100, 101, 99, 100, v=1000.0) for i in range(20)]
    trigger = make_candle(20, 100, 101, 99, 100, v=200.0)  # jauh di bawah rata-rata
    cfg = {"requireVolumeConfirmation": True, "volumeLookbackCandles": 20, "minVolumeMultiplier": 1.0}
    assert passes_volume_filter(baseline + [trigger], cfg) is False


def test_passes_when_trigger_volume_above_average():
    baseline = [make_candle(i, 100, 101, 99, 100, v=1000.0) for i in range(20)]
    trigger = make_candle(20, 100, 101, 99, 100, v=1500.0)
    cfg = {"requireVolumeConfirmation": True, "volumeLookbackCandles": 20, "minVolumeMultiplier": 1.0}
    assert passes_volume_filter(baseline + [trigger], cfg) is True


def test_multiplier_raises_the_bar():
    baseline = [make_candle(i, 100, 101, 99, 100, v=1000.0) for i in range(20)]
    trigger = make_candle(20, 100, 101, 99, 100, v=1400.0)  # 1.4x rata-rata
    cfg = {
        "requireVolumeConfirmation": True,
        "volumeLookbackCandles": 20,
        "minVolumeMultiplier": 1.5,
    }
    assert passes_volume_filter(baseline + [trigger], cfg) is False
