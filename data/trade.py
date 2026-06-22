from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import MetaTrader5 as mt5

class MarketPhase(Enum):
    TREND = "trend"
    RANGE = "range"

class TradeStatus(Enum):
    OPEN = "open"
    RUNNING = "running"
    TRAILING = "trailing"
    CLOSED = "closed"
    STOPPED_OUT = "stopped_out"
    TAKE_PROFIT = "take_profit"

class TradeAction(Enum):
    PENDING = mt5.TRADE_ACTION_PENDING
    PENDING_MODIFY = mt5.TRADE_ACTION_MODIFY
    PENDING_REMOVE = mt5.TRADE_ACTION_REMOVE
    ACTION = mt5.TRADE_ACTION_DEAL
    ACTION_MODIFY_SL_TP = mt5.TRADE_ACTION_SLTP

class TradeType(Enum):
    BUY = mt5.ORDER_TYPE_BUY
    BUY_LIMIT = mt5.ORDER_TYPE_BUY_LIMIT
    BUY_STOP = mt5.ORDER_TYPE_BUY_STOP
    BUY_STOP_LIMIT = mt5.ORDER_TYPE_BUY_STOP_LIMIT
    SELL = mt5.ORDER_TYPE_SELL
    SELL_LIMIT = mt5.ORDER_TYPE_SELL_LIMIT
    SELL_STOP = mt5.ORDER_TYPE_SELL_STOP
    SELL_STOP_LIMIT = mt5.ORDER_TYPE_SELL_STOP_LIMIT


LONG_TYPES = frozenset({
    TradeType.BUY, TradeType.BUY_LIMIT, TradeType.BUY_STOP, TradeType.BUY_STOP_LIMIT,
})
SHORT_TYPES = frozenset({
    TradeType.SELL, TradeType.SELL_LIMIT, TradeType.SELL_STOP, TradeType.SELL_STOP_LIMIT,
})

@dataclass
class Trade:
    symbol: str
    type: TradeType
    action: TradeAction
    ticket: int
    entry_price: float
    volume: float
    volume_initial: float | None = None

    comment: str | None = None
    market_phase: MarketPhase | None = None
    trigger_price: float | None = None  # stop trigger for STOP_LIMIT orders

    stop_loss: float | None = None
    take_profit: float | None = None
    initial_stop_loss: float | None = None
    exit_price: float | None = None

    initial_time: datetime | None = None
    open_time: datetime | None = None
    close_time: datetime | None = None

    status: TradeStatus = TradeStatus.OPEN

    current_price: float | None = None
    pnl: float | None = None

    trailing_stop: float | None = None
    trailing_active: bool = False

    notes: str | None = None
    trailing_time: datetime | None = None