from __future__ import annotations

from src.strategy.volume_profile import compute_volume_profile
from tests.conftest import make_candle


def test_poc_price_falls_in_high_volume_bucket():
    candles = [
        make_candle(0, 100, 101, 99, 100.5, v=10),
        make_candle(1, 100, 101, 99, 100.5, v=500),
        make_candle(2, 100, 101, 99, 100.5, v=10),
    ]
    result = compute_volume_profile(candles, bucket_count=4)
    assert result.poc_price is not None
    assert 99 <= result.poc_price <= 101


def test_buy_imbalance_when_bullish_volume_dominant():
    candles = [
        make_candle(0, 100, 105, 99, 104, v=100),  # bullish
        make_candle(1, 104, 108, 103, 107, v=100),  # bullish
        make_candle(2, 107, 108, 105, 106, v=10),   # bearish kecil
    ]
    result = compute_volume_profile(candles, bucket_count=4)
    assert result.imbalance == "buy_imbalance"


def test_sell_imbalance_when_bearish_volume_dominant():
    candles = [
        make_candle(0, 108, 109, 104, 105, v=100),  # bearish
        make_candle(1, 105, 106, 101, 102, v=100),  # bearish
        make_candle(2, 102, 104, 101, 103, v=10),   # bullish kecil
    ]
    result = compute_volume_profile(candles, bucket_count=4)
    assert result.imbalance == "sell_imbalance"


def test_neutral_when_volume_balanced():
    candles = [
        make_candle(0, 100, 105, 99, 104, v=100),  # bullish
        make_candle(1, 104, 105, 99, 100, v=100),  # bearish, volume sama
    ]
    result = compute_volume_profile(candles, bucket_count=4)
    assert result.imbalance == "neutral"


def test_empty_candles_returns_empty_result():
    result = compute_volume_profile([], bucket_count=10)
    assert result.levels == []
    assert result.poc_price is None
    assert result.imbalance == "neutral"


def test_bucket_count_less_than_one_returns_empty():
    candles = [make_candle(0, 100, 101, 99, 100)]
    result = compute_volume_profile(candles, bucket_count=0)
    assert result.levels == []
