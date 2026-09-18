"""
Zone (support/resistance) construction — PRD §11 poin 2-3.

Zona dibentuk dari level swing yang relevan terhadap event struktur terakhir:
- Bias BULLISH  -> zona SUPPORT dari last_swing_low (area demand yang divalidasi BOS/CHoCH)
- Bias BEARISH  -> zona RESISTANCE dari last_swing_high (area supply yang divalidasi BOS/CHoCH)

Toleransi zona (persen) dibuat configurable per-symbol lewat strategy.json
(zoneTolerancePct) karena volatilitas BTC vs GOLD berbeda jauh.
"""

from __future__ import annotations

from typing import List, Optional

from src.models import Bias, StructureResult, Zone, ZoneType


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
