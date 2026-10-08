"""Shared, deterministic OHLC exit accounting for live tracker and backtest.

SL takes precedence if both SL and a target are touched in one OHLC candle.
New signals can realize a configured fraction at TP1; old trade records with
no fraction retain their original all-or-nothing accounting.
"""
from __future__ import annotations
from src.models import Direction
from src.strategy.pnl import pnl_pct, r_multiple


def resolve_exit(row: dict, candle):
    """Return (updated_fields, event); fields is empty when nothing happened."""
    direction = Direction(row["direction"])
    entry, sl = float(row["entry_price"]), float(row["stop_loss"])
    tp1, tp2 = row.get("take_profit_1"), row.get("take_profit_2")
    tp1_hit = bool(row.get("tp1_hit", 0))
    fraction = float(row.get("tp1_close_fraction", 0.0))
    if not (0.0 <= fraction <= 1.0):
        raise ValueError("Invalid tp1_close_fraction")

    sl_hit = candle.low <= sl if direction == Direction.BUY else candle.high >= sl
    tp1_now = tp1 is not None and (candle.high >= tp1 if direction == Direction.BUY else candle.low <= tp1)
    tp2_now = tp2 is not None and (candle.high >= tp2 if direction == Direction.BUY else candle.low <= tp2)

    if sl_hit or tp2_now or (tp1_now and tp2 is None):
        exit_price = sl if sl_hit else tp2 if tp2_now else tp1
        partial = fraction if tp1 is not None and (tp1_hit or (tp2_now and tp1_now)) else 0.0
        if tp2 is None:
            partial = 0.0  # Single target: exit entire position at TP1.
        final_fraction = 1.0 - partial
        pnl_r = final_fraction * r_multiple(entry, sl, exit_price, direction)
        pnl_p = final_fraction * pnl_pct(entry, exit_price, direction)
        if partial:
            pnl_r += partial * r_multiple(entry, sl, tp1, direction)
            pnl_p += partial * pnl_pct(entry, tp1, direction)
        reason = ("SL_AFTER_TP1" if tp1_hit else "SL") if sl_hit else ("TP2" if tp2_now else "TP1")
        fields = {
            "status": "CLOSED",
            "exit_price": exit_price,
            "exit_time": candle.candle_time_iso,
            "exit_reason": reason,
            "pnl_pct": pnl_p,
            "pnl_r": pnl_r,
            "closed_notified": 0,
        }
        if partial and not tp1_hit:
            fields.update({"tp1_hit": 1, "tp1_hit_at": candle.candle_time_iso})
        return fields, "CLOSED_" + reason

    if tp1_now and not tp1_hit:
        return {
            "status": "TP1_HIT", "tp1_hit": 1,
            "tp1_hit_at": candle.candle_time_iso,
        }, "TP1_HIT"
    return {}, "OPEN"
