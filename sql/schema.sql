-- Schema D1 untuk audit trail signal (PRD §17.1, + kolom `notified` sbg
-- penguat idempotency: INSERT dulu sebagai checkpoint dedup, baru update
-- notified=1 setelah Discord sukses terkirim — supaya retry tidak dobel
-- kirim notifikasi tapi juga tidak kehilangan notifikasi kalau proses
-- terputus tepat setelah insert).

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_key TEXT NOT NULL UNIQUE,
    cooldown_key TEXT NOT NULL,
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    direction TEXT NOT NULL,
    m15_bias TEXT NOT NULL,
    price REAL NOT NULL,
    zone_type TEXT NOT NULL,
    zone_level REAL NOT NULL,
    structure_event TEXT NOT NULL,
    pattern TEXT NOT NULL,
    candle_time TEXT NOT NULL,
    candle_open_time_ms INTEGER NOT NULL,
    notified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_signals_cooldown_key ON signals (cooldown_key);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf ON signals (symbol, timeframe);
