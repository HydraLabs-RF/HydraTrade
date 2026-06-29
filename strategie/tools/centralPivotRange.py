"""
Central Pivot Range (CPR).

Daily pivot P with a Top/Bottom Central band: BC = (H+L)/2, TC = 2*P - BC.
A narrow CPR signals a trend day, a wide CPR a range day. One theme, full service:
compute from raw HLC or directly from daily candles, plus a width helper.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from data.candle import Candle


@dataclass
class CPRLevels:
    pivot: float
    top: float       # max(TC, BC)
    bottom: float    # min(TC, BC)

    @property
    def width(self) -> float:
        return self.top - self.bottom


class CentralPivotRangeIndicator:
    def calculate(self, high: float, low: float, close: float) -> CPRLevels:
        pivot = (high + low + close) / 3.0
        bc = (high + low) / 2.0
        tc = 2 * pivot - bc
        return CPRLevels(pivot=pivot, top=max(tc, bc), bottom=min(tc, bc))

    def from_daily_candles(self, daily: List[Candle]) -> Optional[CPRLevels]:
        """CPR from the last fully-closed daily bar (daily[-2])."""
        if not daily or len(daily) < 2:
            return None
        prior = daily[-2]
        return self.calculate(prior.high, prior.low, prior.close)
