"""Trade types — enums and dataclasses for the trading engine."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import uuid


class TradeDirection(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeAction(str, Enum):
    OPEN = "open"
    CLOSE = "close"
    MODIFY = "modify"
    PARTIAL_CLOSE = "partial_close"


class LotSizingMode(str, Enum):
    MULTIPLIER = "multiplier"
    FIXED = "fixed"
    EQUITY_PERCENT = "equity_percent"
    CUSTOM_MAP = "custom_map"


class ExecutionPolicy(str, Enum):
    MATCH_MASTER = "match_master"
    FORCE_FOK = "force_fok"
    FORCE_IOC = "force_ioc"
    FOK_IOC_FALLBACK = "fok_ioc_fallback"


class OrderFillType(str, Enum):
    FOK = "fok"       # Fill or Kill
    IOC = "ioc"       # Immediate or Cancel
    RETURN = "return"  # Return remainder


@dataclass
class MasterTrade:
    """Represents a detected master trade event."""
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    ticket: int = 0
    login: int = 0
    symbol: str = ""
    direction: TradeDirection = TradeDirection.BUY
    action: TradeAction = TradeAction.OPEN
    volume: float = 0.0
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    comment: str = ""
    magic: int = 0


@dataclass
class SlaveOrder:
    """Order to be sent to a slave account."""
    slave_login: int = 0
    master_uuid: str = ""
    symbol: str = ""
    direction: TradeDirection = TradeDirection.BUY
    volume: float = 0.0
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    fill_type: OrderFillType = OrderFillType.FOK
    deviation: int = 50
    comment: str = ""


@dataclass
class RiskConfig:
    """Per-slave risk configuration."""
    enabled: bool = True
    lot_mode: LotSizingMode = LotSizingMode.MULTIPLIER
    lot_multiplier: float = 1.0
    fixed_lot: float = 0.01
    equity_percent: float = 1.0
    custom_lot_map: dict = field(default_factory=dict)
    execution_policy: ExecutionPolicy = ExecutionPolicy.MATCH_MASTER
    max_slippage: int = 50
    max_spread: int = 100
    force_sl: Optional[float] = None
    force_tp: Optional[float] = None
    equity_threshold: float = 0.0  # Stop copying if equity drops below
    max_daily_drawdown_usd: float = 0.0
    max_daily_drawdown_pct: float = 0.0
    daily_target_profit: float = 0.0
    allowed_directions: str = "both"  # "buy", "sell", "both"
    symbol_mapping: dict = field(default_factory=dict)  # e.g. {"EURUSD": "EURUSDm"}


@dataclass
class TradeSnapshot:
    """Snapshot of current positions for comparison."""
    positions: dict = field(default_factory=dict)  # ticket -> position data
    orders: dict = field(default_factory=dict)      # ticket -> order data
    timestamp: float = 0.0
