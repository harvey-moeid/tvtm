from __future__ import annotations

from src.backtest.metrics import compute_metrics
from src.backtest.simulator import BacktestTrade
from src.models import Direction, Signal


def _signal(direction=Direction.BUY, pattern="bullish_pin_bar") -> Signal:
    return Signal(
        market_id="BTCUSDT_FUTURES", symbol="BTCUSDT", market="futures", timeframe="5m",
        direction=direction, m15_bias="BULLISH", price=100.0, zone_type="support",
        zone_level=99.0, structure_event="BOS_BULLISH", pattern=pattern,
        candle_time_iso="2024-01-01T00:00:00Z", candle_open_time_ms=0,
        signal_key="k", cooldown_key="ck",
    )


def _closed_trade(pnl_r: float, exit_time: str, exit_reason: str = "TP2", pattern="bullish_pin_bar") -> BacktestTrade:
    t = BacktestTrade(
        signal=_signal(pattern=pattern), entry_time="2024-01-01T00:00:00Z", entry_price=100.0,
        stop_loss=99.0, take_profit_1=101.5, take_profit_2=103.0,
    )
    t.status = "CLOSED"
    t.exit_reason = exit_reason
    t.exit_time = exit_time
    t.pnl_r = pnl_r
    t.pnl_pct = pnl_r  # nilai persis tidak penting utk tes ini
    return t


def test_win_rate_and_totals_with_mixed_outcomes():
    trades = [
        _closed_trade(3.0, "2024-01-01T01:00:00Z"),   # win
        _closed_trade(-1.0, "2024-01-01T02:00:00Z", exit_reason="SL"),  # loss
        _closed_trade(1.5, "2024-01-01T03:00:00Z"),   # win
        _closed_trade(-1.0, "2024-01-01T04:00:00Z", exit_reason="SL"),  # loss
    ]
    m = compute_metrics(trades)

    assert m.closed_trades == 4
    assert m.wins == 2
    assert m.losses == 2
    assert m.win_rate_pct == 50.0
    assert m.total_r == 2.5  # 3.0 - 1.0 + 1.5 - 1.0
    assert m.avg_r == 0.625
    assert m.profit_factor == round((3.0 + 1.5) / (1.0 + 1.0), 3)


def test_open_trades_excluded_from_win_rate_but_counted_separately():
    open_trade = BacktestTrade(
        signal=_signal(), entry_time="2024-01-01T00:00:00Z", entry_price=100.0,
        stop_loss=99.0, take_profit_1=101.5, take_profit_2=103.0,
    )  # status default OPEN, pnl_r=None
    closed = _closed_trade(2.0, "2024-01-01T01:00:00Z")

    m = compute_metrics([open_trade, closed])
    assert m.total_signals == 2
    assert m.closed_trades == 1
    assert m.open_trades == 1
    assert m.wins == 1
    assert m.win_rate_pct == 100.0


def test_max_drawdown_from_equity_curve():
    # Kurva ekuitas kumulatif (R): +2 -> +1 (dd=1) -> -1.5 (dd=3.5 dari peak 2) -> +0.5
    trades = [
        _closed_trade(2.0, "2024-01-01T01:00:00Z"),
        _closed_trade(-1.0, "2024-01-01T02:00:00Z", exit_reason="SL"),
        _closed_trade(-1.5, "2024-01-01T03:00:00Z", exit_reason="SL"),
        _closed_trade(2.0, "2024-01-01T04:00:00Z"),
    ]
    m = compute_metrics(trades)
    # peak=2.0 (setelah trade1), equity terendah setelahnya = 2-1-1.5=-0.5 -> dd=2.5
    assert m.max_drawdown_r == 2.5


def test_profit_factor_is_none_when_no_losses():
    trades = [_closed_trade(1.0, "2024-01-01T01:00:00Z"), _closed_trade(2.0, "2024-01-01T02:00:00Z")]
    m = compute_metrics(trades)
    assert m.profit_factor is None
    assert m.losses == 0


def test_breakdown_by_pattern_and_exit_reason():
    trades = [
        _closed_trade(1.0, "2024-01-01T01:00:00Z", exit_reason="TP2", pattern="bullish_pin_bar"),
        _closed_trade(-1.0, "2024-01-01T02:00:00Z", exit_reason="SL", pattern="bullish_pin_bar"),
        _closed_trade(1.0, "2024-01-01T03:00:00Z", exit_reason="TP2", pattern="bullish_engulfing"),
    ]
    m = compute_metrics(trades)
    assert m.by_pattern["bullish_pin_bar"]["count"] == 2
    assert m.by_pattern["bullish_engulfing"]["count"] == 1
    assert m.by_exit_reason["SL"]["count"] == 1
    assert m.by_exit_reason["TP2"]["count"] == 2
