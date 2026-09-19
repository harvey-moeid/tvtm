"""
Migrasi D1 yang AMAN dijalankan berkali-kali (idempotent) untuk upgrade
risk management - berbeda dengan sql/migrations/0002_risk_management.sql
yang isinya ALTER TABLE polos (SQLite tidak punya "ADD COLUMN IF NOT
EXISTS", jadi kalau dijalankan mentah-mentah dua kali akan error
"duplicate column name").

Jalankan sekali di database D1 yang SUDAH ADA sebelum upgrade ini:

    python scripts/migrate_d1.py

Aman dipanggil ulang kapan saja: kolom yang sudah ada otomatis dilewati.
Untuk database BARU, cukup pakai scripts/setup_d1.py seperti biasa (skema
barunya sudah termasuk kolom-kolom ini).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config_loader import require_env
from src.storage.d1_client import D1Client

NEW_COLUMNS = {
    "stop_loss": "REAL",
    "take_profit_1": "REAL",
    "take_profit_2": "REAL",
    "risk_reward_1": "REAL",
    "risk_reward_2": "REAL",
    "atr": "REAL",
    "zone_tolerance_pct_used": "REAL",
}


def main() -> int:
    account_id = require_env("CF_ACCOUNT_ID")
    database_id = require_env("CF_D1_DATABASE_ID")
    api_token = require_env("CF_API_TOKEN")

    d1 = D1Client(account_id, database_id, api_token)

    existing = d1.execute("PRAGMA table_info(signals)")
    columns = {row["name"] for row in existing.get("result", [{}])[0].get("results", [])}

    added = []
    for name, coltype in NEW_COLUMNS.items():
        if name in columns:
            continue
        d1.execute(f"ALTER TABLE signals ADD COLUMN {name} {coltype}")
        added.append(name)

    d1.execute(
        "CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf_dir_created "
        "ON signals (symbol, timeframe, direction, created_at)"
    )

    if added:
        print(f"Kolom baru ditambahkan: {', '.join(added)}")
    else:
        print("Tidak ada kolom baru yang perlu ditambahkan, skema sudah up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
