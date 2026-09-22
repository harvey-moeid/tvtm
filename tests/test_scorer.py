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


def _structure(trend: StructureTrend) -> StructureResult:
    return StructureResult(trend=trend, last_swing_high=None, last_swing_low=None)


def test_all_components_valid_gives_max_score():
    structure = _structure(StructureTrend.UP)
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
    structure = _structure(StructureTrend.DOWN)  # berlawanan dengan direction BUY
    result = compute_score(Direction.BUY, structure, None, [], None, None)
    assert result.score == 0.0
    assert result.confidence_pct == 0
    assert all(not c.valid for c in result.components)


def test_partial_match_computes_weighted_score():
    structure = _structure(StructureTrend.UP)  # valid, bobot 2.5
    ob = OrderBlock(
        direction="bullish", top=101, bottom=100, formed_at_candle_time=1,
        structure_event=StructureEvent.BOS_BULLISH,
    )  # valid, bobot 2.5
    result = compute_score(Direction.BUY, structure, None, [], ob, None)
    assert result.score == 5.0
    assert result.confidence_pct == 50


def test_mitigated_fvg_and_ob_are_not_counted_valid():
    structure = _structure(StructureTrend.UP)
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
    structure = _structure(StructureTrend.DOWN)
    sweep = LiquiditySweep(direction="bearish", swept_level=100, wick_extreme=101, candle_time=1)
    vp = VolumeProfileResult(levels=[], poc_price=None, imbalance="sell_imbalance")

    result = compute_score(Direction.SELL, structure, sweep, [], None, vp)

    ms = next(c for c in result.components if c.label == "Market Structure")
    liq = next(c for c in result.components if c.label == "Liquidity")
    vpc = next(c for c in result.components if c.label == "Volume Profile")
    assert ms.valid and ms.detail == "Downtrend"
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
    assert ms_buy.detail == "Range"
