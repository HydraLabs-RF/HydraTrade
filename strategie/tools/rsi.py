"""
RSI (Relative Strength Index).

Wilder/Connors-style oscillator on close. One theme, full service: latest value,
the full series and a convenience overbought/oversold check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from data.candle import Candle


@dataclass
class RSIResult:
    value: float          # latest RSI
    values: List[float]   # RSI series (aligned to the smoothed range)


class RSIIndicator:
    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, candles: List[Candle]) -> Optional[RSIResult]:
        """RSI via simple average of gains/losses over the period (Connors-compatible
        for short periods like 2). Returns None if not enough candles."""
        if len(candles) < self.period + 1:
            return None
        closes = [c.close for c in candles]
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

        values: List[float] = []
        for end in range(self.period, len(deltas) + 1):
            window = deltas[end - self.period:end]
            gains = sum(d for d in window if d > 0)
            losses = -sum(d for d in window if d < 0)
            if losses == 0:
                values.append(100.0)
            else:
                rs = (gains / self.period) / (losses / self.period)
                values.append(100.0 - 100.0 / (1.0 + rs))
        if not values:
            return None
        return RSIResult(value=values[-1], values=values)

    def is_oversold(self, candles: List[Candle], level: float) -> Optional[bool]:
        res = self.calculate(candles)
        return None if res is None else res.value <= level

    def is_overbought(self, candles: List[Candle], level: float) -> Optional[bool]:
        res = self.calculate(candles)
        return None if res is None else res.value >= level
