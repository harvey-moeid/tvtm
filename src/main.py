from __future__ import annotations

import logging
import json
import sys
from datetime import datetime, timezone

from src.config_loader import load_strategy_config, load_symbols, require_env
from src.storage.github_store import connect_from_env
from src.storage.signal_repository import pending_signals
from src.models import Bias, Direction, ScoreComponent, Signal
from src.strategy.strategy import (
    MarketDataUnavailable,
    dispatch_signal,
    evaluate_market,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> int:
    started = datetime.now(timezone.utc)

    try:
        webhook = require_env("DISCORD_WEBHOOK_URL")
        store = connect_from_env()
    except RuntimeError as exc:
        logging.error("Konfigurasi environment tidak lengkap: %s", exc)
        return 1

    summary = {
        "evaluated": 0,
        "skipped": 0,
        "signals": 0,
        "notified": 0,
        "errors": 0,
        "data_errors": 0,
    }

    # Retry reservations that were saved before an interrupted/failed Discord call.
    for row in pending_signals(store):
        try:
            signal = Signal(
                row.get("market_id", row["symbol"]), row["symbol"], row["market"],
                row["timeframe"], Direction(row["direction"]), Bias(row["m15_bias"]),
                row["price"], row["zone_type"], row["zone_level"],
                row["structure_event"], row["pattern"], row["candle_time"],
                row["candle_open_time_ms"], row["signal_key"], row["cooldown_key"],
                row.get("stop_loss"), row.get("take_profit_1"), row.get("take_profit_2"),
                row.get("risk_reward_1"), row.get("risk_reward_2"), row.get("atr"),
                row.get("zone_tolerance_pct_used"), row.get("confidence_pct"),
                row.get("score"), [ScoreComponent(**c) for c in
                                   json.loads(row.get("checklist_json") or "[]")],
            )
            if dispatch_signal(webhook, store, signal):
                summary["notified"] += 1
        except Exception:
            summary["errors"] += 1
            logging.exception("[%s] retry pending gagal", row["signal_key"])

    for cfg in load_symbols():
        if not cfg.get("enabled", True):
            continue

        summary["evaluated"] += 1

        try:
            signal = evaluate_market(
                cfg,
                load_strategy_config(cfg["symbol"]),
                store,
                webhook,
            )
            if signal is None:
                summary["skipped"] += 1
                continue

            summary["signals"] += 1
            if dispatch_signal(webhook, store, signal):
                summary["notified"] += 1

        except MarketDataUnavailable as exc:
            summary["data_errors"] += 1
            logging.error("[%s] %s", cfg["id"], exc)
        except Exception:
            summary["errors"] += 1
            logging.exception("[%s] error", cfg["id"])

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    logging.info(
        "run %.2fs evaluated=%d skipped=%d signals=%d notified=%d errors=%d "
        "data_errors=%d",
        elapsed,
        summary["evaluated"],
        summary["skipped"],
        summary["signals"],
        summary["notified"],
        summary["errors"],
        summary["data_errors"],
    )

    return (
        1
        if summary["errors"]
        or (summary["evaluated"] and summary["data_errors"] == summary["evaluated"])
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
