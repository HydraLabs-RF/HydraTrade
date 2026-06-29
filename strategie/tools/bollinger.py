"""
Bollinger Bands.

SMA of close +/- k * standard deviation. One theme, full service: middle band,
upper/lower bands, bandwidth and a squeeze check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from data.candle import Candle


@dataclass
class BollingerBands:
    mid: float
    upper: float
    lower: float
    std: float

    @property
    def bandwidth(self) -> float:
        """Relative band width (upper-lower)/mid — low value = squeeze."""
        return (self.upper - self.lower) / self.mid if self.mid else 0.0


class BollingerIndicator:
    def __init__(self, period: int = 20, k: float = 2.0):
        self.period = period
        self.k = k

    def calculate(self, candles: List[Candle]) -> Optional[BollingerBands]:
        """Bollinger bands on the latest closed bar. Returns None if too little data
        or zero volatility."""
        if len(candles) < self.period:
            return None
        closes = [c.close for c in candles[-self.period:]]
        mid = sum(closes) / self.period
        std = (sum((x - mid) ** 2 for x in closes) / self.period) ** 0.5
        if std <= 0:
            return None
        return BollingerBands(mid=mid, upper=mid + self.k * std,
                              lower=mid - self.k * std, std=std)
