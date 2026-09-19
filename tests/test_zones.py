from __future__ import annotations

from src.models import (
    Bias,
    StructureEvent,
    StructureResult,
    StructureTrend,
    SwingPoint,
    ZoneType,
)
from src.strategy.zones import build_active_zone, compute_zone_tolerance_pct


def test_static_tolerance_used_when_atr_none():
    cfg = {"zoneTolerancePct": 0.10, "zoneAtrMultiplier": 0.5, "zoneTolerancePctFloor": 0.05}
    pct = compute_zone_tolerance_pct(level=50000, atr=None, cfg=cfg)
    assert pct == 0.10


def test_static_tolerance_used_when_multiplier_disabled():
    cfg = {"zoneTolerancePct": 0.10, "zoneAtrMultiplier": 0.0, "zoneTolerancePctFloor": 0.05}
    pct = compute_zone_tolerance_pct(level=50000, atr=100, cfg=cfg)
    assert pct == 0.10


def test_atr_based_tolerance_used_when_wider_than_floor():
    # ATR=100, level=50000, multiplier=0.5 -> atr_based_pct = 100*0.5/50000*100 = 0.10%
    cfg = {"zoneTolerancePct": 0.02, "zoneAtrMultiplier": 0.5, "zoneTolerancePctFloor": 0.05}
    pct = compute_zone_tolerance_pct(level=50000, atr=100, cfg=cfg)
    assert abs(pct - 0.10) < 1e-9


def test_floor_applied_when_atr_based_tolerance_too_small():
    # volatilitas sangat rendah -> atr_based_pct kecil sekali, floor harus menang
    cfg = {"zoneTolerancePct": 0.10, "zoneAtrMultiplier": 0.5, "zoneTolerancePctFloor": 0.05}
    pct = compute_zone_tolerance_pct(level=50000, atr=1, cfg=cfg)  # atr_based ~0.001%
    assert pct == 0.05


def test_tolerance_widens_with_higher_volatility():
    cfg = {"zoneTolerancePct": 0.10, "zoneAtrMultiplier": 0.5, "zoneTolerancePctFloor": 0.05}
    low_vol = compute_zone_tolerance_pct(level=50000, atr=50, cfg=cfg)
    high_vol = compute_zone_tolerance_pct(level=50000, atr=500, cfg=cfg)
    assert high_vol > low_vol


def _structure(trend, event, low_price=95.0, high_price=110.0):
    low = SwingPoint(index=0, price=low_price, kind="low", candle_time=0)
    high = SwingPoint(index=1, price=high_price, kind="high", candle_time=1)
    return StructureResult(
        trend=trend,
        last_swing_high=high,
        last_swing_low=low,
        event=event,
        event_candle_time=123,
    )


def test_build_active_zone_bullish_uses_support_from_last_low():
    structure = _structure(StructureTrend.UP, StructureEvent.BOS_BULLISH)
    zone = build_active_zone(Bias.BULLISH, structure, tolerance_pct=0.10)
    assert zone is not None
    assert zone.zone_type == ZoneType.SUPPORT
    assert zone.level == 95.0


def test_build_active_zone_bearish_uses_resistance_from_last_high():
    structure = _structure(StructureTrend.DOWN, StructureEvent.BOS_BEARISH)
    zone = build_active_zone(Bias.BEARISH, structure, tolerance_pct=0.10)
    assert zone is not None
    assert zone.zone_type == ZoneType.RESISTANCE
    assert zone.level == 110.0


def test_zone_tolerance_is_mutable_for_atr_refresh():
    structure = _structure(StructureTrend.UP, StructureEvent.BOS_BULLISH)
    zone = build_active_zone(Bias.BULLISH, structure, tolerance_pct=0.10)
    zone.tolerance_pct = 0.25  # simulasi refresh adaptif di trigger_m5.py
    assert zone.tolerance_pct == 0.25
    assert abs(zone.upper_bound - zone.level * 1.0025) < 1e-9
