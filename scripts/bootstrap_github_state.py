"""Verify existing GitHub trading journal, or safely import R2 state once.

This job performs no market fetching, Discord notifications or trades. It is
serialized with check-signal.yml and fails closed if legacy storage is missing.
"""
from __future__ import annotations

import hashlib
import json
import logging

from src.storage.github_store import connect_from_env


def main() -> None:
    store = connect_from_env()
    state = store.state
    signals, trades = state["signals"], state["trades"]
    if state["version"] != 1:
        raise ValueError("State format version is unsupported")
    for rows, name in ((signals, "signals"), (trades, "trades")):
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError(f"Malformed {name} rows")
        ids = [row.get("id") for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate {name} IDs")
    raw = json.dumps(state, sort_keys=True, ensure_ascii=False).encode("utf-8")
    fingerprint = hashlib.sha256(raw).hexdigest()[:16]
    logging.warning(
        "GitHub state verified: version=%d signals=%d trades=%d bytes=%d fingerprint=%s",
        state["version"], len(signals), len(trades), len(raw), fingerprint,
    )


if __name__ == "__main__":
    main()
