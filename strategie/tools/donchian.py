"""
Donchian Channel.

Highest high / lowest low over the lookback period. `exclude_current` drops the
forming bar so the channel can be used for clean breakout logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from data.candle import Candle


@dataclass
class DonchianChannel:
    upper: float
    lower: float

    @property
    def mid(self) -> float:
        return (self.upper + self.lower) / 2.0


class DonchianIndicator:
    def __init__(self, period: int, exclude_current: bool = True):
        self.period = period
        self.exclude_current = exclude_current

    def calculate(self, candles: List[Candle]) -> Optional[DonchianChannel]:
        window = candles[:-1] if self.exclude_current else candles
        if len(window) < self.period:
            return None
        last = window[-self.period:]
        return DonchianChannel(upper=max(c.high for c in last),
                               lower=min(c.low for c in last))
