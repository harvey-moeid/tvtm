from __future__ import annotations

from src.indicators.atr import compute_atr, true_range
from tests.conftest import make_candle


def test_atr_none_when_insufficient_data():
    candles = [make_candle(i, 100, 105, 95, 100) for i in range(5)]
    assert compute_atr(candles, period=14) is None


def test_true_range_uses_widest_of_three_measures():
    prev = make_candle(0, 100, 102, 98, 100)
    # gap up: range candle sendiri kecil (3), tapi jarak ke close sebelumnya besar
    curr = make_candle(1, 110, 112, 109, 111)
    tr = true_range(curr, prev)
    # max(112-109=3, |112-100|=12, |109-100|=9) = 12
    assert tr == 12


def test_atr_converges_to_constant_true_range():
    # Semua candle: open == close == prev.close (tidak ada gap), high-low tetap 20.
    # TR tiap candle = 20 persis -> ATR (rata-rata bergerak) juga harus konvergen ke 20.
    candles = []
    price = 100.0
    for i in range(30):
        candles.append(make_candle(i, price, price + 10, price - 10, price))
    atr = compute_atr(candles, period=14)
    assert atr is not None
    assert abs(atr - 20.0) < 1e-9


def test_atr_reacts_to_recent_volatility_spike():
    # 20 candle tenang (range kecil) lalu beberapa candle volatile di akhir.
    # ATR (Wilder) harus naik dibanding rata-rata TR periode tenang saja.
    calm = [make_candle(i, 100, 101, 99, 100) for i in range(20)]
    volatile = [make_candle(20 + i, 100, 130, 70, 100) for i in range(5)]
    atr_calm_only = compute_atr(calm, period=14)
    atr_with_spike = compute_atr(calm + volatile, period=14)
    assert atr_calm_only is not None
    assert atr_with_spike is not None
    assert atr_with_spike > atr_calm_only
