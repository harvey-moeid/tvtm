from src.models import Direction
from src.strategy.tracker import _r_multiple,track_trade_row
from tests.conftest import FakeD1Client,make_candle
def row(**kw):
    r={"id":1,"signal_key":"s1","symbol":"BTCUSDT","market":"futures","timeframe":"5m","direction":"BUY","entry_price":100.0,"stop_loss":95.0,"take_profit_1":105.0,"take_profit_2":110.0,"entry_time":"2026-01-01T00:00:00Z","status":"OPEN","tp1_hit":0}; r.update(kw); return r
def test_buy_hits_tp1_then_tp2():
    d=FakeD1Client(); d.trades.append(row()); candles=[make_candle(1,100,106,99,104),make_candle(2,105,111,104,110)]
    assert track_trade_row(d,d.trades[0],candles)=="CLOSED_TP2"; assert d.trades[0]["status"]=="CLOSED" and d.trades[0]["pnl_r"]==2.0
def test_buy_hits_sl():
    d=FakeD1Client(); d.trades.append(row()); assert track_trade_row(d,d.trades[0],[make_candle(1,100,101,94,96)])=="CLOSED_SL"
def test_same_candle_sl_and_tp_is_conservative_sl():
    d=FakeD1Client(); d.trades.append(row()); assert track_trade_row(d,d.trades[0],[make_candle(1,100,106,94,100)])=="CLOSED_SL"
def test_r_multiple(): assert _r_multiple(100,95,110,Direction.BUY)==2.0
