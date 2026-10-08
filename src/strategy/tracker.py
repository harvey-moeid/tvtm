from __future__ import annotations

from datetime import datetime
from src.storage.signal_repository import list_open_trades, update_trade
from src.strategy.exit_policy import resolve_exit
from src.strategy.pnl import r_multiple as _r_multiple, pnl_pct as _pnl_pct


def _to_ms(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def track_trade_row(store, row, candles):
    previously_hit = bool(row.get("tp1_hit"))
    updated_tp1 = False
    subsequent = sorted(
        (c for c in candles if c.open_time > _to_ms(row["entry_time"])),
        key=lambda c: c.open_time,
    )
    for candle in subsequent:
        fields, event = resolve_exit(row, candle)
        if fields:
            update_trade(store, row["id"], fields)
            row.update(fields)
        if event.startswith("CLOSED"):
            return "CLOSED_SL" if event.startswith("CLOSED_SL") else "CLOSED_TP"
        if event == "TP1_HIT":
            updated_tp1 = True
    return "TP1_HIT" if updated_tp1 and not previously_hit else "OPEN"


def track_open_trades(store, candles_by_symbol):
    out = {"checked": 0, "tp1": 0, "closed": 0, "open": 0, "closed_trades": []}
    for stored_row in list_open_trades(store):
        row = dict(stored_row)
        out["checked"] += 1
        result = track_trade_row(store, row, candles_by_symbol.get(row["symbol"], []))
        if result.startswith("CLOSED"):
            out["closed"] += 1
            out["closed_trades"].append(row)
        elif result == "TP1_HIT":
            out["tp1"] += 1
        else:
            out["open"] += 1
    return out
