-- Migration 0002: tambah kolom risk management ke tabel `signals`.
--
-- PERINGATAN: D1/SQLite TIDAK mendukung "ALTER TABLE ... ADD COLUMN IF NOT
-- EXISTS". File ini murni DOKUMENTASI perubahan skema - JANGAN dieksekusi
-- langsung berulang kali (akan error "duplicate column name" di run kedua).
--
-- Untuk apply migrasi ini secara aman & idempotent ke database yang sudah
-- ada, gunakan:
--
--     python scripts/migrate_d1.py
--
-- Skrip itu mengecek PRAGMA table_info(signals) dulu dan hanya menambah
-- kolom yang belum ada.

ALTER TABLE signals ADD COLUMN stop_loss REAL;
ALTER TABLE signals ADD COLUMN take_profit_1 REAL;
ALTER TABLE signals ADD COLUMN take_profit_2 REAL;
ALTER TABLE signals ADD COLUMN risk_reward_1 REAL;
ALTER TABLE signals ADD COLUMN risk_reward_2 REAL;
ALTER TABLE signals ADD COLUMN atr REAL;
ALTER TABLE signals ADD COLUMN zone_tolerance_pct_used REAL;

CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf_dir_created
    ON signals (symbol, timeframe, direction, created_at);
