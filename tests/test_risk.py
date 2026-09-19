from __future__ import annotations

from src.models import Direction
from src.strategy.risk import compute_risk_levels

BASE_CFG = {
    "slAtrBufferMultiplier": 0.25,
    "riskRewardTargets": [1.5, 3.0],
    "minRiskRewardRatio": 1.2,
    "minStopDistancePct": 0.05,
    "maxStopDistancePct": 5.0,
}


def test_buy_signal_stop_below_zone_minus_buffer():
    risk = compute_risk_levels(
        direction=Direction.BUY,
        entry_price=50100.0,
        structure_stop_price=50000.0,  # level zona (support)
        atr=100.0,
        cfg=BASE_CFG,
    )
    assert risk.valid
    # buffer = atr * 0.25 = 25 -> SL = 50000 - 25 = 49975
    assert abs(risk.stop_loss - 49975.0) < 1e-6
    risk_amount = 50100.0 - 49975.0  # 125
    assert abs(risk.take_profit_1 - (50100.0 + risk_amount * 1.5)) < 1e-6
    assert abs(risk.take_profit_2 - (50100.0 + risk_amount * 3.0)) < 1e-6
    assert risk.risk_reward_1 == 1.5
    assert risk.risk_reward_2 == 3.0


def test_sell_signal_stop_above_zone_plus_buffer():
    risk = compute_risk_levels(
        direction=Direction.SELL,
        entry_price=49900.0,
        structure_stop_price=50000.0,  # level zona (resistance)
        atr=100.0,
        cfg=BASE_CFG,
    )
    assert risk.valid
    assert abs(risk.stop_loss - 50025.0) < 1e-6  # 50000 + 25
    risk_amount = 50025.0 - 49900.0  # 125
    assert abs(risk.take_profit_1 - (49900.0 - risk_amount * 1.5)) < 1e-6


def test_invalid_when_atr_missing():
    risk = compute_risk_levels(
        direction=Direction.BUY, entry_price=100, structure_stop_price=95, atr=None, cfg=BASE_CFG
    )
    assert not risk.valid
    assert risk.reason == "atr_or_price_invalid"


def test_invalid_when_risk_non_positive():
    # entry sudah di bawah structure_stop_price + buffer utk BUY -> risk <= 0
    risk = compute_risk_levels(
        direction=Direction.BUY,
        entry_price=100.0,
        structure_stop_price=105.0,  # stop di atas entry -> risk negatif utk BUY
        atr=1.0,
        cfg=BASE_CFG,
    )
    assert not risk.valid
    assert risk.reason == "non_positive_risk"


def test_invalid_when_stop_too_tight():
    cfg = dict(BASE_CFG, minStopDistancePct=1.0)  # butuh jarak SL >= 1% dari entry
    risk = compute_risk_levels(
        direction=Direction.BUY,
        entry_price=50000.0,
        structure_stop_price=49990.0,  # sangat dekat
        atr=1.0,  # buffer kecil
        cfg=cfg,
    )
    assert not risk.valid
    assert risk.reason == "stop_too_tight"


def test_invalid_when_stop_too_wide():
    cfg = dict(BASE_CFG, maxStopDistancePct=1.0)  # SL maksimal 1% dari entry
    risk = compute_risk_levels(
        direction=Direction.BUY,
        entry_price=50000.0,
        structure_stop_price=40000.0,  # jarak sangat lebar (~20%)
        atr=100.0,
        cfg=cfg,
    )
    assert not risk.valid
    assert risk.reason == "stop_too_wide"


def test_invalid_when_rr_below_minimum():
    cfg = dict(BASE_CFG, riskRewardTargets=[1.0, 2.0], minRiskRewardRatio=1.2)
    risk = compute_risk_levels(
        direction=Direction.BUY,
        entry_price=50100.0,
        structure_stop_price=50000.0,
        atr=100.0,
        cfg=cfg,
    )
    assert not risk.valid
    assert risk.reason == "risk_reward_below_minimum"


def test_single_target_when_only_one_rr_configured():
    cfg = dict(BASE_CFG, riskRewardTargets=[2.0])
    risk = compute_risk_levels(
        direction=Direction.BUY,
        entry_price=50100.0,
        structure_stop_price=50000.0,
        atr=100.0,
        cfg=cfg,
    )
    assert risk.valid
    assert risk.take_profit_2 is None
    assert risk.risk_reward_2 is None
