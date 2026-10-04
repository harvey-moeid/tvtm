from __future__ import annotations
from datetime import datetime,timedelta,timezone
from typing import Any,Optional
from src.models import Candle
BASE_TIME_MS=1_700_000_000_000
INTERVAL_MS=5*60*1000
def make_candle(idx:int,o:float,h:float,l:float,c:float,v:float=1000.0,interval_ms:int=INTERVAL_MS,base:int=BASE_TIME_MS)->Candle:
    t=base+idx*interval_ms
    return Candle(t,t+interval_ms-1,o,h,l,c,v,True)
from src.storage.r2_store import JSONStore, empty_state

class FakeJSONStore(JSONStore):
    def __init__(self):
        super().__init__(empty_state())

    def backdate_all(self, minutes: int):
        for row in self.rows:
            dt = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            row["created_at"] = (dt - timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")

def seed_notified_row(
    store: FakeJSONStore,
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
        "id": store.state["next_signal_id"],
        "notified": 1,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    row.update(overrides)
    store.state["next_signal_id"] += 1
    store.rows.append(row)
    return row
