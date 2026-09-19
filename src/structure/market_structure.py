"""
Market structure classification - PRD 8.2, + upgrade min_confirmation.

UP   : minimal `min_confirmation + 1` swing high berturut-turut naik (HH)
       DAN minimal `min_confirmation + 1` swing low berturut-turut naik (HL).
DOWN : mirror (LH + LL berturut-turut turun).
RANGE: selain kondisi di atas, atau data swing belum cukup.

UPGRADE: parameter `min_confirmation` (default 1, IDENTIK dengan perilaku
versi awal yang membandingkan 2 swing high + 2 swing low terakhir) dibuat
configurable lewat strategy.json (minStructureConfirmation).

Efek sebenarnya menaikkan nilai ini: klasifikasi trend mensyaratkan seluruh
`min_confirmation + 1` swing high DAN swing low terakhir monoton searah -
bukan cuma pasangan swing paling akhir. Jadi kalau ada 1 swing "shakeout"
(mis. sedikit lower-high/lower-low di tengah uptrend yang sehat), versi
awal (confirmation=1) akan langsung membaca ini sebagai reversal ke DOWN
(karena cuma bandingkan pasangan terakhir) - berpotensi memicu CHoCH_BEARISH
palsu. Versi upgrade dengan confirmation>=2 akan jatuh ke RANGE pada momen
itu (karena tidak semua swing di window monoton), BUKAN salah membaca DOWN.
Trade-off: sistem butuh lebih banyak swing konsisten untuk kembali percaya
diri UP/DOWN setelah shakeout, jadi pengenalan trend (dan trend reversal
yang valid) jadi lebih lambat - tapi kegagalannya berubah dari "percaya
diri salah arah" menjadi "tidak yakin / no-trade", yang jauh lebih aman
untuk sistem trading.
"""

from __future__ import annotations

from typing import List

from src.models import StructureResult, StructureTrend, SwingPoint


def _is_monotonic_increasing(prices: List[float]) -> bool:
    return all(prices[i] < prices[i + 1] for i in range(len(prices) - 1))


def _is_monotonic_decreasing(prices: List[float]) -> bool:
    return all(prices[i] > prices[i + 1] for i in range(len(prices) - 1))


def classify_structure(swings: List[SwingPoint], min_confirmation: int = 1) -> StructureResult:
    min_confirmation = max(1, min_confirmation)
    need = min_confirmation + 1  # jumlah swing high/low berturut-turut yang dibandingkan

    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]

    last_high = highs[-1] if highs else None
    last_low = lows[-1] if lows else None

    if len(highs) < need or len(lows) < need:
        return StructureResult(
            trend=StructureTrend.RANGE,
            last_swing_high=last_high,
            last_swing_low=last_low,
            swings=swings,
        )

    recent_highs = [s.price for s in highs[-need:]]
    recent_lows = [s.price for s in lows[-need:]]

    is_up = _is_monotonic_increasing(recent_highs) and _is_monotonic_increasing(recent_lows)
    is_down = _is_monotonic_decreasing(recent_highs) and _is_monotonic_decreasing(recent_lows)

    if is_up:
        trend = StructureTrend.UP
    elif is_down:
        trend = StructureTrend.DOWN
    else:
        trend = StructureTrend.RANGE

    return StructureResult(
        trend=trend,
        last_swing_high=last_high,
        last_swing_low=last_low,
        swings=swings,
    )
