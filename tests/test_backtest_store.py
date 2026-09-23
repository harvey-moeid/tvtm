from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.backtest.store import InMemorySignalStore


def test_cooldown_key_blocks_exact_duplicate_regardless_of_simulated_time():
    store = InMemorySignalStore()
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    store.advance_to(t0)
    store.record_notified(
        cooldown_key="k1", symbol="BTCUSDT", timeframe="5m", direction="BUY", created_at=t0
    )

    row = store.query_one(
        "SELECT id FROM signals WHERE cooldown_key = ? AND notified = 1 LIMIT 1", ["k1"]
    )
    assert row is not None

    row_other = store.query_one(
        "SELECT id FROM signals WHERE cooldown_key = ? AND notified = 1 LIMIT 1", ["k2"]
    )
    assert row_other is None


def test_rate_limit_uses_simulated_clock_not_wall_clock():
    store = InMemorySignalStore()
    t0 = datetime(2020, 1, 1, tzinfo=timezone.utc)  # jauh di masa lalu dari wall-clock asli
    store.advance_to(t0)
    store.record_notified(
        cooldown_key="k1", symbol="BTCUSDT", timeframe="5m", direction="BUY", created_at=t0
    )

    sql = (
        "SELECT id FROM signals WHERE symbol = ? AND timeframe = ? AND direction = ? "
        "AND notified = 1 AND created_at >= strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?) LIMIT 1"
    )

    # Maju 30 menit (simulasi) dgn cooldown 60 menit -> MASIH kena rate-limit.
    store.advance_to(t0 + timedelta(minutes=30))
    row = store.query_one(sql, ["BTCUSDT", "5m", "BUY", "-60 minutes"])
    assert row is not None

    # Maju 90 menit (simulasi) dgn cooldown 60 menit -> SUDAH lewat cooldown.
    store.advance_to(t0 + timedelta(minutes=90))
    row2 = store.query_one(sql, ["BTCUSDT", "5m", "BUY", "-60 minutes"])
    assert row2 is None


def test_execute_is_not_supported_reads_only():
    store = InMemorySignalStore()
    try:
        store.execute("INSERT INTO signals ...", [])
        assert False, "harus raise NotImplementedError"
    except NotImplementedError:
        pass
