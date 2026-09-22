"""
Scorer - menggabungkan 5 komponen konfluensi ICT jadi satu skor sinyal:

  1. Market Structure  (bobot 2.5) - ada BOS/CHoCH M15 BARU (event candle ini) searah sinyal
  2. Liquidity          (bobot 1.5) - ada liquidity sweep searah sinyal
  3. FVG                (bobot 2.0) - ada Fair Value Gap belum-mitigated searah sinyal
  4. Order Block        (bobot 2.5) - ada Order Block belum-mitigated searah sinyal
  5. Volume Profile     (bobot 1.5) - imbalance volume searah sinyal

Total bobot = 10.0, sehingga `score = sum(bobot komponen valid)` otomatis
berada di rentang 0-10 - selaras dengan tampilan referensi ("Score 8.2/10").
`confidence_pct = round(score / 10 * 100)` - representasi persentase yang
sama, dibulatkan ke bilangan bulat.

Bobot Market Structure dan Order Block paling besar (2.5) karena keduanya
paling langsung menunjukkan arah & area entry; Liquidity dan Volume Profile
paling kecil (1.5) karena sifatnya konfirmasi tambahan (confluence), bukan
sinyal utama. Ini keputusan desain awal - BELUM divalidasi backtest, sama
seperti parameter ICT lain di repo ini (lihat README bagian "Parameter baru").

Fungsi ini murni (tidak I/O), menerima hasil semua detektor yang sudah
dihitung caller (trigger_m5.py) dan mengembalikan ScoreResult siap ditempel
ke Signal.

CATATAN PERBAIKAN - komponen "Market Structure":
Sebelumnya komponen ini mengecek `m15_structure.trend` searah `direction`
semata. Tapi di trigger_m5.py, `direction` (BUY/SELL) hanya pernah di-set
SETELAH m15_bias (BULLISH/BEARISH) sudah dicek cocok - dan m15_bias sendiri
diturunkan langsung dari m15_structure.trend di bias_m15.py (Bias.BULLISH
hanya kalau trend==UP, Bias.BEARISH hanya kalau trend==DOWN). Akibatnya
kombinasi "direction BUY tapi trend DOWN" MUSTAHIL terjadi di jalur produksi,
sehingga cek berbasis trend itu SELALU valid=True - menyumbang 2.5/10 poin
(25%) gratis yang tidak pernah benar-benar menyaring sinyal apa pun (lantai
skor tersembunyi).

Sekarang komponen ini mengecek `m15_structure.event`: apakah candle M15
terakhir BARU SAJA membentuk BOS/CHoCH searah sinyal (bukan cuma trend lama
yang sudah berjalan tanpa breakout baru). `event` bisa NONE walau trend
sudah UP/DOWN sejak beberapa candle M15 lalu, jadi ini benar-benar
diskriminatif: sinyal yang muncul persis di momen breakout struktural M15
mendapat skor lebih tinggi daripada sinyal retest biasa di trend yang sudah
lama berjalan tanpa event baru.
"""

from __future__ import annotations

from typing import List, Optional

from src.models import (
    Direction,
    FairValueGap,
    LiquiditySweep,
    OrderBlock,
    ScoreComponent,
    ScoreResult,
    StructureEvent,
    StructureResult,
    VolumeProfileResult,
)

_MARKET_STRUCTURE_WEIGHT = 2.5
_LIQUIDITY_WEIGHT = 1.5
_FVG_WEIGHT = 2.0
_ORDER_BLOCK_WEIGHT = 2.5
_VOLUME_PROFILE_WEIGHT = 1.5

_BULLISH_STRUCTURE_EVENTS = (StructureEvent.BOS_BULLISH, StructureEvent.CHOCH_BULLISH)
_BEARISH_STRUCTURE_EVENTS = (StructureEvent.BOS_BEARISH, StructureEvent.CHOCH_BEARISH)

_STRUCTURE_EVENT_LABELS = {
    StructureEvent.BOS_BULLISH: "BOS Bullish",
    StructureEvent.CHOCH_BULLISH: "CHoCH Bullish",
    StructureEvent.BOS_BEARISH: "BOS Bearish",
    StructureEvent.CHOCH_BEARISH: "CHoCH Bearish",
    StructureEvent.NONE: "No Fresh Break",
}


def compute_score(
    direction: Direction,
    m15_structure: StructureResult,
    liquidity_sweep: Optional[LiquiditySweep],
    fvgs: List[FairValueGap],
    order_block: Optional[OrderBlock],
    volume_profile: Optional[VolumeProfileResult],
) -> ScoreResult:
    is_buy = direction == Direction.BUY
    components: List[ScoreComponent] = []

    # 1. Market Structure - lihat catatan panjang di docstring modul ini:
    # dicek dari BOS/CHoCH BARU (event candle M15 ini), bukan dari trend saja
    # (yang selalu match arah sinyal by construction dan tidak diskriminatif).
    event = m15_structure.event
    matching_events = _BULLISH_STRUCTURE_EVENTS if is_buy else _BEARISH_STRUCTURE_EVENTS
    structure_ok = event in matching_events
    components.append(
        ScoreComponent(
            label="Market Structure",
            valid=structure_ok,
            detail=_STRUCTURE_EVENT_LABELS.get(event, "No Fresh Break"),
            weight=_MARKET_STRUCTURE_WEIGHT,
        )
    )

    # 2. Liquidity
    sweep_direction = "bullish" if is_buy else "bearish"
    liquidity_ok = liquidity_sweep is not None and liquidity_sweep.direction == sweep_direction
    components.append(
        ScoreComponent(
            label="Liquidity",
            valid=liquidity_ok,
            detail="Liquidity Sweep" if liquidity_ok else "No Sweep",
            weight=_LIQUIDITY_WEIGHT,
        )
    )

    # 3. FVG - cari FVG belum-mitigated searah sinyal
    fvg_direction = "bullish" if is_buy else "bearish"
    matching_fvgs = [g for g in (fvgs or []) if g.direction == fvg_direction and not g.mitigated]
    fvg_ok = len(matching_fvgs) > 0
    components.append(
        ScoreComponent(
            label="FVG",
            valid=fvg_ok,
            detail="Valid" if fvg_ok else "None",
            weight=_FVG_WEIGHT,
        )
    )

    # 4. Order Block
    ob_direction = "bullish" if is_buy else "bearish"
    ob_ok = (
        order_block is not None
        and order_block.direction == ob_direction
        and not order_block.mitigated
    )
    if ob_ok:
        ob_detail = "Bullish OB" if is_buy else "Bearish OB"
    else:
        ob_detail = "None"
    components.append(
        ScoreComponent(
            label="Order Block",
            valid=ob_ok,
            detail=ob_detail,
            weight=_ORDER_BLOCK_WEIGHT,
        )
    )

    # 5. Volume Profile
    imbalance = volume_profile.imbalance if volume_profile else "neutral"
    wants = "buy_imbalance" if is_buy else "sell_imbalance"
    vp_ok = imbalance == wants
    vp_label = {
        "buy_imbalance": "Buy Imbalance",
        "sell_imbalance": "Sell Imbalance",
        "neutral": "Neutral",
    }[imbalance]
    components.append(
        ScoreComponent(
            label="Volume Profile",
            valid=vp_ok,
            detail=vp_label,
            weight=_VOLUME_PROFILE_WEIGHT,
        )
    )

    total_weight = sum(c.weight for c in components)
    earned = sum(c.weight for c in components if c.valid)
    score = round((earned / total_weight) * 10, 1) if total_weight else 0.0
    confidence_pct = round((earned / total_weight) * 100) if total_weight else 0

    return ScoreResult(score=score, confidence_pct=confidence_pct, components=components)
