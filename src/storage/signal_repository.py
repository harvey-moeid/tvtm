"""Signal and trade operations on the R2 JSON state."""
from __future__ import annotations

import json

from src.storage.r2_store import utc_now


def try_reserve(store, signal):
    existing = next((r for r in store.rows if r["signal_key"] == signal.signal_key), None)
    if existing is not None:
        return False  # pending rows are retried once at the start of each run
    row = {
        "id": store.state["next_signal_id"], "signal_key": signal.signal_key,
        "cooldown_key": signal.cooldown_key, "market_id": signal.market_id, "symbol": signal.symbol,
        "market": signal.market, "timeframe": signal.timeframe,
        "direction": signal.direction.value, "m15_bias": signal.m15_bias.value,
        "price": signal.price, "zone_type": signal.zone_type,
        "zone_level": signal.zone_level, "structure_event": signal.structure_event,
        "pattern": signal.pattern, "candle_time": signal.candle_time_iso,
        "candle_open_time_ms": signal.candle_open_time_ms,
        "stop_loss": signal.stop_loss, "take_profit_1": signal.take_profit_1,
        "take_profit_2": signal.take_profit_2, "risk_reward_1": signal.risk_reward_1,
        "risk_reward_2": signal.risk_reward_2, "atr": signal.atr,
        "zone_tolerance_pct_used": signal.zone_tolerance_pct_used,
        "confidence_pct": signal.confidence_pct, "score": signal.score,
        "tp1_close_fraction": signal.tp1_close_fraction,
        "checklist_json": json.dumps([{
            "label": c.label, "valid": c.valid, "detail": c.detail, "weight": c.weight
        } for c in signal.checklist], separators=(",", ":")),
        "notified": 0, "created_at": utc_now(),
    }
    store.state["next_signal_id"] += 1
    store.rows.append(row)
    store.save()
    return True


def mark_notified(store, signal_key):
    row = next(r for r in store.rows if r["signal_key"] == signal_key)
    row["notified"] = 1
    store.save()


def pending_signals(store):
    return [r for r in store.rows if r["notified"] == 0]


def create_trade(store, signal):
    if signal.stop_loss is None or any(r["signal_key"] == signal.signal_key for r in store.trades):
        return False
    now = utc_now()
    store.trades.append({
        "id": store.state["next_trade_id"], "signal_key": signal.signal_key,
        "symbol": signal.symbol, "market": signal.market,
        "timeframe": signal.timeframe, "direction": signal.direction.value,
        "entry_price": signal.price, "stop_loss": signal.stop_loss,
        "take_profit_1": signal.take_profit_1, "take_profit_2": signal.take_profit_2,
        "entry_time": signal.candle_time_iso, "status": "OPEN", "tp1_hit": 0,
        "tp1_close_fraction": signal.tp1_close_fraction,
        "tp1_hit_at": None, "exit_price": None, "exit_time": None,
        "exit_reason": None, "pnl_pct": None, "pnl_r": None,
        "created_at": now, "updated_at": now,
    })
    store.state["next_trade_id"] += 1
    store.save()
    return True


def list_open_trades(store):
    return sorted((r for r in store.trades if r["status"] in ("OPEN", "TP1_HIT")), key=lambda r: r["entry_time"])


def update_trade(store, trade_id, fields):
    allowed = {"status", "tp1_hit", "tp1_hit_at", "exit_price", "exit_time", "exit_reason", "pnl_pct", "pnl_r"}
    row = next(r for r in store.trades if r["id"] == trade_id)
    row.update({k: v for k, v in fields.items() if k in allowed})
    row["updated_at"] = utc_now()
    store.save()
