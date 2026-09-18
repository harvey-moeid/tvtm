"""
Jalankan SEKALI secara manual buat bikin tabel `signals` di D1:

    python scripts/setup_d1.py

Butuh env CF_ACCOUNT_ID, CF_D1_DATABASE_ID, CF_API_TOKEN (sama seperti workflow).
Tidak dipanggil otomatis tiap cron run supaya tidak menambah 1 HTTP call D1
setiap 5 menit untuk sesuatu yang cukup dijalankan sekali (CREATE TABLE IF NOT EXISTS).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config_loader import require_env
from src.storage.d1_client import D1Client


def main() -> int:
    account_id = require_env("CF_ACCOUNT_ID")
    database_id = require_env("CF_D1_DATABASE_ID")
    api_token = require_env("CF_API_TOKEN")

    schema_path = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    d1 = D1Client(account_id, database_id, api_token)
    d1.ensure_schema(schema_sql)
    print("Schema D1 siap: tabel `signals` sudah dibuat (atau sudah ada sebelumnya).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
