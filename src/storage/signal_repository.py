from __future__ import annotations
import json
from src.models import Signal
from src.storage.d1_client import D1Client
_INSERT_SQL="""INSERT OR IGNORE INTO signals
(signal_key,cooldown_key,symbol,market,timeframe,direction,m15_bias,price,zone_type,zone_level,structure_event,pattern,candle_time,candle_open_time_ms,stop_loss,take_profit_1,take_profit_2,risk_reward_1,risk_reward_2,atr,zone_tolerance_pct_used,confidence_pct,score,checklist_json)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
def try_reserve(d1,signal):
    existing=d1.query_one("SELECT id, notified FROM signals WHERE signal_key = ? LIMIT 1",[signal.signal_key])
    if existing is not None:return existing.get("notified")==0
    data=d1.execute(_INSERT_SQL,[signal.signal_key,signal.cooldown_key,signal.symbol,signal.market,signal.timeframe,signal.direction.value,signal.m15_bias.value,signal.price,signal.zone_type,signal.zone_level,signal.structure_event,signal.pattern,signal.candle_time_iso,signal.candle_open_time_ms,signal.stop_loss,signal.take_profit_1,signal.take_profit_2,signal.risk_reward_1,signal.risk_reward_2,signal.atr,signal.zone_tolerance_pct_used,signal.confidence_pct,signal.score,json.dumps([{"label":c.label,"valid":c.valid,"detail":c.detail,"weight":c.weight} for c in signal.checklist],separators=(",",":"))])
    return bool(data.get("result",[{}])[0].get("meta",{}).get("rows_written",data.get("result",[{}])[0].get("meta",{}).get("changes",0)))
def mark_notified(d1,signal_key): d1.execute("UPDATE signals SET notified=1 WHERE signal_key=?",[signal_key])
def create_trade(d1,signal):
    if signal.stop_loss is None:return False
    data=d1.execute("""INSERT OR IGNORE INTO trades
    (signal_key,symbol,market,timeframe,direction,entry_price,stop_loss,take_profit_1,take_profit_2,entry_time)
    VALUES (?,?,?,?,?,?,?,?,?,?)""",[signal.signal_key,signal.symbol,signal.market,signal.timeframe,signal.direction.value,signal.price,signal.stop_loss,signal.take_profit_1,signal.take_profit_2,signal.candle_time_iso])
    return bool(data.get("result",[{}])[0].get("meta",{}).get("rows_written",data.get("result",[{}])[0].get("meta",{}).get("changes",0)))
def list_open_trades(d1):
    data=d1.execute("SELECT * FROM trades WHERE status IN ('OPEN','TP1_HIT') ORDER BY entry_time ASC")
    return data.get("result",[{}])[0].get("results",[])
def update_trade(d1,trade_id,fields):
    allowed={"status","tp1_hit","tp1_hit_at","exit_price","exit_time","exit_reason","pnl_pct","pnl_r"}
    fields={k:v for k,v in fields.items() if k in allowed}
    if not fields:return
    assignments=", ".join(f"{k}=?" for k in fields)
    d1.execute(f"UPDATE trades SET {assignments}, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",list(fields.values())+[trade_id])
