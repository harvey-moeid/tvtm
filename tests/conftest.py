from __future__ import annotations
from datetime import datetime,timedelta,timezone
from typing import Any,Optional
from src.models import Candle
BASE_TIME_MS=1_700_000_000_000
INTERVAL_MS=5*60*1000
def make_candle(idx:int,o:float,h:float,l:float,c:float,v:float=1000.0,interval_ms:int=INTERVAL_MS,base:int=BASE_TIME_MS)->Candle:
    t=base+idx*interval_ms
    return Candle(t,t+interval_ms-1,o,h,l,c,v,True)
_INSERT_COLUMNS=["signal_key","cooldown_key","symbol","market","timeframe","direction","m15_bias","price","zone_type","zone_level","structure_event","pattern","candle_time","candle_open_time_ms","stop_loss","take_profit_1","take_profit_2","risk_reward_1","risk_reward_2","atr","zone_tolerance_pct_used","confidence_pct","score","checklist_json"]
class FakeD1Client:
    def __init__(self): self.rows=[]; self.trades=[]; self._next_id=1; self._next_trade_id=1
    def backdate_all(self,minutes:int):
        for r in self.rows:
            dt=datetime.fromisoformat(r["created_at"].replace("Z","+00:00")); r["created_at"]=(dt-timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    def query_one(self,sql:str,params:Optional[list]=None):
        p=params or []; s=" ".join(sql.split())
        if "SELECT id, notified FROM signals WHERE signal_key" in s:
            return next(({"id":r["id"],"notified":r["notified"]} for r in self.rows if r["signal_key"]==p[0]),None)
        if "SELECT id FROM signals WHERE cooldown_key" in s:
            return next(({"id":r["id"]} for r in self.rows if r["cooldown_key"]==p[0] and r["notified"]==1),None)
        if "SELECT id FROM signals" in s and "symbol = ?" in s:
            symbol,timeframe,direction,offset_expr=p; minutes=int(offset_expr.strip().split()[0]); cutoff=datetime.now(timezone.utc)+timedelta(minutes=minutes)
            for r in self.rows:
                if r["symbol"]==symbol and r["timeframe"]==timeframe and r["direction"]==direction and r["notified"]==1:
                    created=datetime.fromisoformat(r["created_at"].replace("Z","+00:00"))
                    if created>=cutoff:return {"id":r["id"]}
            return None
        raise NotImplementedError(s)
    def execute(self,sql:str,params:Optional[list]=None):
        p=params or []; s=" ".join(sql.split())
        if s.startswith("INSERT OR IGNORE INTO signals"):
            if any(r["signal_key"]==p[0] for r in self.rows): return {"success":True,"result":[{"meta":{"rows_written":0}}]}
            row=dict(zip(_INSERT_COLUMNS,p)); row.update(id=self._next_id,notified=0,created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")); self._next_id+=1; self.rows.append(row); return {"success":True,"result":[{"meta":{"rows_written":1}}]}
        if s.startswith("UPDATE signals SET notified"):
            n=0
            for r in self.rows:
                if r["signal_key"]==p[0]:r["notified"]=1;n+=1
            return {"success":True,"result":[{"meta":{"rows_written":n}}]}
        if s.startswith("INSERT OR IGNORE INTO trades"):
            if any(r["signal_key"]==p[0] for r in self.trades): return {"success":True,"result":[{"meta":{"rows_written":0}}]}
            keys=["signal_key","symbol","market","timeframe","direction","entry_price","stop_loss","take_profit_1","take_profit_2","entry_time"]
            row=dict(zip(keys,p)); row.update(id=self._next_trade_id,status="OPEN",tp1_hit=0,tp1_hit_at=None,exit_price=None,exit_time=None,exit_reason=None,pnl_pct=None,pnl_r=None); self._next_trade_id+=1; self.trades.append(row); return {"success":True,"result":[{"meta":{"rows_written":1}}]}
        if s.startswith("SELECT * FROM trades"):
            return {"success":True,"result":[{"results":[r for r in self.trades if r["status"] in ("OPEN","TP1_HIT")]}]}
        if s.startswith("UPDATE trades SET"):
            trade_id=p[-1]
            for r in self.trades:
                if r["id"]==trade_id:
                    assignment=s.split("SET ",1)[1].split(" WHERE",1)[0].replace(" updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')","")
                    names=[x.split("=")[0].strip() for x in assignment.split(",") if x.strip()]
                    for k,v in zip(names,p[:-1]): r[k]=v
                    return {"success":True,"result":[{"meta":{"rows_written":1}}]}
            return {"success":True,"result":[{"meta":{"rows_written":0}}]}
        raise NotImplementedError(s)

def seed_notified_row(
    d1: FakeD1Client,
    *,
    cooldown_key: str = "seeded-cooldown-key",
    signal_key: Optional[str] = None,
    symbol: str = "BTCUSDT",
    market: str = "futures",
    timeframe: str = "5m",
    direction: str = "BUY",
    **overrides: Any,
) -> dict:
    """Seed a previously notified signal for cooldown/rate-limit tests."""
    row = {
        "signal_key": signal_key or f"seed:{cooldown_key}",
        "cooldown_key": cooldown_key,
        "symbol": symbol,
        "market": market,
        "timeframe": timeframe,
        "direction": direction,
        "m15_bias": "BULLISH",
        "price": 50000.0,
        "zone_type": "support",
        "zone_level": 50000.0,
        "structure_event": "BOS_BULLISH",
        "pattern": "bullish_pin_bar",
        "candle_time": 0,
        "candle_open_time_ms": 0,
        "stop_loss": None,
        "take_profit_1": None,
        "take_profit_2": None,
        "risk_reward_1": None,
        "risk_reward_2": None,
        "atr": None,
        "zone_tolerance_pct_used": None,
        "confidence_pct": None,
        "score": None,
        "checklist_json": "{}",
        "id": d1._next_id,
        "notified": 1,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    row.update(overrides)
    d1._next_id += 1
    d1.rows.append(row)
    return row
