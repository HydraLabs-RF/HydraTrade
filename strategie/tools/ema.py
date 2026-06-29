"""
EMA (Exponential Moving Average).

One theme, full service: latest value, the full EMA series, and a convenience
helper to run it straight on candle closes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from data.candle import Candle


@dataclass
class EMAResult:
    value: float          # latest EMA
    values: List[float]   # full EMA series (from the first valid point)


class EMAIndicator:
    def __init__(self, period: int):
        self.period = period

    def calculate(self, values: List[float]) -> Optional[EMAResult]:
        """EMA over a list of floats (seeded with an SMA of the first `period`)."""
        if len(values) < self.period:
            return None
        k = 2.0 / (self.period + 1.0)
        series: List[float] = [sum(values[:self.period]) / self.period]
        for v in values[self.period:]:
            series.append(v * k + series[-1] * (1.0 - k))
        return EMAResult(value=series[-1], values=series)

    def close(self, candles: List[Candle]) -> Optional[EMAResult]:
        """EMA over candle closes."""
        return self.calculate([c.close for c in candles])


def close_ema(candles: List[Candle], period: int) -> Optional[float]:
    """Latest EMA of candle closes (convenience for strategies)."""
    res = EMAIndicator(period).close(candles)
    return res.value if res else None
