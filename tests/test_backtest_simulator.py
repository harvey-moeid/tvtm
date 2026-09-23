from __future__ import annotations

from src.config_loader import load_strategy_config
from src.backtest.simulator import run_backtest
from tests.conftest import make_candle


def _mk15(i, o, h, l, c):
    return make_candle(i, o, h, l, c, interval_ms=15 * 60 * 1000)


def _mk5(i, o, h, l, c):
    return make_candle(i, o, h, l, c, interval_ms=5 * 60 * 1000)


# 16 candle M15 yang membentuk uptrend bersih (2 swing high & 2 swing low naik)
# lalu BOS bullish di candle terakhir (close menembus swing high ke-2 = 49400).
# Sudah diverifikasi manual lewat src.structure.swings/market_structure/bos_choch
# menghasilkan trend=UP, event=BOS_BULLISH, last_swing_low=48950.
_M15_ROWS = [
    (49000, 49010, 48995, 49005), (49005, 49015, 48995, 49010),
    (49010, 49015, 48900, 48910), (48910, 49020, 48905, 49000),
    (49000, 49040, 48990, 49030), (49030, 49200, 49010, 49150),
    (49150, 49160, 49040, 49060), (49060, 49070, 48980, 48990),
    (48990, 49000, 48950, 48965), (48965, 49080, 48960, 49070),
    (49070, 49250, 49060, 49220), (49220, 49400, 49210, 49380),
    (49380, 49385, 49250, 49260), (49260, 49270, 49200, 49220),
    (49220, 49230, 49190, 49210), (49210, 49710, 49255, 49700),
]


def _base_m15_candles():
    return [_mk15(i, *r) for i, r in enumerate(_M15_ROWS)]


def _cfg():
    cfg = dict(load_strategy_config("BTCUSDT"))
    cfg["minHistoricalCandles"] = 16  # kecilkan window khusus skenario test (bukan 200)
    return cfg


def test_generates_one_trade_and_resolves_via_stop_loss():
    m15 = _base_m15_candles()

    # M5: filler jauh dari zona (level 48950) selama 60 candle (300 menit),
    # cukup lewat 240 menit supaya M15 sudah BOS bullish saat kita masuk zona.
    m5 = [_mk5(i, 49600, 49605, 49595, 49600) for i in range(60)]
    m5.append(_mk5(60, 49000, 49020, 48900, 49010))  # bullish pin bar, retest zona
    m5.append(_mk5(61, 49010, 49015, 48000, 48010))  # crash jauh di bawah SL manapun
    for i in range(62, 70):
        m5.append(_mk5(i, 48010, 48015, 48000, 48005))

    trades = run_backtest("BTCUSDT_FUTURES", "BTCUSDT", "futures", m15, m5, _cfg())

    assert len(trades) == 1
    trade = trades[0]
    assert trade.signal.direction.value == "BUY"
    assert trade.signal.pattern == "bullish_pin_bar"
    assert trade.signal.structure_event == "BOS_BULLISH"
    assert trade.status == "CLOSED"
    assert trade.exit_reason == "SL"
    # Exit persis di stop_loss -> R-multiple SELALU -1.0 (didefinisikan dari risk itu sendiri)
    assert trade.pnl_r == -1.0
    assert trade.pnl_pct is not None and trade.pnl_pct < 0


def test_cooldown_blocks_second_signal_at_same_zone_before_structure_changes():
    m15 = _base_m15_candles()

    m5 = [_mk5(i, 49600, 49605, 49595, 49600) for i in range(60)]
    m5.append(_mk5(60, 49000, 49020, 48900, 49010))  # trigger pertama
    m5.append(_mk5(61, 49010, 49040, 49005, 49030))  # netral, SL aman
    m5.append(_mk5(62, 49005, 49020, 48950, 49010))  # pin bar KEDUA di zona sama, SL tetap aman
    for i in range(63, 75):
        m5.append(_mk5(i, 49030, 49040, 49020, 49035))  # flat, tidak pernah resolve

    trades = run_backtest("BTCUSDT_FUTURES", "BTCUSDT", "futures", m15, m5, _cfg())

    # Sinyal kedua HARUS diblok cooldown_key (zona/event M15/arah sama) - tanpa
    # perbaikan ini, backtest akan melaporkan lebih banyak trade daripada yang
    # akan benar-benar dikirim ke Discord kalau strategi ini jalan live.
    assert len(trades) == 1


def test_no_signal_during_warmup_before_enough_m15_history_closed():
    m15 = _base_m15_candles()

    # M5 cuma 100 menit pertama (candle M15 terakhir baru closed di menit
    # ke-240) - window M15 yang sudah closed belum genap minHistoricalCandles,
    # jadi engine harus skip evaluasi ("continue") sama sekali, walau harga
    # M5 terus-terusan menyentuh level zona 48950.
    m5 = [_mk5(i, 49000, 49020, 48900, 49010) for i in range(20)]

    trades = run_backtest("BTCUSDT_FUTURES", "BTCUSDT", "futures", m15, m5, _cfg())
    assert trades == []
