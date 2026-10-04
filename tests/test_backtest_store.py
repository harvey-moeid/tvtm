from datetime import datetime, timedelta, timezone

from src.backtest.store import InMemorySignalStore


def test_cooldown_key_blocks_exact_duplicate_regardless_of_simulated_time():
    store = InMemorySignalStore()
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    store.advance_to(t0)
    store.record_notified(cooldown_key="k1", symbol="BTCUSDT", timeframe="5m", direction="BUY", created_at=t0)
    assert store.has_notified_cooldown("k1")
    assert not store.has_notified_cooldown("k2")


def test_rate_limit_uses_simulated_clock():
    store = InMemorySignalStore()
    t0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
    store.record_notified(cooldown_key="k1", symbol="BTCUSDT", timeframe="5m", direction="BUY", created_at=t0)
    store.advance_to(t0 + timedelta(minutes=30))
    assert store.was_notified_recently("BTCUSDT", "5m", "BUY", 60)
    store.advance_to(t0 + timedelta(minutes=90))
    assert not store.was_notified_recently("BTCUSDT", "5m", "BUY", 60)
