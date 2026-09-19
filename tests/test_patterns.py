from __future__ import annotations

from src.patterns.engulfing import detect_bearish_engulfing, detect_bullish_engulfing
from src.patterns.pin_bar import detect_bearish_pin_bar, detect_bullish_pin_bar
from tests.conftest import make_candle


def test_valid_bullish_pin_bar():
    # body kecil di 1/3 atas, lower wick panjang, close>open
    c = make_candle(0, 99, 100, 90, 99.5)
    result = detect_bullish_pin_bar(c, wick_to_body_ratio=2.0, min_pin_bar_body_ratio=0.03)
    assert result.valid


def test_bullish_pin_bar_rejected_if_body_not_in_upper_third():
    c = make_candle(0, 95, 100, 90, 95.5)  # body di tengah, bukan atas
    result = detect_bullish_pin_bar(c, wick_to_body_ratio=2.0, min_pin_bar_body_ratio=0.03)
    assert not result.valid


def test_valid_bearish_pin_bar():
    c = make_candle(0, 100.5, 110, 100, 100)
    result = detect_bearish_pin_bar(c, wick_to_body_ratio=2.0, min_pin_bar_body_ratio=0.03)
    assert result.valid


def test_doji_rejected_by_min_body_ratio():
    # posisi body sudah di upper third & wick ratio terpenuhi, TAPI body/range
    # (0.1/10 = 0.01) di bawah ambang min_pin_bar_body_ratio (0.03) -> harus
    # ditolak murni karena ratio, bukan karena posisi.
    c = make_candle(0, 99.9, 100, 90, 100.0)
    result = detect_bullish_pin_bar(c, wick_to_body_ratio=2.0, min_pin_bar_body_ratio=0.03)
    assert not result.valid


def test_valid_bullish_engulfing():
    prev = make_candle(0, 100, 101, 95, 96)  # bearish
    curr = make_candle(1, 95, 103, 94, 102)  # bullish, menelan penuh body prev
    result = detect_bullish_engulfing(prev, curr, min_body_range_ratio=0.35)
    assert result.valid


def test_bullish_engulfing_rejected_when_not_fully_engulfing():
    prev = make_candle(0, 100, 101, 95, 96)
    curr = make_candle(1, 97, 103, 96, 99)  # tidak menelan penuh (close < open prev)
    result = detect_bullish_engulfing(prev, curr, min_body_range_ratio=0.35)
    assert not result.valid


def test_valid_bearish_engulfing():
    prev = make_candle(0, 95, 101, 94, 100)  # bullish
    curr = make_candle(1, 101, 102, 93, 94)  # bearish, menelan penuh body prev
    result = detect_bearish_engulfing(prev, curr, min_body_range_ratio=0.35)
    assert result.valid
