from __future__ import annotations

from src.strategy.cooldown import build_cooldown_key, is_in_cooldown, is_rate_limited
from tests.conftest import FakeJSONStore, seed_notified_row


def test_cooldown_key_changes_when_structure_event_time_changes():
    k1 = build_cooldown_key("BTCUSDT", "5m", "support", 100.0, "BOS_BULLISH", 111, "BUY")
    k2 = build_cooldown_key("BTCUSDT", "5m", "support", 100.0, "BOS_BULLISH", 222, "BUY")
    assert k1 != k2  # event/zona baru -> key baru -> cooldown lama otomatis tidak berlaku


def test_is_in_cooldown_true_only_after_notified():
    store = FakeJSONStore()
    key = "BTCUSDT:5m:support:99.0:BOS_BULLISH:111:BUY"
    assert is_in_cooldown(store, key) is False
    seed_notified_row(store, cooldown_key=key)
    assert is_in_cooldown(store, key) is True


def test_rate_limit_disabled_when_zero_or_none():
    store = FakeJSONStore()
    seed_notified_row(store, symbol="BTCUSDT", timeframe="5m", direction="BUY")
    assert is_rate_limited(store, "BTCUSDT", "5m", "BUY", 0) is False
    assert is_rate_limited(store, "BTCUSDT", "5m", "BUY", None) is False


def test_rate_limit_blocks_recent_notification_same_symbol_direction():
    store = FakeJSONStore()
    seed_notified_row(store, symbol="BTCUSDT", timeframe="5m", direction="BUY")
    # signal baru DIFFERENT zona/event tapi symbol+timeframe+direction SAMA,
    # dalam window cooldown_minutes=60 -> harus diblokir walau cooldown_key beda.
    assert is_rate_limited(store, "BTCUSDT", "5m", "BUY", 60) is True


def test_rate_limit_does_not_block_different_direction_or_symbol():
    store = FakeJSONStore()
    seed_notified_row(store, symbol="BTCUSDT", timeframe="5m", direction="BUY")
    assert is_rate_limited(store, "BTCUSDT", "5m", "SELL", 60) is False
    assert is_rate_limited(store, "GOLDUSDT", "5m", "BUY", 60) is False


def test_rate_limit_expires_after_window_passes():
    store = FakeJSONStore()
    seed_notified_row(store, symbol="BTCUSDT", timeframe="5m", direction="BUY")
    store.backdate_all(minutes=90)  # geser mundur 90 menit
    assert is_rate_limited(store, "BTCUSDT", "5m", "BUY", 60) is False  # window 60m sudah lewat
