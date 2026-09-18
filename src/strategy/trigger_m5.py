"""
M5 Entry Trigger — PRD §11 (BUY & SELL, semua syarat wajib terpenuhi).

Urutan evaluasi:
1. Bias M15 harus BULLISH/BEARISH (NEUTRAL -> tidak ada signal, PRD §10 akhir).
2. Bangun zona aktif (support utk BULLISH, resistance utk BEARISH) dari struktur M15.
3. Candle M5 terakhir (closed) harus retest/menyentuh zona.
4. Candle M5 tsb harus pin bar atau engulfing sesuai arah bias.
5. Lolos anti-noise filter (dicek di dalam masing-masing pattern detector).
6. Belum kena cooldown untuk cooldown_key yang sama.
"""

from __future__ import annotations

from typing import List, Optional

from src.models import (
    Bias,
    Candle,
    Direction,
    PatternType,
    Signal,
    StructureResult,
    Zone,
)
from src.patterns.engulfing import detect_bearish_engulfing, detect_bullish_engulfing
from src.patterns.pin_bar import detect_bearish_pin_bar, detect_bullish_pin_bar
from src.storage.d1_client import D1Client
from src.strategy.cooldown import build_cooldown_key, is_in_cooldown
from src.strategy.zones import build_active_zone


def evaluate_m5_trigger(
    market_id: str,
    symbol: str,
    market: str,
    m15_bias: Bias,
    m15_structure: StructureResult,
    m5_candles: List[Candle],
    cfg: dict,
    d1: D1Client,
) -> Optional[Signal]:
    if m15_bias == Bias.NEUTRAL:
        return None
    if len(m5_candles) < 2:
        return None

    zone: Optional[Zone] = build_active_zone(m15_bias, m15_structure, cfg["zoneTolerancePct"])
    if zone is None:
        return None

    curr = m5_candles[-1]
    prev = m5_candles[-2]

    if not zone.is_touched_by(curr):
        return None

    wick_ratio = cfg["pinBarWickToBodyRatio"]
    min_pin_ratio = cfg["minPinBarBodyRangeRatio"]
    min_engulf_ratio = cfg["minEngulfingBodyRangeRatio"]

    direction: Optional[Direction] = None
    pattern: PatternType = PatternType.NONE

    if m15_bias == Bias.BULLISH:
        pin = detect_bullish_pin_bar(curr, wick_ratio, min_pin_ratio)
        eng = detect_bullish_engulfing(prev, curr, min_engulf_ratio)
        if pin.valid:
            direction, pattern = Direction.BUY, PatternType.BULLISH_PIN_BAR
        elif eng.valid:
            direction, pattern = Direction.BUY, PatternType.BULLISH_ENGULFING
    else:  # BEARISH
        pin = detect_bearish_pin_bar(curr, wick_ratio, min_pin_ratio)
        eng = detect_bearish_engulfing(prev, curr, min_engulf_ratio)
        if pin.valid:
            direction, pattern = Direction.SELL, PatternType.BEARISH_PIN_BAR
        elif eng.valid:
            direction, pattern = Direction.SELL, PatternType.BEARISH_ENGULFING

    if direction is None:
        return None

    cooldown_key = build_cooldown_key(
        symbol=symbol,
        timeframe="5m",
        zone_type=zone.zone_type.value,
        zone_level=zone.level,
        structure_event=m15_structure.event.value,
        structure_event_candle_time=m15_structure.event_candle_time,
        direction=direction.value,
    )
    if is_in_cooldown(d1, cooldown_key, cfg["cooldownMinutes"]):
        return None

    signal_key = f"{symbol}:{market}:5m:{curr.candle_time_iso}:{direction.value}"

    return Signal(
        market_id=market_id,
        symbol=symbol,
        market=market,
        timeframe="5m",
        direction=direction,
        m15_bias=m15_bias,
        price=curr.close,
        zone_type=zone.zone_type.value,
        zone_level=zone.level,
        structure_event=m15_structure.event.value,
        pattern=pattern.value,
        candle_time_iso=curr.candle_time_iso,
        candle_open_time_ms=curr.open_time,
        signal_key=signal_key,
        cooldown_key=cooldown_key,
    )
