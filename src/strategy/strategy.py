from __future__ import annotations
import logging
from typing import Optional
from src.market.fetch_candles import fetch_closed_candles
from src.models import Signal
from src.storage.d1_client import D1Client
from src.storage.signal_repository import mark_notified,try_reserve,create_trade
from src.strategy.bias_m15 import compute_m15_bias
from src.strategy.trigger_m5 import evaluate_m5_trigger
log=logging.getLogger("strategy")
class MarketDataUnavailable(RuntimeError): pass
def evaluate_market(market_cfg,strategy_cfg,d1)->Optional[Signal]:
    market_id=market_cfg["id"]; symbol=market_cfg["symbol"]; market_type=market_cfg["market"]; exchange=market_cfg["exchange"]; exchange_symbol=market_cfg["exchange_symbol"]
    n=strategy_cfg["minHistoricalCandles"]; lookback=strategy_cfg["swingLookback"]
    m15=fetch_closed_candles(exchange,exchange_symbol,"15m",n)
    if not m15:raise MarketDataUnavailable("M15 candles tidak tersedia")
    m5=fetch_closed_candles(exchange,exchange_symbol,"5m",n)
    if not m5:raise MarketDataUnavailable("M5 candles tidak tersedia")
    bias=compute_m15_bias(m15,lookback,min_structure_confirmation=strategy_cfg.get("minStructureConfirmation",1),structure_break_buffer_pct=strategy_cfg.get("structureBreakBufferPct",0.0))
    signal=evaluate_m5_trigger(market_id,symbol,market_type,bias.bias,bias.structure,m15,m5,strategy_cfg,d1)
    if signal is None:return None
    if not try_reserve(d1,signal):
        log.info("[%s] signal %s sudah diproses",market_id,signal.signal_key); return None
    create_trade(d1,signal)
    return signal
def dispatch_signal(webhook_url,d1,signal):
    from src.notify.notify_discord import send_discord_signal
    ok=send_discord_signal(webhook_url,signal)
    if ok:mark_notified(d1,signal.signal_key)
    else:log.error("[%s] notifikasi gagal, row retained for retry",signal.market_id)
    return ok
