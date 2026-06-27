from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from data.candle import Candle
from core.enums import TimeFrame
from core.config import configConnection
from execution.live.mt5execution import MT5CExecution

@dataclass
class ATRResult:
    value: float
    values: List[float]  # ATR value history


class ATRIndicator:
    def __init__(self, period: int = 14, timeframe: TimeFrame = TimeFrame.H1):
        self.period = period
        self.timeframe = timeframe
        self.config = configConnection()
        # Instantiate execution layer for autonomous data access
        self.execution = MT5CExecution()

    def calculate_by_time(self, reference_time: Optional[datetime] = None) -> ATRResult:
        """
        Fetches the required historical candles independently using a
        datetime and calculates the ATR value.
        """
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)
        elif reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        # For Wilder's smoothing we need exactly:
        # 1 (for true range of the first comparison) + period (for initial ATR) + additional historical candles,
        # to build the smoothed value for the current target precisely.
        # A buffer of period * 2 ensures mathematically clean smoothing.
        needed_candles = self.period * 3

        candles = self.execution.getHistoricalCandles(
            timeframe=self.timeframe,
            reference_time=reference_time,
            candle_count=needed_candles,
            Symbol=self.config.getSymbol()
        )

        return self.calculate(candles)

    def calculate(self, candles: List[Candle]) -> ATRResult:
        """
        Core mathematical ATR calculation based on a provided candle list.
        If fewer candles than the standard period are passed, the calculation
        adapts dynamically to the available data.
        """
        # Absolute fallback: with fewer than 2 candles we cannot compute true range
        if len(candles) < 2:
            return ATRResult(value=0.0, values=[0.0])

        # 1. Compute all available true ranges
        true_ranges = []
        for i in range(1, len(candles)):
            current = candles[i]
            previous = candles[i - 1]

            tr = max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
            true_ranges.append(tr)

        # 2. Dynamic period adjustment
        # We can compute at most as many periods as we have true ranges.
        # If self.period = 14 but we only have 7 true ranges, we effectively use a period of 7.
        effective_period = min(self.period, len(true_ranges))

        atr_values = []

        # Initial ATR (simple average of the first 'effective_period' true ranges)
        first_atr = sum(true_ranges[:effective_period]) / effective_period
        atr_values.append(first_atr)

        # 3. Wilder's smoothing logic (only runs if remaining true ranges exist)
        for i in range(effective_period, len(true_ranges)):
            prev_atr = atr_values[-1]
            current_tr = true_ranges[i]

            # Use the adjusted effective period for smoothing
            atr = (prev_atr * (effective_period - 1) + current_tr) / effective_period
            atr_values.append(atr)

        return ATRResult(
            value=atr_values[-1],
            values=atr_values
        )