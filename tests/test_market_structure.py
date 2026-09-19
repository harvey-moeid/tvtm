from __future__ import annotations

from src.models import StructureTrend, SwingPoint
from src.structure.market_structure import classify_structure


def sp(price: float, kind: str, t: int) -> SwingPoint:
    return SwingPoint(index=t, price=price, kind=kind, candle_time=t)


def test_up_trend_default_confirmation_matches_original_behavior():
    swings = [
        sp(100, "low", 0), sp(110, "high", 1),
        sp(105, "low", 2), sp(115, "high", 3),
    ]
    result = classify_structure(swings, min_confirmation=1)
    assert result.trend == StructureTrend.UP


def test_down_trend_default_confirmation():
    swings = [
        sp(115, "high", 0), sp(105, "low", 1),
        sp(110, "high", 2), sp(100, "low", 3),
    ]
    result = classify_structure(swings, min_confirmation=1)
    assert result.trend == StructureTrend.DOWN


def test_mixed_hh_ll_is_range():
    swings = [
        sp(100, "low", 0), sp(110, "high", 1),
        sp(95, "low", 2), sp(115, "high", 3),  # HH tapi LL -> ambigu
    ]
    result = classify_structure(swings, min_confirmation=1)
    assert result.trend == StructureTrend.RANGE


def test_insufficient_swings_is_range():
    swings = [sp(100, "low", 0), sp(110, "high", 1)]
    result = classify_structure(swings, min_confirmation=1)
    assert result.trend == StructureTrend.RANGE


def test_higher_confirmation_avoids_false_reversal_on_shakeout():
    """
    Skenario: uptrend sehat (h1,l1 -> h2,l2), lalu SATU pasang swing "shakeout"
    (h3,l3 sedikit lebih rendah dari h2,l2 -- retracement wajar, bukan reversal
    sungguhan), sebelum lanjut naik lagi (h4,l4).

    confirmation=1 (perilaku awal): hanya bandingkan pasangan swing PALING AKHIR.
    Pada titik h3/l3, pasangan terakhir (h3<h2, l3<l2) terbaca DOWN -> berpotensi
    memicu CHoCH_BEARISH palsu padahal ini cuma retracement kecil.

    confirmation=2 (upgrade): butuh 3 swing high & 3 swing low terakhir monoton
    penuh. Karena h3/l3 memutus monotonicity, hasilnya RANGE (tidak yakin),
    bukan salah membaca DOWN -- inilah manfaat utamanya: gagal ke "no-trade",
    bukan gagal ke "arah salah".
    """
    highs = [sp(100, "high", 0), sp(110, "high", 2), sp(108, "high", 4), sp(115, "high", 6)]
    lows = [sp(95, "low", 1), sp(102, "low", 3), sp(99, "low", 5), sp(106, "low", 7)]

    # Sampai titik shakeout (h1,h2,h3 / l1,l2,l3) saja:
    swings_at_shakeout = highs[:3] + lows[:3]

    old_behavior = classify_structure(swings_at_shakeout, min_confirmation=1)
    assert old_behavior.trend == StructureTrend.DOWN  # false reversal read

    upgraded_behavior = classify_structure(swings_at_shakeout, min_confirmation=2)
    assert upgraded_behavior.trend == StructureTrend.RANGE  # no-trade, bukan salah arah

    # Full 4 swing (uptrend lanjut lagi setelah shakeout):
    swings_full = highs + lows
    old_behavior_full = classify_structure(swings_full, min_confirmation=1)
    assert old_behavior_full.trend == StructureTrend.UP  # cepat balik yakin (tapi reaktif)

    upgraded_behavior_full = classify_structure(swings_full, min_confirmation=2)
    # masih RANGE karena window 3-swing terakhir (h2,h3,h4 / l2,l3,l4) masih
    # memuat titik shakeout -> butuh 1 swing lagi yang konsisten baru yakin UP lagi.
    assert upgraded_behavior_full.trend == StructureTrend.RANGE


def test_last_swing_high_low_reported_regardless_of_confirmation():
    swings = [sp(100, "low", 0), sp(110, "high", 1)]
    result = classify_structure(swings, min_confirmation=3)
    assert result.last_swing_high is not None and result.last_swing_high.price == 110
    assert result.last_swing_low is not None and result.last_swing_low.price == 100
