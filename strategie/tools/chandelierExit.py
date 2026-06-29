"""
Chandelier Exit.

A volatility trailing stop: highest high (long) minus N*ATR, or lowest low (short)
plus N*ATR, over a lookback window. Takes the ATR explicitly so the caller controls
the timeframe; `from_candles` is a convenience that derives ATR via ATRIndicator.
"""

from __future__ import annotations

from typing import List, Optional

from data.candle import Candle
from strategie.tools.ATR import ATRIndicator


class ChandelierExitIndicator:
    def __init__(self, multiplier: float = 3.0, lookback: int = 22):
        self.multiplier = multiplier
        self.lookback = lookback

    def calculate(self, candles: List[Candle], atr: float, for_long: bool,
                  digits: int) -> Optional[float]:
        if atr <= 0 or len(candles) < self.lookback:
            return None
        window = candles[-self.lookback:]
        if for_long:
            return round(max(c.high for c in window) - self.multiplier * atr, digits)
        return round(min(c.low for c in window) + self.multiplier * atr, digits)

    def from_candles(self, candles: List[Candle], for_long: bool, digits: int,
                     atr_period: int = 14) -> Optional[float]:
        atr_res = ATRIndicator(period=atr_period).calculate(candles)
        if not atr_res or atr_res.value <= 0:
            return None
        return self.calculate(candles, atr_res.value, for_long, digits)
