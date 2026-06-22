from enum import Enum
import MetaTrader5 as mt5

class TimeFrame(Enum):
    M1 = mt5.TIMEFRAME_M1
    M5 = mt5.TIMEFRAME_M5
    M15 = mt5.TIMEFRAME_M15
    H1 = mt5.TIMEFRAME_H1
    H4 = mt5.TIMEFRAME_H4
    D1 = mt5.TIMEFRAME_D1

class StructureState(Enum):
    SEEK_HIGH = "SEEK_HIGH"
    SEEK_LOW = "SEEK_LOW"


class MarketStructure(Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    CHOPPY = "CHOPPY"

class MarketBias(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"

class StrategyContext(Enum):

    TREND_LONG = "TREND_LONG"
    TREND_SHORT = "TREND_SHORT"

    RANGE_LONG = "RANGE_LONG"
    RANGE_SHORT = "RANGE_SHORT"

    CHOPPY = "CHOPPY"

    NO_TRADE = "NO_TRADE"