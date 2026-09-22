"""
Model data inti untuk engine price action.
Semua modul struktur/strategi bertukar data lewat dataclass di sini
supaya kontraknya eksplisit dan gampang di-unit-test.

UPGRADE: Signal ditambah field risk management (stop_loss, take_profit,
risk_reward, atr, zone_tolerance_pct_used) supaya hasil sinyal bukan cuma
"price action valid" tapi juga bawa level eksekusi + ukuran risikonya.
Semua field baru Optional dan default None supaya backward compatible.

UPGRADE 2 (ICT full suite): tambah dataclass FairValueGap, OrderBlock,
LiquiditySweep, VolumeProfileLevel, ScoreResult - dipakai oleh
src/structure/fvg.py, src/structure/order_block.py, src/strategy/liquidity.py,
src/strategy/volume_profile.py, dan src/strategy/scorer.py. Signal ditambah
field confidence_pct/score/checklist (Optional, default None/empty, backward
compatible dengan konsumen lama yang belum tahu field ini).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Bias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class StructureTrend(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    RANGE = "RANGE"


class StructureEvent(str, Enum):
    BOS_BULLISH = "BOS_BULLISH"
    BOS_BEARISH = "BOS_BEARISH"
    CHOCH_BULLISH = "CHOCH_BULLISH"
    CHOCH_BEARISH = "CHOCH_BEARISH"
    NONE = "NONE"


class ZoneType(str, Enum):
    SUPPORT = "support"
    RESISTANCE = "resistance"


class PatternType(str, Enum):
    BULLISH_PIN_BAR = "bullish_pin_bar"
    BEARISH_PIN_BAR = "bearish_pin_bar"
    BULLISH_ENGULFING = "bullish_engulfing"
    BEARISH_ENGULFING = "bearish_engulfing"
    NONE = "none"


@dataclass(frozen=True)
class Candle:
    open_time: int          # epoch ms, waktu buka candle
    close_time: int         # epoch ms, waktu candle resmi close
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = True

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return max(self.high - self.low, 1e-12)

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def candle_time_iso(self) -> str:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(self.open_time / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )


@dataclass(frozen=True)
class SwingPoint:
    index: int
    price: float
    kind: str  # "high" | "low"
    candle_time: int  # open_time candle terkait, epoch ms


@dataclass
class StructureResult:
    trend: StructureTrend
    last_swing_high: Optional[SwingPoint]
    last_swing_low: Optional[SwingPoint]
    swings: list = field(default_factory=list)
    event: StructureEvent = StructureEvent.NONE
    event_candle_time: Optional[int] = None
    event_level: Optional[float] = None


@dataclass
class Zone:
    zone_type: ZoneType
    level: float
    tolerance_pct: float
    source_swing: SwingPoint
    structure_event: StructureEvent
    structure_event_candle_time: Optional[int]

    @property
    def upper_bound(self) -> float:
        return self.level * (1 + self.tolerance_pct / 100)

    @property
    def lower_bound(self) -> float:
        return self.level * (1 - self.tolerance_pct / 100)

    def is_touched_by(self, candle: Candle) -> bool:
        return candle.low <= self.upper_bound and candle.high >= self.lower_bound

    @property
    def zone_key(self) -> str:
        return f"{self.zone_type.value}:{round(self.level, 6)}:{self.structure_event_candle_time}"


@dataclass
class PatternResult:
    pattern: PatternType
    valid: bool
    body_range_ratio: float = 0.0


@dataclass
class BiasResult:
    bias: Bias
    structure: StructureResult


@dataclass(frozen=True)
class FairValueGap:
    """
    Fair Value Gap (FVG) - imbalance 3-candle: gap antara wick candle[0] dan
    candle[2] yang tidak overlap sama sekali, terbentuk oleh gerakan impulsif
    di candle[1] (candle tengah).

    Bullish FVG : low candle[2] > high candle[0]  -> gap price di antaranya
    Bearish FVG : high candle[2] < low candle[0]  -> gap price di antaranya
    """

    direction: str  # "bullish" | "bearish"
    top: float
    bottom: float
    formed_at_candle_time: int  # open_time candle[1] (candle impulsif pembentuk gap)
    mitigated: bool = False  # True kalau harga sudah kembali mengisi sebagian/seluruh gap

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def size_pct(self) -> float:
        return (self.top - self.bottom) / self.bottom * 100 if self.bottom else 0.0

    def is_touched_by(self, candle: Candle) -> bool:
        return candle.low <= self.top and candle.high >= self.bottom


@dataclass(frozen=True)
class OrderBlock:
    """
    Order Block (OB) - candle terakhir berlawanan arah sebelum pergerakan
    impulsif (displacement) yang membentuk BOS/CHoCH. Zona [low, high] candle
    itu dianggap area akumulasi order institusional; retest ke zona ini jadi
    entry konfirmasi searah displacement.

    Bullish OB : candle bearish terakhir sebelum impuls naik yang break structure
    Bearish OB : candle bullish terakhir sebelum impuls turun yang break structure
    """

    direction: str  # "bullish" | "bearish"
    top: float
    bottom: float
    formed_at_candle_time: int  # open_time candle OB itu sendiri
    structure_event: StructureEvent = StructureEvent.NONE
    mitigated: bool = False

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2

    def is_touched_by(self, candle: Candle) -> bool:
        return candle.low <= self.top and candle.high >= self.bottom


@dataclass(frozen=True)
class LiquiditySweep:
    """
    Liquidity sweep - wick menembus equal-highs/equal-lows (kumpulan swing
    dengan level yang hampir sama, tempat stop-loss retail berkumpul) lalu
    close kembali ke dalam range, indikasi stop hunt sebelum reversal.
    """

    direction: str  # "bullish" (sweep low -> reversal naik) | "bearish" (sweep high -> reversal turun)
    swept_level: float
    wick_extreme: float  # harga terjauh wick yang menembus level
    candle_time: int


@dataclass(frozen=True)
class VolumeProfileLevel:
    """Satu bucket harga dalam Volume Profile, dengan volume beli/jual terpisah."""

    price_low: float
    price_high: float
    buy_volume: float
    sell_volume: float

    @property
    def total_volume(self) -> float:
        return self.buy_volume + self.sell_volume

    @property
    def mid(self) -> float:
        return (self.price_low + self.price_high) / 2


@dataclass
class VolumeProfileResult:
    levels: List[VolumeProfileLevel] = field(default_factory=list)
    poc_price: Optional[float] = None  # Point of Control - level dengan volume tertinggi
    imbalance: str = "neutral"  # "buy_imbalance" | "sell_imbalance" | "neutral"


@dataclass
class ScoreComponent:
    """Satu baris checklist di panel sinyal (label + status + deskripsi singkat)."""

    label: str          # mis. "Market Structure", "Liquidity", "FVG", "Order Block", "Volume Profile"
    valid: bool
    detail: str          # mis. "Uptrend", "Liquidity Sweep", "Valid", "Bullish OB", "Buy Imbalance"
    weight: float = 1.0


@dataclass
class ScoreResult:
    score: float          # 0-10
    confidence_pct: float  # 0-100
    components: List[ScoreComponent] = field(default_factory=list)


@dataclass
class Signal:
    market_id: str
    symbol: str
    market: str
    timeframe: str
    direction: Direction
    m15_bias: Bias
    price: float
    zone_type: str
    zone_level: float
    structure_event: str
    pattern: str
    candle_time_iso: str
    candle_open_time_ms: int
    signal_key: str
    cooldown_key: str
    # --- risk management (upgrade) ---
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    risk_reward_1: Optional[float] = None
    risk_reward_2: Optional[float] = None
    atr: Optional[float] = None
    zone_tolerance_pct_used: Optional[float] = None
    # --- scoring ICT full suite (upgrade 2) ---
    confidence_pct: Optional[float] = None
    score: Optional[float] = None
    checklist: List[ScoreComponent] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "symbol": self.symbol,
            "market": self.market,
            "timeframe": self.timeframe,
            "direction": self.direction.value,
            "m15_bias": self.m15_bias.value,
            "price": self.price,
            "zone": {"type": self.zone_type, "level": self.zone_level},
            "structure_event": self.structure_event,
            "pattern": self.pattern,
            "candle_time": self.candle_time_iso,
            "risk": {
                "stop_loss": self.stop_loss,
                "take_profit_1": self.take_profit_1,
                "take_profit_2": self.take_profit_2,
                "risk_reward_1": self.risk_reward_1,
                "risk_reward_2": self.risk_reward_2,
                "atr": self.atr,
            },
            "scoring": {
                "confidence_pct": self.confidence_pct,
                "score": self.score,
                "checklist": [
                    {"label": c.label, "valid": c.valid, "detail": c.detail}
                    for c in self.checklist
                ],
            },
        }
