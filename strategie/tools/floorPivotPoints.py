"""
Floor-Trader Pivot Points (classic daily pivots).

Pivot P from prior-day HLC plus R1/S1/R2/S2. One theme, full service: compute from
raw HLC or directly from a list of daily candles (uses the last fully-closed bar).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from data.candle import Candle


@dataclass
class FloorPivotLevels:
    pivot: float
    r1: float
    s1: float
    r2: float
    s2: float


class FloorPivotIndicator:
    def calculate(self, high: float, low: float, close: float) -> FloorPivotLevels:
        p = (high + low + close) / 3.0
        r1 = 2 * p - low
        s1 = 2 * p - high
        r2 = p + (high - low)
        s2 = p - (high - low)
        return FloorPivotLevels(pivot=p, r1=r1, s1=s1, r2=r2, s2=s2)

    def from_daily_candles(self, daily: List[Candle]) -> Optional[FloorPivotLevels]:
        """Pivots from the last fully-closed daily bar (daily[-2])."""
        if not daily or len(daily) < 2:
            return None
        prior = daily[-2]
        return self.calculate(prior.high, prior.low, prior.close)
