from __future__ import annotations

import copy

from src.config_loader import load_strategy_config
from src.models import Bias, StructureEvent, StructureResult, StructureTrend, SwingPoint
from src.strategy.cooldown import build_cooldown_key
from src.strategy.trigger_m5 import evaluate_m5_trigger
from tests.conftest import FakeD1Client, make_candle, seed_notified_row

M15_INTERVAL_MS = 15 * 60 * 1000


def _m15_candles():
    # histori tenang, cukup untuk ATR M15 (>= atrPeriod+1)
    return [
        make_candle(i, 50500, 50550, 50450, 50500, interval_ms=M15_INTERVAL_MS)
        for i in range(20)
    ]


def _m15_structure() -> StructureResult:
    low_swing = SwingPoint(index=0, price=50000.0, kind="low", candle_time=0)
    high_swing = SwingPoint(index=1, price=51000.0, kind="high", candle_time=1)
    return StructureResult(
        trend=StructureTrend.UP,
        last_swing_high=high_swing,
        last_swing_low=low_swing,
        event=StructureEvent.BOS_BULLISH,
        event_candle_time=999,
    )


def _m5_candles_with_bullish_retest():
    # 13 candle filler (histori utk ATR M5) + prev + curr (bullish pin bar
    # yang retest zona support di level 50000, toleransi ~0.10%).
    filler = [make_candle(i, 50200, 50220, 50180, 50200) for i in range(13)]
    prev = make_candle(13, 50150, 50170, 50100, 50120)
    curr = make_candle(14, 50040, 50055, 49960, 50050)  # bullish pin bar
    return filler + [prev, curr]


def _base_cfg() -> dict:
    return load_strategy_config("BTCUSDT")


def test_generates_buy_signal_with_full_risk_management():
    d1 = FakeD1Client()
    signal = evaluate_m5_trigger(
        market_id="BTCUSDT_FUTURES",
        symbol="BTCUSDT",
        market="futures",
        m15_bias=Bias.BULLISH,
        m15_structure=_m15_structure(),
        m15_candles=_m15_candles(),
        m5_candles=_m5_candles_with_bullish_retest(),
        cfg=_base_cfg(),
        d1=d1,
    )

    assert signal is not None
    assert signal.direction.value == "BUY"
    assert signal.pattern == "bullish_pin_bar"
    assert signal.zone_level == 50000.0
    # risk management wajib terisi (requireRiskManagement default True)
    assert signal.stop_loss is not None
    assert signal.stop_loss < signal.zone_level  # SL di luar (bawah) level zona
    assert signal.take_profit_1 is not None and signal.take_profit_1 > signal.price
    assert signal.risk_reward_1 == 1.5
    assert signal.risk_reward_2 == 3.0
    assert signal.atr is not None
    assert signal.zone_tolerance_pct_used is not None


def test_no_signal_when_bias_neutral():
    d1 = FakeD1Client()
    signal = evaluate_m5_trigger(
        market_id="BTCUSDT_FUTURES", symbol="BTCUSDT", market="futures",
        m15_bias=Bias.NEUTRAL, m15_structure=_m15_structure(),
        m15_candles=_m15_candles(), m5_candles=_m5_candles_with_bullish_retest(),
        cfg=_base_cfg(), d1=d1,
    )
    assert signal is None


def test_no_signal_when_zone_not_touched():
    d1 = FakeD1Client()
    m5_candles = _m5_candles_with_bullish_retest()
    # geser candle terakhir jauh dari zona (tidak retest sama sekali)
    far_curr = make_candle(14, 60040, 60055, 59960, 60050)
    m5_candles = m5_candles[:-1] + [far_curr]
    signal = evaluate_m5_trigger(
        market_id="BTCUSDT_FUTURES", symbol="BTCUSDT", market="futures",
        m15_bias=Bias.BULLISH, m15_structure=_m15_structure(),
        m15_candles=_m15_candles(), m5_candles=m5_candles,
        cfg=_base_cfg(), d1=d1,
    )
    assert signal is None


def test_no_signal_when_risk_reward_below_minimum():
    d1 = FakeD1Client()
    cfg = copy.deepcopy(_base_cfg())
    cfg["minRiskRewardRatio"] = 10.0  # naikkan syarat RR jauh di atas target 1.5
    signal = evaluate_m5_trigger(
        market_id="BTCUSDT_FUTURES", symbol="BTCUSDT", market="futures",
        m15_bias=Bias.BULLISH, m15_structure=_m15_structure(),
        m15_candles=_m15_candles(), m5_candles=_m5_candles_with_bullish_retest(),
        cfg=cfg, d1=d1,
    )
    assert signal is None  # price-action valid, tapi risk:reward tidak layak -> dibatalkan


def test_risk_management_can_be_disabled_for_backward_compatibility():
    d1 = FakeD1Client()
    cfg = copy.deepcopy(_base_cfg())
    cfg["requireRiskManagement"] = False
    signal = evaluate_m5_trigger(
        market_id="BTCUSDT_FUTURES", symbol="BTCUSDT", market="futures",
        m15_bias=Bias.BULLISH, m15_structure=_m15_structure(),
        m15_candles=_m15_candles(), m5_candles=_m5_candles_with_bullish_retest(),
        cfg=cfg, d1=d1,
    )
    assert signal is not None
    assert signal.stop_loss is None
    assert signal.take_profit_1 is None


def test_cooldown_key_blocks_identical_setup_already_notified():
    d1 = FakeD1Client()
    structure = _m15_structure()
    expected_key = build_cooldown_key(
        "BTCUSDT", "5m", "support", 50000.0, "BOS_BULLISH",
        structure.event_candle_time, "BUY",
    )
    # symbol sengaja beda supaya HANYA layer cooldown_key yang teruji,
    # bukan rate-limit waktu (yang dicek berdasar symbol+timeframe+direction).
    seed_notified_row(d1, cooldown_key=expected_key, symbol="OTHER_SYMBOL")

    signal = evaluate_m5_trigger(
        market_id="BTCUSDT_FUTURES", symbol="BTCUSDT", market="futures",
        m15_bias=Bias.BULLISH, m15_structure=structure,
        m15_candles=_m15_candles(), m5_candles=_m5_candles_with_bullish_retest(),
        cfg=_base_cfg(), d1=d1,
    )
    assert signal is None


def test_rate_limit_blocks_new_setup_too_soon_after_notified_signal():
    d1 = FakeD1Client()
    # signal SEBELUMNYA untuk symbol+timeframe+direction yang sama, tapi
    # cooldown_key BEDA (mis. zona/event berbeda) -> cooldown_key layer lolos,
    # tapi rate-limit waktu (default cooldownMinutes=60) harus tetap blokir.
    seed_notified_row(
        d1, cooldown_key="setup_lain_sama_sekali", symbol="BTCUSDT",
        timeframe="5m", direction="BUY",
    )

    signal = evaluate_m5_trigger(
        market_id="BTCUSDT_FUTURES", symbol="BTCUSDT", market="futures",
        m15_bias=Bias.BULLISH, m15_structure=_m15_structure(),
        m15_candles=_m15_candles(), m5_candles=_m5_candles_with_bullish_retest(),
        cfg=_base_cfg(), d1=d1,
    )
    assert signal is None


def test_rate_limit_disabled_still_allows_signal_when_cooldown_minutes_zero():
    d1 = FakeD1Client()
    seed_notified_row(
        d1, cooldown_key="setup_lain_sama_sekali", symbol="BTCUSDT",
        timeframe="5m", direction="BUY",
    )
    cfg = copy.deepcopy(_base_cfg())
    cfg["cooldownMinutes"] = 0

    signal = evaluate_m5_trigger(
        market_id="BTCUSDT_FUTURES", symbol="BTCUSDT", market="futures",
        m15_bias=Bias.BULLISH, m15_structure=_m15_structure(),
        m15_candles=_m15_candles(), m5_candles=_m5_candles_with_bullish_retest(),
        cfg=cfg, d1=d1,
    )
    assert signal is not None


def test_volume_filter_blocks_low_conviction_retest_when_enabled():
    d1 = FakeD1Client()
    cfg = copy.deepcopy(_base_cfg())
    cfg["requireVolumeConfirmation"] = True
    cfg["volumeLookbackCandles"] = 13
    cfg["minVolumeMultiplier"] = 1.0

    filler = [make_candle(i, 50200, 50220, 50180, 50200, v=1000.0) for i in range(13)]
    prev = make_candle(13, 50150, 50170, 50100, 50120, v=1000.0)
    weak_curr = make_candle(14, 50040, 50055, 49960, 50050, v=100.0)  # volume lemah
    m5_candles = filler + [prev, weak_curr]

    signal = evaluate_m5_trigger(
        market_id="BTCUSDT_FUTURES", symbol="BTCUSDT", market="futures",
        m15_bias=Bias.BULLISH, m15_structure=_m15_structure(),
        m15_candles=_m15_candles(), m5_candles=m5_candles,
        cfg=cfg, d1=d1,
    )
    assert signal is None
