from src.models import Direction
from src.strategy.tracker import _r_multiple,track_trade_row
from tests.conftest import FakeJSONStore,make_candle
def row(**kw):
    r={"id":1,"signal_key":"s1","symbol":"BTCUSDT","market":"futures","timeframe":"5m","direction":"BUY","entry_price":100.0,"stop_loss":95.0,"take_profit_1":105.0,"take_profit_2":110.0,"entry_time":"2023-11-14T22:13:20Z","status":"OPEN","tp1_hit":0}; r.update(kw); return r
def test_buy_hits_tp1_then_tp2():
    d=FakeJSONStore(); d.trades.append(row()); candles=[make_candle(1,100,106,99,104),make_candle(2,105,111,104,110)]
    assert track_trade_row(d,d.trades[0],candles)=="CLOSED_TP2"; assert d.trades[0]["status"]=="CLOSED" and d.trades[0]["pnl_r"]==2.0
def test_buy_hits_sl():
    d=FakeJSONStore(); d.trades.append(row()); assert track_trade_row(d,d.trades[0],[make_candle(1,100,101,94,96)])=="CLOSED_SL"
def test_same_candle_sl_and_tp_is_conservative_sl():
    d=FakeJSONStore(); d.trades.append(row()); assert track_trade_row(d,d.trades[0],[make_candle(1,100,106,94,100)])=="CLOSED_SL"
def test_r_multiple(): assert _r_multiple(100,95,110,Direction.BUY)==2.0


def test_tp1_partial_then_sl_credits_realized_gain():
    d = FakeJSONStore()
    trade = row(tp1_close_fraction=0.5)
    d.trades.append(trade)
    candles = [make_candle(1, 100, 106, 99, 104), make_candle(2, 104, 104, 94, 95)]
    assert track_trade_row(d, trade, candles) == "CLOSED_SL"
    assert trade["exit_reason"] == "SL_AFTER_TP1"
    assert trade["pnl_r"] == 0.0  # 50% at +1R, 50% at -1R


def test_single_target_closes_at_tp1():
    d = FakeJSONStore()
    trade = row(take_profit_2=None, tp1_close_fraction=0.5)
    d.trades.append(trade)
    assert track_trade_row(d, trade, [make_candle(1, 100, 106, 99, 105)]) == "CLOSED_TP1"
    assert trade["status"] == "CLOSED"
    assert trade["exit_reason"] == "TP1"
    assert trade["pnl_r"] == 1.0


def test_tp1_partial_then_tp2_is_weighted():
    d = FakeJSONStore()
    trade = row(tp1_close_fraction=0.5)
    d.trades.append(trade)
    candles = [make_candle(1, 100, 106, 99, 105), make_candle(2, 105, 111, 104, 110)]
    assert track_trade_row(d, trade, candles) == "CLOSED_TP2"
    assert trade["pnl_r"] == 1.5  # 50% x 1R + 50% x 2R


def test_tp2_same_candle_as_tp1_respects_partial_allocation():
    d = FakeJSONStore()
    trade = row(tp1_close_fraction=0.5)
    d.trades.append(trade)
    assert track_trade_row(d, trade, [make_candle(1, 100, 111, 99, 110)]) == "CLOSED_TP2"
    assert trade["pnl_r"] == 1.5
