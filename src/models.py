"""Core dataclasses shared by engine, storage and dashboard."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

class Direction(str, Enum):
    BUY="BUY"; SELL="SELL"
class Bias(str, Enum):
    BULLISH="BULLISH"; BEARISH="BEARISH"; NEUTRAL="NEUTRAL"
class StructureTrend(str, Enum):
    UP="UP"; DOWN="DOWN"; RANGE="RANGE"
class StructureEvent(str, Enum):
    BOS_BULLISH="BOS_BULLISH"; BOS_BEARISH="BOS_BEARISH"; CHOCH_BULLISH="CHOCH_BULLISH"; CHOCH_BEARISH="CHOCH_BEARISH"; NONE="NONE"
class ZoneType(str, Enum):
    SUPPORT="support"; RESISTANCE="resistance"
class PatternType(str, Enum):
    BULLISH_PIN_BAR="bullish_pin_bar"; BEARISH_PIN_BAR="bearish_pin_bar"; BULLISH_ENGULFING="bullish_engulfing"; BEARISH_ENGULFING="bearish_engulfing"; NONE="none"

@dataclass(frozen=True)
class Candle:
    open_time:int; close_time:int; open:float; high:float; low:float; close:float; volume:float; is_closed:bool=True
    @property
    def body(self): return abs(self.close-self.open)
    @property
    def range(self): return max(self.high-self.low,1e-12)
    @property
    def upper_wick(self): return self.high-max(self.open,self.close)
    @property
    def lower_wick(self): return min(self.open,self.close)-self.low
    @property
    def is_bullish(self): return self.close>self.open
    @property
    def is_bearish(self): return self.close<self.open
    @property
    def candle_time_iso(self):
        from datetime import datetime, timezone
        return datetime.fromtimestamp(self.open_time/1000,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@dataclass(frozen=True)
class SwingPoint:
    index:int; price:float; kind:str; candle_time:int
@dataclass
class StructureResult:
    trend:StructureTrend; last_swing_high:Optional[SwingPoint]; last_swing_low:Optional[SwingPoint]; swings:list=field(default_factory=list); event:StructureEvent=StructureEvent.NONE; event_candle_time:Optional[int]=None; event_level:Optional[float]=None
@dataclass
class Zone:
    zone_type:ZoneType; level:float; tolerance_pct:float; source_swing:SwingPoint; structure_event:StructureEvent; structure_event_candle_time:Optional[int]
    @property
    def upper_bound(self): return self.level*(1+self.tolerance_pct/100)
    @property
    def lower_bound(self): return self.level*(1-self.tolerance_pct/100)
    def is_touched_by(self,candle:Candle): return candle.low<=self.upper_bound and candle.high>=self.lower_bound
    @property
    def zone_key(self): return f"{self.zone_type.value}:{round(self.level,6)}:{self.structure_event_candle_time}"
@dataclass
class PatternResult:
    pattern:PatternType; valid:bool; body_range_ratio:float=0.0
@dataclass
class BiasResult:
    bias:Bias; structure:StructureResult
@dataclass(frozen=True)
class FairValueGap:
    direction:str; top:float; bottom:float; formed_at_candle_time:int; mitigated:bool=False
    @property
    def mid(self): return (self.top+self.bottom)/2
    @property
    def size_pct(self): return (self.top-self.bottom)/self.bottom*100 if self.bottom else 0.0
    def is_touched_by(self,candle:Candle): return candle.low<=self.top and candle.high>=self.bottom
@dataclass(frozen=True)
class OrderBlock:
    direction:str; top:float; bottom:float; formed_at_candle_time:int; structure_event:StructureEvent=StructureEvent.NONE; mitigated:bool=False
    @property
    def mid(self): return (self.top+self.bottom)/2
    def is_touched_by(self,candle:Candle): return candle.low<=self.top and candle.high>=self.bottom
@dataclass(frozen=True)
class LiquiditySweep:
    direction:str; swept_level:float; wick_extreme:float; candle_time:int
@dataclass(frozen=True)
class VolumeProfileLevel:
    price_low:float; price_high:float; buy_volume:float; sell_volume:float
    @property
    def total_volume(self): return self.buy_volume+self.sell_volume
    @property
    def mid(self): return (self.price_low+self.price_high)/2
@dataclass
class VolumeProfileResult:
    levels:List[VolumeProfileLevel]=field(default_factory=list); poc_price:Optional[float]=None; imbalance:str="neutral"
@dataclass
class ScoreComponent:
    label:str; valid:bool; detail:str; weight:float=1.0
@dataclass
class ScoreResult:
    score:float; confidence_pct:float; components:List[ScoreComponent]=field(default_factory=list)

@dataclass
class Signal:
    market_id:str; symbol:str; market:str; timeframe:str; direction:Direction; m15_bias:Bias; price:float; zone_type:str; zone_level:float; structure_event:str; pattern:str; candle_time_iso:str; candle_open_time_ms:int; signal_key:str; cooldown_key:str
    stop_loss:Optional[float]=None; take_profit_1:Optional[float]=None; take_profit_2:Optional[float]=None; risk_reward_1:Optional[float]=None; risk_reward_2:Optional[float]=None; atr:Optional[float]=None; zone_tolerance_pct_used:Optional[float]=None
    confidence_pct:Optional[float]=None; score:Optional[float]=None; checklist:List[ScoreComponent]=field(default_factory=list)
    def to_payload(self):
        return {"symbol":self.symbol,"market":self.market,"timeframe":self.timeframe,"direction":self.direction.value,"m15_bias":self.m15_bias.value,"price":self.price,"zone":{"type":self.zone_type,"level":self.zone_level},"structure_event":self.structure_event,"pattern":self.pattern,"candle_time":self.candle_time_iso,"risk":{"stop_loss":self.stop_loss,"take_profit_1":self.take_profit_1,"take_profit_2":self.take_profit_2,"risk_reward_1":self.risk_reward_1,"risk_reward_2":self.risk_reward_2,"atr":self.atr},"scoring":{"confidence_pct":self.confidence_pct,"score":self.score,"checklist":[{"label":c.label,"valid":c.valid,"detail":c.detail} for c in self.checklist]}}

@dataclass
class Trade:
    signal_key:str; symbol:str; market:str; timeframe:str; direction:Direction; entry_price:float; stop_loss:float; take_profit_1:Optional[float]; take_profit_2:Optional[float]; entry_time:str
    status:str="OPEN"; tp1_hit:bool=False; tp1_hit_at:Optional[str]=None; exit_price:Optional[float]=None; exit_time:Optional[str]=None; exit_reason:Optional[str]=None; pnl_pct:Optional[float]=None; pnl_r:Optional[float]=None
