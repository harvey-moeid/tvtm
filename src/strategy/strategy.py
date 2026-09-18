"""
Orkestrasi per market: fetch M15 + M5 -> bias -> trigger -> idempotency -> notify.
Setiap market dievaluasi terisolasi (PRD §20): 1 market gagal tidak boleh
menghentikan evaluasi market lain.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.market.fetch_candles import fetch_closed_candles
from src.models import Signal
from src.storage.d1_client import D1Client
from src.storage.signal_repository import mark_notified, try_reserve
from src.strategy.bias_m15 import compute_m15_bias
from src.strategy.trigger_m5 import evaluate_m5_trigger

log = logging.getLogger("strategy")


def evaluate_market(market_cfg: dict, strategy_cfg: dict, d1: D1Client) -> Optional[Signal]:
    market_id = market_cfg["id"]
    symbol = market_cfg["symbol"]
    market_type = market_cfg["market"]
    exchange = market_cfg["exchange"]
    exchange_symbol = market_cfg["exchange_symbol"]
    min_history = strategy_cfg["minHistoricalCandles"]
    swing_lookback = strategy_cfg["swingLookback"]

    m15_candles = fetch_closed_candles(exchange, exchange_symbol, "15m", min_history)
    if not m15_candles:
        log.warning("[%s] skip: M15 candles tidak tersedia", market_id)
        return None

    m5_candles = fetch_closed_candles(exchange, exchange_symbol, "5m", min_history)
    if not m5_candles:
        log.warning("[%s] skip: M5 candles tidak tersedia", market_id)
        return None

    bias_result = compute_m15_bias(m15_candles, swing_lookback)
    log.info(
        "[%s] M15 bias=%s trend=%s event=%s",
        market_id, bias_result.bias.value, bias_result.structure.trend.value,
        bias_result.structure.event.value,
    )

    signal = evaluate_m5_trigger(
        market_id=market_id,
        symbol=symbol,
        market=market_type,
        m15_bias=bias_result.bias,
        m15_structure=bias_result.structure,
        m5_candles=m5_candles,
        cfg=strategy_cfg,
        d1=d1,
    )
    if signal is None:
        log.info("[%s] tidak ada trigger valid pada run ini", market_id)
        return None

    if not try_reserve(d1, signal):
        log.info("[%s] signal %s sudah pernah diproses (idempotent skip)", market_id, signal.signal_key)
        return None

    return signal


def dispatch_signal(webhook_url: str, d1: D1Client, signal: Signal) -> bool:
    from src.notify.notify_discord import send_discord_signal

    ok = send_discord_signal(webhook_url, signal)
    if ok:
        mark_notified(d1, signal.signal_key)
        log.info("[%s] notifikasi terkirim: %s", signal.market_id, signal.signal_key)
    else:
        log.error(
            "[%s] gagal kirim notifikasi, row tetap notified=0 utk retry run berikutnya: %s",
            signal.market_id, signal.signal_key,
        )
    return ok
