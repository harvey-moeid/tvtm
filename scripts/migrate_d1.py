"""Idempotent D1 migration for ICT scoring and trade tracking."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.config_loader import require_env
from src.storage.d1_client import D1Client

NEW_COLUMNS={
    "stop_loss":"REAL","take_profit_1":"REAL","take_profit_2":"REAL",
    "risk_reward_1":"REAL","risk_reward_2":"REAL","atr":"REAL","zone_tolerance_pct_used":"REAL",
    "confidence_pct":"REAL","score":"REAL","checklist_json":"TEXT",
}
TRADES_SCHEMA="""
CREATE TABLE IF NOT EXISTS trades (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 signal_key TEXT NOT NULL UNIQUE,
 symbol TEXT NOT NULL, market TEXT NOT NULL, timeframe TEXT NOT NULL, direction TEXT NOT NULL,
 entry_price REAL NOT NULL, stop_loss REAL NOT NULL, take_profit_1 REAL, take_profit_2 REAL,
 entry_time TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN',
 tp1_hit INTEGER NOT NULL DEFAULT 0, tp1_hit_at TEXT,
 exit_price REAL, exit_time TEXT, exit_reason TEXT, pnl_pct REAL, pnl_r REAL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_trades_status_symbol ON trades(status,symbol);
CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON trades(exit_time);
"""

def main()->int:
    d1=D1Client(require_env("CF_ACCOUNT_ID"),require_env("CF_D1_DATABASE_ID"),require_env("CF_API_TOKEN"))
    existing=d1.execute("PRAGMA table_info(signals)")
    cols={r["name"] for r in existing.get("result",[{}])[0].get("results",[])}
    added=[]
    for name,typ in NEW_COLUMNS.items():
        if name not in cols:
            d1.execute(f"ALTER TABLE signals ADD COLUMN {name} {typ}"); added.append(name)
    for stmt in [s.strip() for s in TRADES_SCHEMA.split(";") if s.strip()]:
        d1.execute(stmt)
    d1.execute("CREATE INDEX IF NOT EXISTS idx_signals_score ON signals(score)")
    print("Migrasi selesai." if not added else f"Kolom ditambahkan: {', '.join(added)}")
    return 0
if __name__=="__main__": sys.exit(main())
