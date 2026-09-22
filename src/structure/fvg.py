"""
Fair Value Gap (FVG) detector - imbalance 3-candle.

Definisi (standar ICT): untuk tiap window 3 candle berurutan [c0, c1, c2],
gap terbentuk kalau wick c0 dan c2 tidak overlap sama sekali - artinya
c1 (candle tengah) bergerak begitu impulsif sehingga harga "melompati"
satu level tanpa ada transaksi di sana ("inefficiency"). Level itu punya
kecenderungan statistik untuk di-retest ("mitigated") sebelum harga
melanjutkan arah aslinya.

Bullish FVG : low(c2) > high(c0)  -> gap = [high(c0), low(c2)]
Bearish FVG : high(c2) < low(c0)  -> gap = [high(c2), low(c0)]

`min_gap_pct` menyaring gap yang terlalu kecil (noise, bukan imbalance
yang bermakna secara price-action) relatif terhadap harga candle tengah.
Default 0.0 = semua gap valid diterima, identik perilaku "deteksi murni"
tanpa filter - konsisten dengan pola default backward-compatible modul lain
di repo ini (mis. structureBreakBufferPct, break_buffer_pct=0.0 di bos_choch.py).

Gap yang sudah "mitigated" (harga candle setelahnya sudah masuk ke zona gap)
tetap dikembalikan tapi ditandai `mitigated=True` - dipakai scorer untuk
membedakan FVG yang masih "segar" (belum disentuh, confluence lebih kuat)
vs yang sudah pernah di-retest.
"""

from __future__ import annotations

from typing import List

from src.models import Candle, FairValueGap


def detect_fvgs(candles: List[Candle], min_gap_pct: float = 0.0) -> List[FairValueGap]:
    gaps: List[FairValueGap] = []

    for i in range(len(candles) - 2):
        c0, c1, c2 = candles[i], candles[i + 1], candles[i + 2]

        if c2.low > c0.high:
            top, bottom = c2.low, c0.high
            gap_pct = (top - bottom) / c1.close * 100 if c1.close else 0.0
            if gap_pct >= min_gap_pct:
                gaps.append(
                    FairValueGap(
                        direction="bullish",
                        top=top,
                        bottom=bottom,
                        formed_at_candle_time=c1.open_time,
                    )
                )
        elif c2.high < c0.low:
            top, bottom = c0.low, c2.high
            gap_pct = (top - bottom) / c1.close * 100 if c1.close else 0.0
            if gap_pct >= min_gap_pct:
                gaps.append(
                    FairValueGap(
                        direction="bearish",
                        top=top,
                        bottom=bottom,
                        formed_at_candle_time=c1.open_time,
                    )
                )

    return gaps


def mark_mitigated(gaps: List[FairValueGap], candles_after: List[Candle]) -> List[FairValueGap]:
    """
    Tandai tiap FVG sebagai mitigated=True kalau ada candle SETELAH gap
    terbentuk yang menyentuh zonanya (`is_touched_by`). Dipisah dari
    `detect_fvgs` supaya deteksi tetap pure/stateless dan mudah dites
    terpisah dari logika mitigasi.
    """

    result: List[FairValueGap] = []
    for gap in gaps:
        touched = any(
            c.open_time > gap.formed_at_candle_time and gap.is_touched_by(c)
            for c in candles_after
        )
        result.append(gap if not touched else _with_mitigated(gap))
    return result


def _with_mitigated(gap: FairValueGap) -> FairValueGap:
    return FairValueGap(
        direction=gap.direction,
        top=gap.top,
        bottom=gap.bottom,
        formed_at_candle_time=gap.formed_at_candle_time,
        mitigated=True,
    )


def latest_unmitigated(gaps: List[FairValueGap], direction: str) -> FairValueGap | None:
    """FVG paling baru yang belum mitigated untuk arah tertentu, dipakai scorer."""

    candidates = [g for g in gaps if g.direction == direction and not g.mitigated]
    if not candidates:
        return None
    return max(candidates, key=lambda g: g.formed_at_candle_time)
