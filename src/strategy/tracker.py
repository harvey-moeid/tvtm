"""Track open trades against closed candles and persist TP/SL outcomes."""
from __future__ import annotations
from datetime import datetime,timezone
from src.models import Direction
from src.storage.signal_repository import list_open_trades,update_trade
def _r_multiple(entry,stop,exit_price,direction):
    risk=abs(entry-stop)
    if risk<=0:return 0.0
    return (exit_price-entry)/risk if direction==Direction.BUY else (entry-exit_price)/risk
def _pnl_pct(entry,exit_price,direction):
    signed=(exit_price-entry) if direction==Direction.BUY else (entry-exit_price)
    return signed/entry*100 if entry else 0.0
def _to_ms(iso): return int(datetime.fromisoformat(iso.replace("Z","+00:00")).timestamp()*1000)
def track_trade_row(d1,row,candles):
    direction=Direction(row["direction"]); sl=row["stop_loss"]; tp1=row.get("take_profit_1"); tp2=row.get("take_profit_2"); hit=bool(row.get("tp1_hit"))
    candles=sorted((c for c in candles if c.open_time>_to_ms(row["entry_time"])),key=lambda c:c.open_time)
    for c in candles:
        sl_hit=(c.low<=sl) if direction==Direction.BUY else (c.high>=sl)
        tp1_now=(tp1 is not None and c.high>=tp1) if direction==Direction.BUY else (tp1 is not None and c.low<=tp1)
        tp2_now=(tp2 is not None and c.high>=tp2) if direction==Direction.BUY else (tp2 is not None and c.low<=tp2)
        if sl_hit:
            update_trade(d1,row["id"],{"status":"CLOSED","exit_price":sl,"exit_time":c.candle_time_iso,"exit_reason":"SL_AFTER_TP1" if hit else "SL","pnl_pct":_pnl_pct(row["entry_price"],sl,direction),"pnl_r":_r_multiple(row["entry_price"],sl,sl,direction)}); return "CLOSED_SL"
        if tp2_now:
            update_trade(d1,row["id"],{"status":"CLOSED","exit_price":tp2,"exit_time":c.candle_time_iso,"exit_reason":"TP2","pnl_pct":_pnl_pct(row["entry_price"],tp2,direction),"pnl_r":_r_multiple(row["entry_price"],sl,tp2,direction)}); return "CLOSED_TP2"
        if tp1_now and not hit:
            update_trade(d1,row["id"],{"status":"TP1_HIT","tp1_hit":1,"tp1_hit_at":c.candle_time_iso}); hit=True
    return "TP1_HIT" if hit and not row.get("tp1_hit") else "OPEN"
