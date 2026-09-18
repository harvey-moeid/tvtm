"""
Client Cloudflare D1 via REST API resmi Cloudflare — TANPA Worker.

Endpoint:
  POST https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query

Ini menggantikan pendekatan "Worker tv-alert-worker" di PRD v4 §6/§17 karena
seluruh stack sekarang murni Python: D1 punya HTTP Query API resmi yang bisa
dipanggil langsung pakai API Token, jadi tidak perlu lapisan Worker terpisah.

Kalau nanti proyek butuh Worker lagi (mis. untuk expose data ke frontend),
kode ini tetap kompatibel karena hanya bergantung pada REST API D1 standar.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests

log = logging.getLogger("d1_client")


class D1Client:
    def __init__(self, account_id: str, database_id: str, api_token: str, timeout: int = 15):
        self.base_url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query"
        )
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self.timeout = timeout

    def execute(self, sql: str, params: Optional[list] = None) -> dict:
        body = {"sql": sql, "params": params or []}
        resp = requests.post(self.base_url, headers=self.headers, json=body, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success", False):
            raise RuntimeError(f"D1 query gagal: {data.get('errors')}")
        return data

    def query_one(self, sql: str, params: Optional[list] = None) -> Optional[dict[str, Any]]:
        data = self.execute(sql, params)
        results = data.get("result", [])
        if not results:
            return None
        rows = results[0].get("results", [])
        return rows[0] if rows else None

    def ensure_schema(self, schema_sql: str) -> None:
        """Jalankan schema.sql (idempotent, pakai IF NOT EXISTS)."""
        statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
        for stmt in statements:
            self.execute(stmt)
