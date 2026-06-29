"""
Stochastic Oscillator.

Fast %K = (close - lowN) / (highN - lowN) * 100, plus %D (SMA of %K). One theme,
full service: %K, %D and overbought/oversold checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from data.candle import Candle


@dataclass
class StochasticResult:
    k: float
    d: Optional[float]   # SMA(k, d_period); None if not enough history


class StochasticIndicator:
    def __init__(self, period: int = 14, d_period: int = 3):
        self.period = period
        self.d_period = d_period

    def _k_at(self, candles: List[Candle]) -> Optional[float]:
        if len(candles) < self.period:
            return None
        window = candles[-self.period:]
        hi = max(c.high for c in window)
        lo = min(c.low for c in window)
        if hi <= lo:
            return None
        return (window[-1].close - lo) / (hi - lo) * 100.0

    def calculate(self, candles: List[Candle]) -> Optional[StochasticResult]:
        """%K on the latest bar plus %D (SMA of the last d_period %K values)."""
        k = self._k_at(candles)
        if k is None:
            return None
        ks: List[float] = []
        for end in range(len(candles) - self.d_period + 1, len(candles) + 1):
            if end < self.period:
                continue
            kv = self._k_at(candles[:end])
            if kv is not None:
                ks.append(kv)
        d = sum(ks) / len(ks) if len(ks) == self.d_period else None
        return StochasticResult(k=k, d=d)

    def is_oversold(self, candles: List[Candle], level: float) -> Optional[bool]:
        res = self.calculate(candles)
        return None if res is None else res.k <= level

    def is_overbought(self, candles: List[Candle], level: float) -> Optional[bool]:
        res = self.calculate(candles)
        return None if res is None else res.k >= level
