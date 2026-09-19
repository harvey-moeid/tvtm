-- Schema D1 untuk audit trail signal (PRD 17.1, + kolom `notified` sbg
-- penguat idempotency: INSERT dulu sebagai checkpoint dedup, baru update
-- notified=1 setelah Discord sukses terkirim, supaya retry tidak dobel
-- kirim notifikasi tapi juga tidak kehilangan notifikasi kalau proses
-- terputus tepat setelah insert).
--
-- UPGRADE: kolom risk management (stop_loss, take_profit_1/2, risk_reward_1/2,
-- atr, zone_tolerance_pct_used) ditambahkan untuk audit trail level eksekusi.
-- Skema ini dipakai untuk INSTALASI BARU (lewat scripts/setup_d1.py).
-- Untuk database yang SUDAH ADA sebelum upgrade ini, jalankan
-- scripts/migrate_d1.py (idempotent, aman dipanggil berkali-kali) - JANGAN
-- jalankan sql/migrations/0002_risk_management.sql secara manual berulang,
-- karena SQLite/D1 tidak mendukung "ADD COLUMN IF NOT EXISTS".

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
    stop_loss REAL,
    take_profit_1 REAL,
    take_profit_2 REAL,
    risk_reward_1 REAL,
    risk_reward_2 REAL,
    atr REAL,
    zone_tolerance_pct_used REAL,
    notified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_signals_cooldown_key ON signals (cooldown_key);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf ON signals (symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf_dir_created
    ON signals (symbol, timeframe, direction, created_at);
