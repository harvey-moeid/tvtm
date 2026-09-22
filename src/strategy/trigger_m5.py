"""
M5 Entry Trigger - PRD 11, + upgrade menyeluruh.

Urutan evaluasi (upgrade dari versi awal ditandai [BARU]):
1. Bias M15 harus BULLISH/BEARISH (NEUTRAL -> tidak ada signal).
2. Bangun zona aktif dari struktur M15.
   [BARU] Toleransi zona dihitung ADAPTIF terhadap ATR M15, bukan persentase
   statis semata (lihat src/strategy/zones.py).
3. Candle M5 terakhir (closed) harus retest/menyentuh zona.
4. [BARU] Kalau requireVolumeConfirmation aktif: volume candle trigger harus
   >= rata-rata x multiplier (confluence tambahan di luar price action murni).
5. Candle M5 tsb harus pin bar atau engulfing sesuai arah bias, lolos
   anti-noise filter masing-masing pattern.
6. [BARU] Hitung risk levels: SL berbasis level zona + buffer ATR M5, TP
   berbasis kelipatan R. Kalau requireRiskManagement aktif dan risk:reward
   atau jarak SL tidak layak, sinyal DIBATALKAN - sebelumnya tidak ada
   konsep "price action valid tapi risknya tidak layak", semua yang lolos
   langkah 1-5 langsung dikirim apa adanya.
7. Belum kena cooldown_key (permanen per setup struktural, PRD 14) DAN
   [BARU] belum kena rate-limit waktu (cooldownMinutes, kini benar-benar aktif).
8. [BARU - ICT full suite] Hitung skor konfluensi (Market Structure, Liquidity
   Sweep, FVG, Order Block, Volume Profile - semua dihitung dari m5_candles)
   lewat scorer.compute_score(). Kalau requireRiskManagement/pattern sudah
   lolos tapi score di bawah `minScoreToNotify` (default 0.0 = tidak pernah
   memfilter, backward compatible), sinyal DIBATALKAN juga - konsisten
   dengan filosofi langkah 6 (price action + risk valid saja tidak cukup
   kalau confluence ICT lain menentang arah sinyal).
"""

from __future__ import annotations

from typing import List, Optional

from src.indicators.atr import compute_atr
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
from src.strategy.cooldown import build_cooldown_key, is_in_cooldown, is_rate_limited
from src.strategy.liquidity import detect_liquidity_sweep
from src.strategy.risk import compute_risk_levels
from src.strategy.scorer import compute_score
from src.strategy.volume_filter import passes_volume_filter
from src.strategy.volume_profile import compute_volume_profile
from src.strategy.zones import build_active_zone, compute_zone_tolerance_pct
from src.structure.bos_choch import detect_structure_event
from src.structure.fvg import detect_fvgs, mark_mitigated as mark_fvgs_mitigated
from src.structure.order_block import detect_order_block, mark_mitigated as mark_ob_mitigated
from src.structure.market_structure import classify_structure
from src.structure.swings import detect_swings


def evaluate_m5_trigger(
    market_id: str,
    symbol: str,
    market: str,
    m15_bias: Bias,
    m15_structure: StructureResult,
    m15_candles: List[Candle],
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

    atr_period = cfg.get("atrPeriod", 14)
    m15_atr = compute_atr(m15_candles, atr_period)
    m5_atr = compute_atr(m5_candles, atr_period)
    # Toleransi zona di-refresh jadi adaptif (fallback otomatis ke statis
    # kalau ATR M15 belum tersedia atau zoneAtrMultiplier tidak diset).
    zone.tolerance_pct = compute_zone_tolerance_pct(zone.level, m15_atr, cfg)

    curr = m5_candles[-1]
    prev = m5_candles[-2]

    if not zone.is_touched_by(curr):
        return None

    if not passes_volume_filter(m5_candles, cfg):
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

    risk = None
    if cfg.get("requireRiskManagement", True):
        risk = compute_risk_levels(
            direction=direction,
            entry_price=curr.close,
            structure_stop_price=zone.level,
            atr=m5_atr,
            cfg=cfg,
        )
        if not risk.valid:
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
    if is_in_cooldown(d1, cooldown_key):
        return None
    if is_rate_limited(d1, symbol, "5m", direction.value, cfg.get("cooldownMinutes", 0)):
        return None

    # --- ICT full suite: hitung Liquidity / FVG / Order Block / Volume
    # Profile dari m5_candles (timeframe yang sama dengan chart di dashboard
    # referensi), lalu gabungkan jadi score/confidence via scorer.py.
    m5_swings = detect_swings(m5_candles, cfg.get("swingLookback", 2))
    m5_structure_result = classify_structure(m5_swings, cfg.get("minStructureConfirmation", 1))
    m5_event_result = detect_structure_event(
        m5_candles,
        m5_swings,
        prior_trend=m5_structure_result.trend,
        min_confirmation=cfg.get("minStructureConfirmation", 1),
        break_buffer_pct=cfg.get("structureBreakBufferPct", 0.0),
    )

    liquidity_sweep = detect_liquidity_sweep(
        m5_candles, m5_swings, cfg.get("liquidityEqualTolerancePct", 0.05)
    )

    fvgs = detect_fvgs(m5_candles, cfg.get("fvgMinGapPct", 0.0))
    fvgs = mark_fvgs_mitigated(fvgs, m5_candles)

    order_block = detect_order_block(
        m5_candles,
        m5_event_result.event,
        m5_event_result.event_candle_time,
        cfg.get("obLookback", 10),
    )
    order_block = mark_ob_mitigated(
        order_block,
        m5_candles,
        event_candle_time=m5_event_result.event_candle_time,
    )

    volume_profile = compute_volume_profile(m5_candles, cfg.get("volumeProfileBucketCount", 24))

    score_result = compute_score(
        direction=direction,
        m15_structure=m15_structure,
        liquidity_sweep=liquidity_sweep,
        fvgs=fvgs,
        order_block=order_block,
        volume_profile=volume_profile,
    )

    min_score = cfg.get("minScoreToNotify", 0.0)
    if score_result.score < min_score:
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
        stop_loss=risk.stop_loss if risk else None,
        take_profit_1=risk.take_profit_1 if risk else None,
        take_profit_2=risk.take_profit_2 if risk else None,
        risk_reward_1=risk.risk_reward_1 if risk else None,
        risk_reward_2=risk.risk_reward_2 if risk else None,
        atr=m5_atr,
        zone_tolerance_pct_used=zone.tolerance_pct,
        confidence_pct=score_result.confidence_pct,
        score=score_result.score,
        checklist=score_result.components,
    )