from src.models import Bias,Direction,Signal
from src.storage.signal_repository import create_trade,try_reserve
from tests.conftest import FakeD1Client
def signal():
    return Signal("BTCUSDT_FUTURES","BTCUSDT","futures","5m",Direction.BUY,Bias.BULLISH,100.0,"support",99.0,"BOS_BULLISH","bullish_pin_bar","2026-01-01T00:00:00Z",1767225600000,"s1","c1",95.0,105.0,110.0,1.5,3.0,1.0,0.1,80,8.0,[])
def test_reserve_persists_scoring_fields():
    d=FakeD1Client(); s=signal(); assert try_reserve(d,s) is True
    assert d.rows[0]["confidence_pct"]==80 and d.rows[0]["score"]==8.0 and d.rows[0]["checklist_json"]=="[]"
def test_create_trade_is_idempotent():
    d=FakeD1Client(); s=signal(); assert create_trade(d,s) is True; assert create_trade(d,s) is False; assert len(d.trades)==1
