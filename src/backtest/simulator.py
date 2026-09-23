"""
Walk-forward backtest simulator.

Mengeksekusi ULANG persis alur produksi (compute_m15_bias -> evaluate_m5_trigger)
candle demi candle secara historis, TANPA menyentuh D1/Discord asli:
cooldown & rate-limit disimulasikan lewat InMemorySignalStore dengan jam
SIMULASI (bukan wall-clock - lihat docstring src/backtest/store.py), dan
setiap sinyal yang lolos langsung dianggap "notified" seperti di produksi.

Posisi yang terbuka disimulasikan maju candle-demi-candle M5 berikutnya pakai
r_multiple()/pnl_pct() dari src/strategy/pnl.py - fungsi PURE yang SAMA PERSIS
dipakai src/strategy/tracker.py untuk live position tracking, supaya hasil
backtest benar-benar merepresentasikan apa yang akan terjadi kalau strategi
ini dijalankan live, bukan rumus PnL yang mendadak berbeda.

SL dicek lebih dulu tiap candle kalau SL & target sama-sama tersentuh di
candle yang sama (OHLC tidak mengungkap urutan intrabar) - identik dengan
asumsi konservatif di tracker.py.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from src.backtest.store import InMemorySignalStore
from src.models import Candle, Direction, Signal
from src.strategy.bias_m15 import compute_m15_bias
from src.strategy.pnl import pnl_pct, r_multiple
from src.strategy.trigger_m5 import evaluate_m5_trigger


@dataclass
class BacktestTrade:
    signal: Signal
    entry_time: str
    entry_price: float
    stop_loss: float
    take_profit_1: Optional[float]
    take_profit_2: Optional[float]
    status: str = "OPEN"  # OPEN | TP1_HIT | CLOSED
    tp1_hit: bool = False
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    exit_reason: Optional[str] = None
    pnl_pct: Optional[float] = None
    pnl_r: Optional[float] = None


def _resolve_trade_one_candle(trade: BacktestTrade, c: Candle) -> None:
    direction = trade.signal.direction
    sl, tp1, tp2 = trade.stop_loss, trade.take_profit_1, trade.take_profit_2

    sl_hit = (c.low <= sl) if direction == Direction.BUY else (c.high >= sl)
    tp1_now = (tp1 is not None) and ((c.high >= tp1) if direction == Direction.BUY else (c.low <= tp1))
    tp2_now = (tp2 is not None) and ((c.high >= tp2) if direction == Direction.BUY else (c.low <= tp2))

    if sl_hit:
        trade.status = "CLOSED"
        trade.exit_price = sl
        trade.exit_time = c.candle_time_iso
        trade.exit_reason = "SL_AFTER_TP1" if trade.tp1_hit else "SL"
        trade.pnl_pct = pnl_pct(trade.entry_price, sl, direction)
        trade.pnl_r = r_multiple(trade.entry_price, sl, sl, direction)
        return
    if tp2_now:
        trade.status = "CLOSED"
        trade.exit_price = tp2
        trade.exit_time = c.candle_time_iso
        trade.exit_reason = "TP2"
        trade.pnl_pct = pnl_pct(trade.entry_price, tp2, direction)
        trade.pnl_r = r_multiple(trade.entry_price, sl, tp2, direction)
        return
    if tp1_now and not trade.tp1_hit:
        trade.tp1_hit = True
        trade.status = "TP1_HIT"


def run_backtest(
    market_id: str,
    symbol: str,
    market: str,
    m15_candles: List[Candle],
    m5_candles: List[Candle],
    cfg: dict,
) -> List[BacktestTrade]:
    """Replay m15_candles/m5_candles (ASCENDING open_time, HANYA candle closed)
    lewat strategi live. cfg sama persis dengan yang dipakai produksi
    (src.config_loader.load_strategy_config), boleh dioverride utk keperluan
    parameter sweep/tuning."""
    history_size = cfg["minHistoricalCandles"]
    lookback = cfg["swingLookback"]
    min_struct_conf = cfg.get("minStructureConfirmation", 1)
    break_buffer = cfg.get("structureBreakBufferPct", 0.0)

    m15_close_times = [c.close_time for c in m15_candles]
    store = InMemorySignalStore()
    trades: List[BacktestTrade] = []
    open_trades: List[BacktestTrade] = []

    start_idx = history_size
    if start_idx >= len(m5_candles):
        return trades

    for i in range(start_idx, len(m5_candles)):
        m5_window = m5_candles[max(0, i - history_size + 1): i + 1]
        curr = m5_window[-1]
        now = datetime.fromtimestamp(curr.close_time / 1000, tz=timezone.utc)
        store.advance_to(now)

        # Resolve posisi terbuka DULU pakai candle ini (sama urutan dgn live:
        # tracker jalan di awal tiap run, sebelum cek sinyal baru).
        still_open = []
        for t in open_trades:
            _resolve_trade_one_candle(t, curr)
            if t.status == "CLOSED":
                trades.append(t)
            else:
                still_open.append(t)
        open_trades = still_open

        # Window M15 yang SUDAH CLOSED sampai waktu candle M5 ini.
        m15_end = bisect.bisect_right(m15_close_times, curr.close_time)
        if m15_end < history_size:
            continue
        m15_window = m15_candles[max(0, m15_end - history_size): m15_end]

        bias = compute_m15_bias(
            m15_window,
            lookback,
            min_structure_confirmation=min_struct_conf,
            structure_break_buffer_pct=break_buffer,
        )

        signal = evaluate_m5_trigger(
            market_id, symbol, market,
            bias.bias, bias.structure,
            m15_window, m5_window,
            cfg, store,
        )
        if signal is None:
            continue

        store.record_notified(
            cooldown_key=signal.cooldown_key,
            symbol=symbol,
            timeframe="5m",
            direction=signal.direction.value,
            created_at=now,
        )

        if signal.stop_loss is None:
            # requireRiskManagement=false -> tidak ada level SL/TP utk disimulasikan
            continue

        open_trades.append(
            BacktestTrade(
                signal=signal,
                entry_time=signal.candle_time_iso,
                entry_price=signal.price,
                stop_loss=signal.stop_loss,
                take_profit_1=signal.take_profit_1,
                take_profit_2=signal.take_profit_2,
            )
        )

    # Posisi yang masih terbuka di akhir data historis tetap dilaporkan (status OPEN/TP1_HIT).
    trades.extend(open_trades)
    return trades
