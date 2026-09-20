from __future__ import annotations
import logging
import sys
from datetime import datetime, timezone
from src.config_loader import load_strategy_config, load_symbols, require_env
from src.storage.d1_client import D1Client
from src.strategy.strategy import MarketDataUnavailable, dispatch_signal, evaluate_market

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
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

    log.info("D1 target configured: %s", database_id)
    d1 = D1Client(account_id, database_id, api_token)
    try:
        before = d1.query_one("SELECT COUNT(*) AS total FROM signals")
        log.info("D1 pre-run signals=%s", (before or {}).get("total", 0))
    except Exception as e:
        log.exception("D1 preflight gagal: %s", e)
        return 1

    markets = load_symbols()
    summary = {"evaluated": 0, "skipped": 0, "signals": 0, "notified": 0, "errors": 0, "data_errors": 0}
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
                log.info("[%s] RESULT: no signal generated", market_id)
                continue
            summary["signals"] += 1
            log.info("[%s] SIGNAL CREATED: %s %s price=%s pattern=%s zone=%s RR1=%s",
                     market_id, signal.direction.value, signal.symbol, signal.price,
                     signal.pattern, signal.zone_level, signal.risk_reward_1)
            if dispatch_signal(webhook_url, d1, signal):
                summary["notified"] += 1
        except MarketDataUnavailable as e:
            summary["data_errors"] += 1
            log.error("[%s] data market tidak tersedia: %s", market_id, e)
        except Exception as e:
            summary["errors"] += 1
            log.exception("[%s] error tak terduga: %s", market_id, e)

    try:
        after = d1.query_one("SELECT COUNT(*) AS total FROM signals")
        log.info("D1 post-run signals=%s", (after or {}).get("total", 0))
    except Exception as e:
        log.exception("D1 postflight gagal: %s", e)

    duration = (datetime.now(timezone.utc) - started_at).total_seconds()
    log.info("=== run selesai (%.2fs) | evaluated=%d skipped=%d signals=%d notified=%d errors=%d data_errors=%d ===",
             duration, summary["evaluated"], summary["skipped"], summary["signals"],
             summary["notified"], summary["errors"], summary["data_errors"])

    # Semua market gagal ambil data = engine praktis mati; run harus merah supaya terlihat.
    if summary["evaluated"] > 0 and summary["data_errors"] == summary["evaluated"]:
        log.error("Semua market gagal mengambil data candle; run ditandai gagal.")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
