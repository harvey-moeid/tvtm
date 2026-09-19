"""
Repository untuk idempotency + audit signal ke D1.

Alur:
1. try_reserve() -> INSERT OR IGNORE pakai signal_key UNIQUE (PRD 5 idempotency).
   - rows_written == 0 artinya signal_key ini SUDAH ada -> duplikat -> skip semua.
   - rows_written == 1 artinya baru -> lanjut kirim Discord.
2. mark_notified() -> update notified=1 setelah Discord sukses.
   Kalau proses mati sebelum langkah ini, run berikutnya akan retry Discord
   (karena notified masih 0) TANPA membuat duplikat record baru.

UPGRADE: kolom risk management (stop_loss, take_profit_1/2, risk_reward_1/2,
atr, zone_tolerance_pct_used) ikut disimpan untuk audit trail - sebelumnya
tabel ini hanya menyimpan hasil price-action tanpa jejak level eksekusi/risiko.
Pastikan skema D1 sudah dimigrasi (scripts/migrate_d1.py) sebelum kolom ini
dipakai di database yang sudah ada.
"""

from __future__ import annotations

import logging

from src.models import Signal
from src.storage.d1_client import D1Client

log = logging.getLogger("signal_repository")

_INSERT_SQL = """
INSERT OR IGNORE INTO signals
  (signal_key, cooldown_key, symbol, market, timeframe, direction, m15_bias,
   price, zone_type, zone_level, structure_event, pattern, candle_time, candle_open_time_ms,
   stop_loss, take_profit_1, take_profit_2, risk_reward_1, risk_reward_2, atr,
   zone_tolerance_pct_used)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def try_reserve(d1: D1Client, signal: Signal) -> bool:
    """True kalau berhasil reserve slot baru (belum pernah ada). False kalau duplikat
    ATAU sudah pernah notified=1 sebelumnya (via cooldown check di layer atas)."""
    existing = d1.query_one(
        "SELECT id, notified FROM signals WHERE signal_key = ? LIMIT 1", [signal.signal_key]
    )
    if existing is not None:
        return existing.get("notified") == 0

    data = d1.execute(
        _INSERT_SQL,
        [
            signal.signal_key,
            signal.cooldown_key,
            signal.symbol,
            signal.market,
            signal.timeframe,
            signal.direction.value,
            signal.m15_bias.value,
            signal.price,
            signal.zone_type,
            signal.zone_level,
            signal.structure_event,
            signal.pattern,
            signal.candle_time_iso,
            signal.candle_open_time_ms,
            signal.stop_loss,
            signal.take_profit_1,
            signal.take_profit_2,
            signal.risk_reward_1,
            signal.risk_reward_2,
            signal.atr,
            signal.zone_tolerance_pct_used,
        ],
    )
    meta = data.get("result", [{}])[0].get("meta", {})
    rows_written = meta.get("rows_written", meta.get("changes", 0))
    return bool(rows_written)


def mark_notified(d1: D1Client, signal_key: str) -> None:
    d1.execute("UPDATE signals SET notified = 1 WHERE signal_key = ?", [signal_key])
