"""
Ringkasan performa dari daftar BacktestTrade - dipakai scripts/backtest.py
buat cetak laporan, dan bisa dipakai ulang utk parameter sweep/tuning manual
di masa depan (mis. membandingkan minRiskRewardRatio atau bobot scorer yang
berbeda-beda dari cfg yang sama, dijalankan lewat run_backtest berkali-kali).

Semua trade OPEN/TP1_HIT (belum resolve final) DIKELUARKAN dari perhitungan
win-rate/expectancy/drawdown - ini murni performa trade yang SUDAH selesai,
supaya tidak bias oleh posisi yang masih menggantung di akhir data historis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from src.backtest.simulator import BacktestTrade


@dataclass
class BacktestMetrics:
    total_signals: int
    closed_trades: int
    open_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    total_r: float
    avg_r: float
    expectancy_r: float
    profit_factor: Optional[float]
    max_drawdown_r: float
    avg_pnl_pct: float
    by_direction: dict = field(default_factory=dict)
    by_pattern: dict = field(default_factory=dict)
    by_exit_reason: dict = field(default_factory=dict)


def _breakdown(trades: List[BacktestTrade], key_fn: Callable[[BacktestTrade], str]) -> dict:
    out: dict = {}
    for t in trades:
        if t.pnl_r is None:
            continue
        k = key_fn(t)
        b = out.setdefault(k, {"count": 0, "wins": 0, "total_r": 0.0})
        b["count"] += 1
        b["total_r"] += t.pnl_r
        if t.pnl_r > 0:
            b["wins"] += 1
    for b in out.values():
        b["win_rate_pct"] = round(b["wins"] / b["count"] * 100, 1) if b["count"] else 0.0
        b["avg_r"] = round(b["total_r"] / b["count"], 3) if b["count"] else 0.0
        b["total_r"] = round(b["total_r"], 3)
    return out


def compute_metrics(trades: List[BacktestTrade]) -> BacktestMetrics:
    closed = [t for t in trades if t.status == "CLOSED" and t.pnl_r is not None]
    open_count = sum(1 for t in trades if t.status != "CLOSED")

    wins = [t for t in closed if t.pnl_r > 0]
    losses = [t for t in closed if t.pnl_r <= 0]

    total_r = sum(t.pnl_r for t in closed)
    avg_r = total_r / len(closed) if closed else 0.0
    win_rate = len(wins) / len(closed) * 100 if closed else 0.0

    gross_win = sum(t.pnl_r for t in wins)
    gross_loss = abs(sum(t.pnl_r for t in losses))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else None

    avg_win_r = gross_win / len(wins) if wins else 0.0
    avg_loss_r = gross_loss / len(losses) if losses else 0.0
    loss_rate = 1 - (win_rate / 100)
    # Expectancy per trade dlm satuan R: (win_rate * avg_win) - (loss_rate * avg_loss)
    expectancy_r = (win_rate / 100) * avg_win_r - loss_rate * avg_loss_r

    # Max drawdown dari kurva ekuitas kumulatif (satuan R), diurutkan by exit_time.
    ordered = sorted(closed, key=lambda t: t.exit_time or "")
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in ordered:
        equity += t.pnl_r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    avg_pnl_pct = sum(t.pnl_pct for t in closed) / len(closed) if closed else 0.0

    return BacktestMetrics(
        total_signals=len(trades),
        closed_trades=len(closed),
        open_trades=open_count,
        wins=len(wins),
        losses=len(losses),
        win_rate_pct=round(win_rate, 2),
        total_r=round(total_r, 3),
        avg_r=round(avg_r, 3),
        expectancy_r=round(expectancy_r, 3),
        profit_factor=round(profit_factor, 3) if profit_factor is not None else None,
        max_drawdown_r=round(max_dd, 3),
        avg_pnl_pct=round(avg_pnl_pct, 3),
        by_direction=_breakdown(closed, lambda t: t.signal.direction.value),
        by_pattern=_breakdown(closed, lambda t: t.signal.pattern),
        by_exit_reason=_breakdown(closed, lambda t: t.exit_reason or "?"),
    )
