from __future__ import annotations

import logging
from typing import Optional

from src.market.fetch_candles import fetch_closed_candles
from src.models import Signal
from src.storage.signal_repository import (
    create_trade,
    mark_notified,
    try_reserve,
)
from src.strategy.bias_m15 import compute_m15_bias
from src.strategy.trigger_m5 import evaluate_m5_trigger
from src.strategy.tracker import track_open_trades

log = logging.getLogger("strategy")


class MarketDataUnavailable(RuntimeError):
    """Raised when required market candles are unavailable."""


def evaluate_market(
    market_cfg,
    strategy_cfg,
    store,
    webhook_url=None,
) -> Optional[Signal]:
    symbol = market_cfg["symbol"]
    exchange = market_cfg["exchange"]
    exchange_symbol = market_cfg["exchange_symbol"]
    history_size = strategy_cfg["minHistoricalCandles"]
    lookback = strategy_cfg["swingLookback"]

    m15 = fetch_closed_candles(
        exchange,
        exchange_symbol,
        "15m",
        history_size,
    )
    if not m15:
        raise MarketDataUnavailable("M15 candles tidak tersedia")

    m5 = fetch_closed_candles(
        exchange,
        exchange_symbol,
        "5m",
        history_size,
    )
    if not m5:
        raise MarketDataUnavailable("M5 candles tidak tersedia")

    tracking = track_open_trades(store, {symbol: m5})
    if webhook_url and tracking["closed_trades"]:
        from src.notify.notify_discord import send_discord_trade_closed

        for trade in tracking["closed_trades"]:
            send_discord_trade_closed(webhook_url, trade)

    # Limit concurrent *virtual* positions to avoid overlapping exposures.
    open_count = sum(
        row["symbol"] == symbol and row["status"] in ("OPEN", "TP1_HIT")
        for row in store.trades
    )
    if open_count >= strategy_cfg.get("maxOpenTradesPerSymbol", 1):
        return None

    bias = compute_m15_bias(
        m15,
        lookback,
        min_structure_confirmation=strategy_cfg.get(
            "minStructureConfirmation",
            1,
        ),
        structure_break_buffer_pct=strategy_cfg.get(
            "structureBreakBufferPct",
            0.0,
        ),
    )

    signal = evaluate_m5_trigger(
        market_cfg["id"],
        symbol,
        market_cfg["market"],
        bias.bias,
        bias.structure,
        m15,
        m5,
        strategy_cfg,
        store,
    )
    if signal is None:
        return None

    if not try_reserve(store, signal):
        return None

    create_trade(store, signal)
    return signal


def dispatch_signal(webhook_url, store, signal):
    from src.notify.notify_discord import send_discord_signal

    ok = send_discord_signal(webhook_url, signal)
    if ok:
        mark_notified(store, signal.signal_key)

    return ok
