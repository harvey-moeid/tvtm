"""JSON state in a private Cloudflare R2 bucket.

The signal workflow has a single concurrency group, so only one writer may
load and replace state.json at a time. Every state transition is persisted
before the next side effect (notably before sending a Discord notification).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone


STATE_KEY = "state.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def empty_state() -> dict:
    return {"version": 1, "next_signal_id": 1, "next_trade_id": 1, "signals": [], "trades": []}


class JSONStore:
    def __init__(self, state: dict, save_callback=None, now=None):
        if state.get("version") != 1 or not isinstance(state.get("signals"), list) or not isinstance(state.get("trades"), list):
            raise ValueError("Format state.json R2 tidak dikenal")
        self.state = state
        self.rows = state["signals"]
        self.trades = state["trades"]
        self._save_callback = save_callback
        self.now = now or (lambda: datetime.now(timezone.utc))

    def save(self):
        if self._save_callback:
            self._save_callback(self.state)

    def has_notified_cooldown(self, key):
        return any(r["cooldown_key"] == key and r["notified"] == 1 for r in self.rows)

    def was_notified_recently(self, symbol, timeframe, direction, minutes):
        cutoff = self.now() - timedelta(minutes=minutes)
        return any(
            r["symbol"] == symbol and r["timeframe"] == timeframe
            and r["direction"] == direction and r["notified"] == 1
            and datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= cutoff
            for r in self.rows
        )


def connect_from_env():
    import os
    import boto3
    from src.config_loader import require_env

    account = require_env("CF_ACCOUNT_ID")
    bucket = os.getenv("R2_BUCKET", "tvtm-data")
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        region_name="auto",
        aws_access_key_id=require_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=require_env("R2_SECRET_ACCESS_KEY"),
    )
    # Never silently reset a missing or unreadable state: it may contain live positions.
    response = client.get_object(Bucket=bucket, Key=STATE_KEY)
    state = json.loads(response["Body"].read())

    def save(updated):
        client.put_object(
            Bucket=bucket, Key=STATE_KEY,
            Body=json.dumps(updated, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            ContentType="application/json",
        )

    return JSONStore(state, save)
