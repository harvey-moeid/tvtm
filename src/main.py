"""
Entrypoint dijalankan oleh GitHub Actions cron (lihat .github/workflows/check-signal.yml).

Setiap run:
1. Load config symbols + strategy.
2. Untuk tiap market enabled: fetch M15+M5 -> bias -> trigger -> idempotency -> Discord.
3. Isolasi kegagalan per market (PRD §20) -> 1 market error tidak menghentikan yang lain.
4. Print ringkasan run ke stdout (observability, muncul di log GitHub Actions).
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from src.config_loader import load_strategy_config, load_symbols, require_env
from src.storage.d1_client import D1Client
from src.strategy.strategy import dispatch_signal, evaluate_market

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


def main() -> int:
    started_at = datetime.now(timezone.utc)
    log.info("=== tv-alert-relay run start: %s ===", started_at.isoformat())

    try:
        webhook_url = require_env("DISCORD_WEBHOOK_URL")
        account_id = require_env("CF_ACCOUNT_ID")
        database_id = require_env("CF_D1_DATABASE_ID")
        api_token = require_env("CF_API_TOKEN")
    except RuntimeError as e:
        log.error("Konfigurasi environment tidak lengkap: %s", e)
        return 1

    d1 = D1Client(account_id, database_id, api_token)

    markets = load_symbols()
    summary = {"evaluated": 0, "skipped": 0, "signals": 0, "notified": 0, "errors": 0}

    for market_cfg in markets:
        if not market_cfg.get("enabled", True):
            continue
        market_id = market_cfg["id"]
        summary["evaluated"] += 1
        try:
            strategy_cfg = load_strategy_config(market_cfg["symbol"])
            signal = evaluate_market(market_cfg, strategy_cfg, d1)
            if signal is None:
                summary["skipped"] += 1
                continue

            summary["signals"] += 1
            ok = dispatch_signal(webhook_url, d1, signal)
            if ok:
                summary["notified"] += 1
        except Exception as e:  # noqa: BLE001 - isolasi wajib per market, PRD §20
            summary["errors"] += 1
            log.exception("[%s] error tak terduga, market di-skip: %s", market_id, e)
            continue

    finished_at = datetime.now(timezone.utc)
    duration = (finished_at - started_at).total_seconds()
    log.info(
        "=== run selesai (%.2fs) | evaluated=%d skipped=%d signals=%d notified=%d errors=%d ===",
        duration, summary["evaluated"], summary["skipped"], summary["signals"],
        summary["notified"], summary["errors"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
