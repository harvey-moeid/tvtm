"""
CLI backtest: replay histori candle OKX lewat strategi live (M15 bias -> M5
trigger -> risk management -> scorer) TANPA menyentuh D1/Discord asli, buat
validasi awal (win-rate/expectancy/drawdown) sebelum parameter (ATR
multiplier, R:R minimum, bobot scorer, dll) dipakai untuk keputusan trading
riil - lihat CHECKLIST.md.

Pemakaian:
    pip install -r requirements.txt
    python scripts/backtest.py --symbol BTCUSDT --candles 6000
    python scripts/backtest.py --symbol GOLDUSDT --candles 6000 --out backtest_gold.json

PENTING: skrip ini butuh akses jaringan ke www.okx.com. Kalau dijalankan di
lingkungan tanpa akses OKX (mis. sandbox CI terbatas), jalankan lewat
workflow_dispatch `.github/workflows/backtest.yml` di GitHub Actions - runner
GitHub Actions sudah terbukti bisa reach OKX (dipakai juga oleh
check-signal.yml).

--candles menentukan jumlah candle M5 historis yang diambil (candle M15
diambil otomatis mengikuti, minimal 2x minHistoricalCandles). 6000 candle M5
~= 20 hari; naikkan sesuai kebutuhan - OKX history-candles dibatasi rate
limit publik, skrip ini sudah kasih jeda antar halaman pagination.

Hasil backtest (win-rate, expectancy, drawdown) adalah ESTIMASI berbasis
histori - bukan jaminan performa ke depan, dan tidak memperhitungkan slippage,
funding rate perpetual, atau downtime API OKX/D1/Discord.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.metrics import BacktestMetrics, compute_metrics  # noqa: E402
from src.backtest.simulator import run_backtest  # noqa: E402
from src.config_loader import load_strategy_config, load_symbols  # noqa: E402
from src.market.history_fetch import fetch_history_candles  # noqa: E402


def _print_report(symbol: str, metrics: BacktestMetrics) -> None:
    print(f"\n=== Backtest {symbol} ===")
    print(f"Total sinyal          : {metrics.total_signals}")
    print(f"Trade closed / open   : {metrics.closed_trades} / {metrics.open_trades}")
    print(f"Win rate              : {metrics.win_rate_pct}% ({metrics.wins}W / {metrics.losses}L)")
    print(f"Total R               : {metrics.total_r}")
    print(f"Avg R / trade         : {metrics.avg_r}")
    print(f"Expectancy (R/trade)  : {metrics.expectancy_r}")
    print(f"Profit factor         : {metrics.profit_factor}")
    print(f"Max drawdown (R)      : {metrics.max_drawdown_r}")
    print(f"Avg PnL%/trade        : {metrics.avg_pnl_pct}%")

    for label, breakdown in (
        ("Per arah", metrics.by_direction),
        ("Per pattern", metrics.by_pattern),
        ("Per exit_reason", metrics.by_exit_reason),
    ):
        if not breakdown:
            continue
        print(f"\n-- {label} --")
        for k, v in breakdown.items():
            print(f"  {k:22s} n={v['count']:<4} win_rate={v['win_rate_pct']:>5}% avg_r={v['avg_r']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbol", required=True, help="Symbol internal, mis. BTCUSDT / GOLDUSDT")
    ap.add_argument("--candles", type=int, default=6000, help="Jumlah candle M5 historis yang diambil")
    ap.add_argument("--out", default=None, help="Path JSON opsional buat simpan hasil trade+metrics")
    args = ap.parse_args()

    market_cfg = next((m for m in load_symbols() if m["symbol"] == args.symbol), None)
    if market_cfg is None:
        print(f"Symbol tidak ditemukan di symbols.json: {args.symbol}", file=sys.stderr)
        return 1

    cfg = load_strategy_config(args.symbol)
    exchange_symbol = market_cfg["exchange_symbol"]

    print(f"Fetching histori M5 {exchange_symbol} ({args.candles} candle)...")
    m5 = fetch_history_candles(exchange_symbol, "5m", args.candles)

    m15_target = max(cfg["minHistoricalCandles"] * 2, args.candles // 3)
    print(f"Fetching histori M15 {exchange_symbol} ({m15_target} candle)...")
    m15 = fetch_history_candles(exchange_symbol, "15m", m15_target)

    print(f"Candle terkumpul: M5={len(m5)} M15={len(m15)}. Menjalankan simulasi...")
    trades = run_backtest(market_cfg["id"], args.symbol, market_cfg["market"], m15, m5, cfg)
    metrics = compute_metrics(trades)
    _print_report(args.symbol, metrics)

    if args.out:
        payload = {
            "symbol": args.symbol,
            "candles": {"m5": len(m5), "m15": len(m15)},
            "metrics": metrics.__dict__,
            "trades": [
                {
                    "entry_time": t.entry_time,
                    "direction": t.signal.direction.value,
                    "pattern": t.signal.pattern,
                    "entry_price": t.entry_price,
                    "stop_loss": t.stop_loss,
                    "take_profit_1": t.take_profit_1,
                    "take_profit_2": t.take_profit_2,
                    "status": t.status,
                    "exit_price": t.exit_price,
                    "exit_time": t.exit_time,
                    "exit_reason": t.exit_reason,
                    "pnl_pct": t.pnl_pct,
                    "pnl_r": t.pnl_r,
                    "score": t.signal.score,
                    "confidence_pct": t.signal.confidence_pct,
                }
                for t in trades
            ],
        }
        Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nDetail tersimpan ke {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
