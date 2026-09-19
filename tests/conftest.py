from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from src.models import Candle

BASE_TIME_MS = 1_700_000_000_000  # epoch ms tetap, arbitrer, cuma butuh konsisten
INTERVAL_MS = 5 * 60 * 1000  # 5 menit


def make_candle(
    idx: int,
    o: float,
    h: float,
    l: float,
    c: float,
    v: float = 1000.0,
    interval_ms: int = INTERVAL_MS,
    base: int = BASE_TIME_MS,
) -> Candle:
    open_time = base + idx * interval_ms
    close_time = open_time + interval_ms - 1
    return Candle(
        open_time=open_time,
        close_time=close_time,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=v,
        is_closed=True,
    )


_INSERT_COLUMNS = [
    "signal_key", "cooldown_key", "symbol", "market", "timeframe", "direction",
    "m15_bias", "price", "zone_type", "zone_level", "structure_event", "pattern",
    "candle_time", "candle_open_time_ms", "stop_loss", "take_profit_1",
    "take_profit_2", "risk_reward_1", "risk_reward_2", "atr",
    "zone_tolerance_pct_used",
]


class FakeD1Client:
    """
    Test double in-memory untuk D1Client.

    Meniru subset perilaku SQL yang BENAR-BENAR dipakai oleh kode produksi
    (signal_repository.py, cooldown.py) lewat pencocokan pola string SQL --
    bukan implementasi SQLite sungguhan -- supaya idempotency, cooldown
    permanen, dan rate-limit waktu bisa diuji end-to-end tanpa jaringan/HTTP
    ke Cloudflare D1. `created_at` disimulasikan bisa digeser mundur lewat
    `backdate_all(minutes)` untuk menguji rate-limit kadaluarsa.
    """

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._next_id = 1

    def backdate_all(self, minutes: int) -> None:
        for r in self.rows:
            created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
            r["created_at"] = (created - timedelta(minutes=minutes)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )

    def query_one(self, sql: str, params: Optional[list] = None) -> Optional[dict[str, Any]]:
        params = params or []
        sql_norm = " ".join(sql.split())

        if "SELECT id, notified FROM signals WHERE signal_key" in sql_norm:
            signal_key = params[0]
            for r in self.rows:
                if r["signal_key"] == signal_key:
                    return {"id": r["id"], "notified": r["notified"]}
            return None

        if "SELECT id FROM signals WHERE cooldown_key" in sql_norm:
            cooldown_key = params[0]
            for r in self.rows:
                if r["cooldown_key"] == cooldown_key and r["notified"] == 1:
                    return {"id": r["id"]}
            return None

        if "SELECT id FROM signals" in sql_norm and "symbol = ?" in sql_norm:
            symbol, timeframe, direction, offset_expr = params
            minutes = int(offset_expr.strip().split()[0])  # "-N minutes" -> -N (negatif)
            cutoff = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            for r in self.rows:
                if (
                    r["symbol"] == symbol
                    and r["timeframe"] == timeframe
                    and r["direction"] == direction
                    and r["notified"] == 1
                ):
                    created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                    if created >= cutoff:
                        return {"id": r["id"]}
            return None

        raise NotImplementedError(f"FakeD1Client belum mendukung query: {sql_norm[:80]}")

    def execute(self, sql: str, params: Optional[list] = None) -> dict:
        params = params or []
        sql_norm = " ".join(sql.split())

        if sql_norm.startswith("INSERT OR IGNORE INTO signals"):
            signal_key = params[0]
            if any(r["signal_key"] == signal_key for r in self.rows):
                return {"success": True, "result": [{"meta": {"rows_written": 0}}]}
            row = dict(zip(_INSERT_COLUMNS, params))
            row["id"] = self._next_id
            row["notified"] = 0
            row["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            self._next_id += 1
            self.rows.append(row)
            return {"success": True, "result": [{"meta": {"rows_written": 1}}]}

        if sql_norm.startswith("UPDATE signals SET notified"):
            signal_key = params[0]
            written = 0
            for r in self.rows:
                if r["signal_key"] == signal_key:
                    r["notified"] = 1
                    written = 1
            return {"success": True, "result": [{"meta": {"rows_written": written}}]}

        raise NotImplementedError(f"FakeD1Client belum mendukung execute: {sql_norm[:80]}")


def seed_notified_row(d1: FakeD1Client, **overrides) -> dict:
    """Helper test: masukkan 1 row `notified=1` langsung ke FakeD1Client,
    dipakai untuk mensimulasikan "sudah pernah dinotifikasi" saat menguji
    cooldown_key permanen maupun rate-limit waktu (cooldownMinutes)."""
    row = {
        "signal_key": f"k{d1._next_id}", "cooldown_key": "cdk_default", "symbol": "BTCUSDT",
        "market": "futures", "timeframe": "5m", "direction": "BUY", "m15_bias": "BULLISH",
        "price": 100.0, "zone_type": "support", "zone_level": 99.0,
        "structure_event": "BOS_BULLISH", "pattern": "bullish_pin_bar",
        "candle_time": "2026-01-01T00:00:00Z", "candle_open_time_ms": 0,
        "stop_loss": None, "take_profit_1": None, "take_profit_2": None,
        "risk_reward_1": None, "risk_reward_2": None, "atr": None,
        "zone_tolerance_pct_used": None,
    }
    row.update(overrides)
    row["id"] = d1._next_id
    row["notified"] = 1
    row.setdefault("created_at", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    d1._next_id += 1
    d1.rows.append(row)
    return row
