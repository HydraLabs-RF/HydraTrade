"""
SuperTrend indicator (TradingView-style).

Uses ATR bands around the median price; flips direction when price crosses the band.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from data.candle import Candle
from strategie.tools.ATR import ATRIndicator


@dataclass
class SuperTrendState:
    value: float
    direction: int  # 1 = bullish (long), -1 = bearish (short)


def supertrend(
    candles: List[Candle],
    period: int = 10,
    multiplier: float = 3.0,
) -> Optional[SuperTrendState]:
    """Returns the SuperTrend line and direction on the latest closed bar."""
    if len(candles) < period + 2:
        return None

    atr_ind = ATRIndicator()
    atr_result = atr_ind.calculate(candles)
    if not atr_result or atr_result.value <= 0:
        return None

    # Walk forward to get stable direction (needs history for flip logic)
    direction = 1
    st_line = candles[0].close

    for i in range(period, len(candles)):
        window = candles[: i + 1]
        atr_res = atr_ind.calculate(window)
        if not atr_res or atr_res.value <= 0:
            continue
        atr = atr_res.value
        hl2 = (window[-1].high + window[-1].low) / 2.0
        upper = hl2 + multiplier * atr
        lower = hl2 - multiplier * atr
        close = window[-1].close

        if direction == 1:
            st_line = max(lower, st_line if i > period else lower)
            if close < st_line:
                direction = -1
                st_line = upper
        else:
            st_line = min(upper, st_line if i > period else upper)
            if close > st_line:
                direction = 1
                st_line = lower

    return SuperTrendState(value=round(st_line, 5), direction=direction)
