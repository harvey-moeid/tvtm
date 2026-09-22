"""Track open trades against closed candles and record TP/SL lifecycle."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Iterable
from src.models import Candle, Direction
from src.storage.d1_client import D1Client
from src.storage.signal_repository import list_open_trades, update_trade

def _now_iso(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _hit(direction:Direction,candle:Candle,level:float)->bool:
    return candle.low <= level <= candle.high

def _pnl(entry:float,exit_price:float,direction:Direction)->tuple[float,float]:
    signed=(exit_price-entry) if direction==Direction.BUY else (entry-exit_price)
    pct=signed/entry*100 if entry else 0.0
    return pct, signed/abs(entry-exit_price) if False else 0.0

def _r_multiple(entry:float,stop:float,exit_price:float,direction:Direction)->float:
    risk=abs(entry-stop)
    if risk<=0:return 0.0
    return ((exit_price-entry)/risk if direction==Direction.BUY else (entry-exit_price)/risk)

def track_trade_row(d1:D1Client,row:dict,candles:Iterable[Candle])->str:
    direction=Direction(row["direction"])
    candles=sorted((c for c in candles if c.open_time > _to_ms(row["entry_time"])),key=lambda c:c.open_time)
    tp1=row.get("take_profit_1"); tp2=row.get("take_profit_2"); sl=row["stop_loss"]
    tp1_hit=bool(row.get("tp1_hit"))
    for candle in candles:
        if direction==Direction.BUY:
            sl_hit=candle.low<=sl; tp1_now=tp1 is not None and candle.high>=tp1; tp2_now=tp2 is not None and candle.high>=tp2
        else:
            sl_hit=candle.high>=sl; tp1_now=tp1 is not None and candle.low<=tp1; tp2_now=tp2 is not None and candle.low<=tp2
        # If both sides occur in one candle, choose SL first (conservative,
        # because OHLC alone cannot reveal intrabar order).
        if sl_hit:
            price=sl
            pct,_=_pnl(row["entry_price"],price,direction)
            r=_r_multiple(row["entry_price"],sl,price,direction)
            update_trade(d1,row["id"],{"status":"CLOSED","exit_price":price,"exit_time":candle.candle_time_iso,"exit_reason":"SL_AFTER_TP1" if tp1_hit else "SL","pnl_pct":pct,"pnl_r":r})
            return "CLOSED_SL"
        if tp2_now:
            price=tp2
            pct,_=_pnl(row["entry_price"],price,direction)
            r=_r_multiple(row["entry_price"],sl,price,direction)
            update_trade(d1,row["id"],{"status":"CLOSED","exit_price":price,"exit_time":candle.candle_time_iso,"exit_reason":"TP2","pnl_pct":pct,"pnl_r":r})
            return "CLOSED_TP2"
        if tp1_now and not tp1_hit:
            update_trade(d1,row["id"],{"status":"TP1_HIT","tp1_hit":1,"tp1_hit_at":candle.candle_time_iso})
            tp1_hit=True
    return "OPEN"

def _to_ms(iso:str)->int:
    dt=datetime.fromisoformat(iso.replace("Z","+00:00"))
    return int(dt.timestamp()*1000)

def track_open_trades(d1:D1Client,candles_by_symbol:dict[str,list[Candle]])->dict[str,int]:
    summary={"checked":0,"tp1":0,"closed":0,"open":0}
    for row in list_open_trades(d1):
        summary["checked"]+=1
        result=track_trade_row(d1,row,candles_by_symbol.get(row["symbol"],[]))
        if result=="CLOSED_SL" or result=="CLOSED_TP2": summary["closed"]+=1
        elif result=="TP1_HIT": summary["tp1"]+=1
        else: summary["open"]+=1
    return summary
