"""
Liquidity sweep detector.

Konsep ICT: retail trader menaruh stop-loss tepat di luar swing high/low
yang jelas terlihat ("obvious liquidity"). Kalau ada beberapa swing high
(atau low) dengan level yang HAMPIR SAMA ("equal highs/lows"), area itu
jadi kolam likuiditas yang menarik - harga sering "disapu" (wick menembus
semua level itu) sebelum benar-benar berbalik arah (stop hunt), karena
broker/institusi butuh likuiditas berlawanan buat isi posisi besar.

Deteksi di modul ini:
1. Kelompokkan swing high (atau low) yang levelnya berdekatan dalam
   `equal_tolerance_pct` -> itu "equal highs/lows" alias liquidity pool.
2. Cek apakah ADA candle setelah pool terbentuk yang wick-nya menembus
   level pool tapi CLOSE kembali ke dalam range (bukan breakout beneran -
   itu bedanya sweep vs BOS asli di bos_choch.py yang pakai close sebagai
   ambang).

Bearish sweep (sweep high)  -> indikasi reversal turun -> direction="bearish"
Bullish sweep (sweep low)   -> indikasi reversal naik  -> direction="bullish"

`equal_tolerance_pct` default 0.05 (0.05% dari harga level) - cukup ketat
supaya cuma level yang benar-benar "equal" secara visual yang dikelompokkan,
konsisten dengan skala tolerance zona lain di repo ini (zoneTolerancePctFloor
default 0.05).
"""

from __future__ import annotations

from typing import List, Optional

from src.models import Candle, LiquiditySweep, SwingPoint


def _group_equal_levels(points: List[SwingPoint], tolerance_pct: float) -> List[List[SwingPoint]]:
    """Kelompokkan swing points yang levelnya berdekatan dalam tolerance_pct.
    Sederhana (bukan clustering optimal): urutkan lalu gabungkan tetangga
    yang jaraknya di bawah tolerance - cukup untuk kebutuhan equal-highs/lows."""

    if not points:
        return []

    sorted_points = sorted(points, key=lambda p: p.price)
    groups: List[List[SwingPoint]] = [[sorted_points[0]]]

    for p in sorted_points[1:]:
        last_group = groups[-1]
        ref_price = last_group[-1].price
        diff_pct = abs(p.price - ref_price) / ref_price * 100 if ref_price else 0.0
        if diff_pct <= tolerance_pct:
            last_group.append(p)
        else:
            groups.append([p])

    return [g for g in groups if len(g) >= 2]


def detect_liquidity_sweep(
    candles: List[Candle],
    swings: List[SwingPoint],
    equal_tolerance_pct: float = 0.05,
) -> Optional[LiquiditySweep]:
    if not candles:
        return None

    latest = candles[-1]
    # pool harus terbentuk dari swing SEBELUM candle terakhir - sama prinsip
    # dengan bos_choch.py (tidak membandingkan candle dengan dirinya sendiri).
    prior_highs = [s for s in swings if s.kind == "high" and s.candle_time < latest.open_time]
    prior_lows = [s for s in swings if s.kind == "low" and s.candle_time < latest.open_time]

    high_pools = _group_equal_levels(prior_highs, equal_tolerance_pct)
    low_pools = _group_equal_levels(prior_lows, equal_tolerance_pct)

    # Bearish sweep: wick tembus level pool high, close balik di bawahnya.
    for pool in high_pools:
        pool_level = max(p.price for p in pool)
        if latest.high > pool_level and latest.close < pool_level:
            return LiquiditySweep(
                direction="bearish",
                swept_level=pool_level,
                wick_extreme=latest.high,
                candle_time=latest.open_time,
            )

    # Bullish sweep: wick tembus level pool low, close balik di atasnya.
    for pool in low_pools:
        pool_level = min(p.price for p in pool)
        if latest.low < pool_level and latest.close > pool_level:
            return LiquiditySweep(
                direction="bullish",
                swept_level=pool_level,
                wick_extreme=latest.low,
                candle_time=latest.open_time,
            )

    return None
