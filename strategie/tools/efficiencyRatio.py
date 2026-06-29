"""
Kaufman Efficiency Ratio.

|net move| / sum(|steps|) over the period, on close. ~1.0 = clean directional
trend, ~0.0 = back-and-forth chop. A direct regime filter (unlike ADX it does not
lag and does not reward directional noise).
"""

from __future__ import annotations

from typing import List, Optional

from data.candle import Candle


class EfficiencyRatioIndicator:
    def __init__(self, period: int = 20):
        self.period = period

    def calculate(self, candles: List[Candle]) -> Optional[float]:
        if len(candles) < self.period + 1:
            return None
        closes = [c.close for c in candles[-(self.period + 1):]]
        net = abs(closes[-1] - closes[0])
        path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
        if path <= 0:
            return None
        return net / path
