"""
Zone (support/resistance) construction - PRD 11 poin 2-3.

Zona dibentuk dari level swing yang relevan terhadap event struktur terakhir:
- Bias BULLISH -> zona SUPPORT dari last_swing_low
- Bias BEARISH -> zona RESISTANCE dari last_swing_high

UPGRADE - toleransi zona ADAPTIF terhadap volatilitas (ATR), bukan cuma
persentase statis:

    tolerance_pct_effective = max(zoneTolerancePctFloor, (ATR * zoneAtrMultiplier / level) * 100)

- zoneTolerancePctFloor : lantai minimum, mencegah toleransi mendekati nol
  saat volatilitas sedang sangat rendah (retest jadi terlalu ketat).
- zoneAtrMultiplier     : skala toleransi terhadap ATR saat ini, supaya
  toleransi otomatis melebar saat market volatile dan menyempit saat tenang
  - dibanding zoneTolerancePct statis lama yang harus di-tuning manual per
  simbol dan gampang basi begitu rezim volatilitas berubah.
- Kalau ATR tidak tersedia (data candle belum cukup) atau zoneAtrMultiplier
  tidak diset (<=0), fallback ke zoneTolerancePct statis - sistem tetap jalan
  seperti versi awal.
"""

from __future__ import annotations

from typing import Optional

from src.models import Bias, StructureResult, Zone, ZoneType


def compute_zone_tolerance_pct(level: float, atr: Optional[float], cfg: dict) -> float:
    static_pct = cfg["zoneTolerancePct"]
    if atr is None or level <= 0:
        return static_pct

    atr_multiplier = cfg.get("zoneAtrMultiplier", 0.0)
    if atr_multiplier <= 0:
        return static_pct

    floor_pct = cfg.get("zoneTolerancePctFloor", static_pct)
    atr_based_pct = (atr * atr_multiplier / level) * 100
    return max(floor_pct, atr_based_pct)


def build_active_zone(
    bias: Bias, m15_structure: StructureResult, tolerance_pct: float
) -> Optional[Zone]:
    if bias == Bias.BULLISH and m15_structure.last_swing_low:
        return Zone(
            zone_type=ZoneType.SUPPORT,
            level=m15_structure.last_swing_low.price,
            tolerance_pct=tolerance_pct,
            source_swing=m15_structure.last_swing_low,
            structure_event=m15_structure.event,
            structure_event_candle_time=m15_structure.event_candle_time,
        )
    if bias == Bias.BEARISH and m15_structure.last_swing_high:
        return Zone(
            zone_type=ZoneType.RESISTANCE,
            level=m15_structure.last_swing_high.price,
            tolerance_pct=tolerance_pct,
            source_swing=m15_structure.last_swing_high,
            structure_event=m15_structure.event,
            structure_event_candle_time=m15_structure.event_candle_time,
        )
    return None
