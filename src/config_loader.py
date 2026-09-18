"""
Loader config JSON + resolve override per-symbol (PRD §7).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path(__file__).parent / "config"


def load_symbols() -> list[dict[str, Any]]:
    with open(_CONFIG_DIR / "symbols.json", "r", encoding="utf-8") as f:
        return json.load(f)["markets"]


def load_strategy_config(symbol: str) -> dict[str, Any]:
    with open(_CONFIG_DIR / "strategy.json", "r", encoding="utf-8") as f:
        raw = json.load(f)
    cfg = dict(raw["default"])
    cfg.update(raw.get("overrides", {}).get(symbol, {}))
    return cfg


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Environment variable wajib belum di-set: {name}")
    return val
