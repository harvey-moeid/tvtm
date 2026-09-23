"""
Pengganti D1Client saat backtest: implementasi in-memory yang cukup untuk
dua pola query yang dikirim src/strategy/cooldown.py (is_in_cooldown &
is_rate_limited), TANPA menyentuh Cloudflare D1 asli.

BEDA PENTING dari FakeD1Client di tests/conftest.py (yang dipakai unit test
lain): store ini dievaluasi terhadap JAM SIMULASI (`self.now`, di-set manual
oleh backtest engine tiap bar lewat `advance_to()`), BUKAN wall-clock time.
SQL asli di cooldown.py memakai literal SQLite `'now'` yang hanya masuk akal
kalau "sekarang" adalah waktu run yang sesungguhnya (benar untuk cron live -
tiap run MEMANG "sekarang"), tapi salah total untuk backtest yang me-replay
candle dari bulan-bulan lalu: kalau dibiarkan pakai wall-clock asli,
`cooldownMinutes` rate-limit tidak akan pernah aktif (karena semua timestamp
historis pasti sudah lebih dari cooldownMinutes di masa lalu dari sudut
pandang wall-clock sekarang), sehingga backtest akan salah menghasilkan sinyal
jauh lebih banyak/sering daripada yang akan terjadi kalau strategi ini
benar-benar dijalankan live candle demi candle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


@dataclass
class InMemorySignalStore:
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _rows: list = field(default_factory=list)

    def advance_to(self, ts: datetime) -> None:
        """Dipanggil backtest engine SEBELUM evaluate_m5_trigger tiap bar,
        supaya rate-limit dihitung relatif terhadap waktu candle yang sedang
        direplay, bukan waktu asli sekarang."""
        self.now = ts

    def record_notified(
        self, *, cooldown_key: str, symbol: str, timeframe: str, direction: str, created_at: datetime
    ) -> None:
        """Dipanggil engine setelah sebuah sinyal lolos - backtest menganggap
        setiap sinyal LANGSUNG notified (sama seperti produksi: try_reserve
        lalu dispatch_signal terjadi di run yang sama; kegagalan kirim Discord
        adalah kasus retry minor yang diabaikan di sini)."""
        self._rows.append(
            {
                "cooldown_key": cooldown_key,
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": direction,
                "notified": 1,
                "created_at": created_at,
            }
        )

    def query_one(self, sql: str, params: Optional[list] = None) -> Optional[dict[str, Any]]:
        p = params or []
        s = " ".join(sql.split())

        if "SELECT id FROM signals WHERE cooldown_key" in s:
            cooldown_key = p[0]
            for r in self._rows:
                if r["cooldown_key"] == cooldown_key and r["notified"] == 1:
                    return {"id": 1}
            return None

        if s.startswith("SELECT id FROM signals") and "symbol = ?" in s:
            symbol, timeframe, direction, offset_expr = p
            minutes = int(offset_expr.strip().split()[0])  # "-60 minutes" -> -60
            cutoff = self.now + timedelta(minutes=minutes)
            for r in self._rows:
                if (
                    r["symbol"] == symbol
                    and r["timeframe"] == timeframe
                    and r["direction"] == direction
                    and r["notified"] == 1
                    and r["created_at"] >= cutoff
                ):
                    return {"id": 1}
            return None

        raise NotImplementedError(f"Query tidak didukung InMemorySignalStore: {s}")

    def execute(self, sql: str, params: Optional[list] = None) -> dict:
        raise NotImplementedError(
            "InMemorySignalStore hanya melayani query baca cooldown/rate-limit "
            "saat backtest - pemanggil harus memakai record_notified() untuk menulis."
        )
