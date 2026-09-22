CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_key TEXT NOT NULL UNIQUE,
    cooldown_key TEXT NOT NULL,
    symbol TEXT NOT NULL, market TEXT NOT NULL, timeframe TEXT NOT NULL,
    direction TEXT NOT NULL, m15_bias TEXT NOT NULL, price REAL NOT NULL,
    zone_type TEXT NOT NULL, zone_level REAL NOT NULL, structure_event TEXT NOT NULL,
    pattern TEXT NOT NULL, candle_time TEXT NOT NULL, candle_open_time_ms INTEGER NOT NULL,
    stop_loss REAL, take_profit_1 REAL, take_profit_2 REAL, risk_reward_1 REAL,
    risk_reward_2 REAL, atr REAL, zone_tolerance_pct_used REAL,
    confidence_pct REAL, score REAL, checklist_json TEXT,
    notified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_signals_cooldown_key ON signals(cooldown_key);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf ON signals(symbol,timeframe);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf_dir_created ON signals(symbol,timeframe,direction,created_at);

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
