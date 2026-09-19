from __future__ import annotations

from src.models import Direction, Bias, Signal
from src.storage.signal_repository import mark_notified, try_reserve
from tests.conftest import FakeD1Client


def _make_signal(signal_key="BTCUSDT:futures:5m:2026-01-01T00:00:00Z:BUY", **overrides) -> Signal:
    base = dict(
        market_id="BTCUSDT_FUTURES",
        symbol="BTCUSDT",
        market="futures",
        timeframe="5m",
        direction=Direction.BUY,
        m15_bias=Bias.BULLISH,
        price=50100.0,
        zone_type="support",
        zone_level=50000.0,
        structure_event="BOS_BULLISH",
        pattern="bullish_pin_bar",
        candle_time_iso="2026-01-01T00:00:00Z",
        candle_open_time_ms=0,
        signal_key=signal_key,
        cooldown_key="BTCUSDT:5m:support:50000.0:BOS_BULLISH:0:BUY",
        stop_loss=49975.0,
        take_profit_1=50287.5,
        take_profit_2=50475.0,
        risk_reward_1=1.5,
        risk_reward_2=3.0,
        atr=100.0,
        zone_tolerance_pct_used=0.1,
    )
    base.update(overrides)
    return Signal(**base)


def test_try_reserve_succeeds_for_new_signal_and_stores_risk_fields():
    d1 = FakeD1Client()
    signal = _make_signal()
    assert try_reserve(d1, signal) is True
    stored = d1.rows[0]
    assert stored["stop_loss"] == 49975.0
    assert stored["take_profit_1"] == 50287.5
    assert stored["risk_reward_2"] == 3.0
    assert stored["notified"] == 0


def test_try_reserve_inserts_only_one_row_across_retries():
    """
    signal_key sama dipanggil try_reserve dua kali SEBELUM notified -> kembali
    True dua-duanya (retry sah, lihat test_try_reserve_allows_retry_when_not_yet_notified),
    TAPI cuma boleh ada SATU row tersimpan (bukan insert dobel).
    """
    d1 = FakeD1Client()
    signal = _make_signal()
    try_reserve(d1, signal)
    try_reserve(d1, signal)
    assert len(d1.rows) == 1


def test_try_reserve_allows_retry_when_not_yet_notified():
    """
    Kalau proses mati SEBELUM mark_notified (mis. Discord gagal terkirim),
    row sudah ada tapi notified=0 -> run berikutnya try_reserve utk signal_key
    yang SAMA harus tetap True (boleh retry), bukan diblokir sebagai duplikat.
    """
    d1 = FakeD1Client()
    signal = _make_signal()
    assert try_reserve(d1, signal) is True
    # simulasikan retry run berikutnya sebelum notified di-set
    assert try_reserve(d1, signal) is True
    assert len(d1.rows) == 1  # tetap 1 row, bukan insert baru


def test_mark_notified_then_try_reserve_blocks():
    d1 = FakeD1Client()
    signal = _make_signal()
    try_reserve(d1, signal)
    mark_notified(d1, signal.signal_key)
    assert try_reserve(d1, signal) is False


def test_signal_without_risk_fields_stores_none():
    d1 = FakeD1Client()
    signal = _make_signal(
        signal_key="BTCUSDT:futures:5m:2026-01-01T00:05:00Z:SELL",
        stop_loss=None, take_profit_1=None, take_profit_2=None,
        risk_reward_1=None, risk_reward_2=None, atr=None, zone_tolerance_pct_used=None,
    )
    assert try_reserve(d1, signal) is True
    stored = d1.rows[-1]
    assert stored["stop_loss"] is None
    assert stored["take_profit_1"] is None
