from __future__ import annotations

from src.models import (
    Direction,
    FairValueGap,
    LiquiditySweep,
    OrderBlock,
    StructureEvent,
    StructureResult,
    StructureTrend,
    VolumeProfileResult,
)
from src.strategy.scorer import compute_score


def _structure(trend: StructureTrend, event: StructureEvent = StructureEvent.NONE) -> StructureResult:
    return StructureResult(
        trend=trend, last_swing_high=None, last_swing_low=None, event=event
    )


def test_all_components_valid_gives_max_score():
    structure = _structure(StructureTrend.UP, event=StructureEvent.BOS_BULLISH)
    sweep = LiquiditySweep(direction="bullish", swept_level=100, wick_extreme=99, candle_time=1)
    fvg = FairValueGap(direction="bullish", top=105, bottom=100, formed_at_candle_time=1)
    ob = OrderBlock(
        direction="bullish", top=101, bottom=100, formed_at_candle_time=1,
        structure_event=StructureEvent.BOS_BULLISH,
    )
    vp = VolumeProfileResult(levels=[], poc_price=None, imbalance="buy_imbalance")

    result = compute_score(Direction.BUY, structure, sweep, [fvg], ob, vp)

    assert result.score == 10.0
    assert result.confidence_pct == 100
    assert all(c.valid for c in result.components)


def test_no_components_valid_gives_zero_score():
    # trend DOWN + event NONE: berlawanan arah DAN tidak ada breakout baru sama sekali
    structure = _structure(StructureTrend.DOWN)
    result = compute_score(Direction.BUY, structure, None, [], None, None)
    assert result.score == 0.0
    assert result.confidence_pct == 0
    assert all(not c.valid for c in result.components)


def test_partial_match_computes_weighted_score():
    structure = _structure(StructureTrend.UP, event=StructureEvent.BOS_BULLISH)  # valid, bobot 2.5
    ob = OrderBlock(
        direction="bullish", top=101, bottom=100, formed_at_candle_time=1,
        structure_event=StructureEvent.BOS_BULLISH,
    )  # valid, bobot 2.5
    result = compute_score(Direction.BUY, structure, None, [], ob, None)
    assert result.score == 5.0
    assert result.confidence_pct == 50


def test_mitigated_fvg_and_ob_are_not_counted_valid():
    structure = _structure(StructureTrend.UP, event=StructureEvent.BOS_BULLISH)
    fvg_mitigated = FairValueGap(
        direction="bullish", top=105, bottom=100, formed_at_candle_time=1, mitigated=True
    )
    ob_mitigated = OrderBlock(
        direction="bullish", top=101, bottom=100, formed_at_candle_time=1,
        structure_event=StructureEvent.BOS_BULLISH, mitigated=True,
    )
    result = compute_score(Direction.BUY, structure, None, [fvg_mitigated], ob_mitigated, None)
    fvg_component = next(c for c in result.components if c.label == "FVG")
    ob_component = next(c for c in result.components if c.label == "Order Block")
    assert fvg_component.valid is False
    assert ob_component.valid is False


def test_sell_direction_checks_opposite_conditions():
    structure = _structure(StructureTrend.DOWN, event=StructureEvent.BOS_BEARISH)
    sweep = LiquiditySweep(direction="bearish", swept_level=100, wick_extreme=101, candle_time=1)
    vp = VolumeProfileResult(levels=[], poc_price=None, imbalance="sell_imbalance")

    result = compute_score(Direction.SELL, structure, sweep, [], None, vp)

    ms = next(c for c in result.components if c.label == "Market Structure")
    liq = next(c for c in result.components if c.label == "Liquidity")
    vpc = next(c for c in result.components if c.label == "Volume Profile")
    assert ms.valid and ms.detail == "BOS Bearish"
    assert liq.valid and liq.detail == "Liquidity Sweep"
    assert vpc.valid and vpc.detail == "Sell Imbalance"


def test_range_trend_is_invalid_market_structure_for_either_direction():
    structure = _structure(StructureTrend.RANGE)
    result_buy = compute_score(Direction.BUY, structure, None, [], None, None)
    result_sell = compute_score(Direction.SELL, structure, None, [], None, None)
    ms_buy = next(c for c in result_buy.components if c.label == "Market Structure")
    ms_sell = next(c for c in result_sell.components if c.label == "Market Structure")
    assert not ms_buy.valid
    assert not ms_sell.valid
    assert ms_buy.detail == "No Fresh Break"


def test_choch_counts_same_as_bos_for_market_structure():
    # CHoCH (potensi reversal) dan BOS (continuation) sama-sama breakout BARU
    # searah sinyal, jadi keduanya harus dihitung valid dengan bobot yang sama.
    structure = _structure(StructureTrend.UP, event=StructureEvent.CHOCH_BULLISH)
    result = compute_score(Direction.BUY, structure, None, [], None, None)
    ms = next(c for c in result.components if c.label == "Market Structure")
    assert ms.valid and ms.detail == "CHoCH Bullish"


def test_stale_trend_without_fresh_event_is_not_counted_valid():
    # REGRESSION GUARD: sebelum perbaikan ini, komponen Market Structure hanya
    # mengecek trend UP/DOWN searah direction - yang di jalur produksi
    # (trigger_m5.py) SELALU true karena direction hanya di-set setelah
    # m15_bias sudah dijamin searah trend (lihat bias_m15.py). Ini membuat
    # 2.5/10 poin selalu "gratis" dan tidak pernah diskriminatif.
    #
    # Sekarang: trend UP (searah BUY) TAPI tidak ada breakout M15 baru
    # (event=NONE, trend lama yang sudah berjalan tanpa BOS/CHoCH terbaru)
    # harus dianggap TIDAK valid - membuktikan komponen ini sekarang benar-benar
    # diskriminatif, bukan tautologi dari gate m15_bias sebelumnya.
    structure = _structure(StructureTrend.UP, event=StructureEvent.NONE)
    result = compute_score(Direction.BUY, structure, None, [], None, None)
    ms = next(c for c in result.components if c.label == "Market Structure")
    assert ms.valid is False
    assert ms.detail == "No Fresh Break"
