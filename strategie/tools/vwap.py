from dataclasses import dataclass
from typing import List, Optional
from data.candle import Candle


@dataclass
class VWAPBands:
    vwap: float
    upper: float
    lower: float


class VWAPEngine:

    def __init__(self):
        self.cum_pv = 0.0   # price * volume
        self.cum_v = 0.0    # volume

        self.vwap = None

    def reset(self):
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.vwap = None

    def update(self, candle: Candle) -> float:

        price = (candle.high + candle.low + candle.close) / 3.0
        volume = float(candle.tick_volume)

        if volume == 0:
            return self.vwap

        self.cum_pv += price * volume
        self.cum_v += volume

        self.vwap = self.cum_pv / self.cum_v
        return self.vwap

    def calculate(self, candles: List[Candle]) -> List[Optional[float]]:

        self.reset()

        vwap_series = []

        for c in candles:
            vwap_series.append(self.update(c))

        return vwap_series

    def bands(self, candles: List[Candle], mult: float = 2.0) -> Optional[VWAPBands]:
        """Session-anchored VWAP plus +/- mult*std bands from intraday candles."""
        if not candles:
            return None
        self.reset()
        typs = []
        for c in candles:
            self.update(c)
            typs.append((c.high + c.low + c.close) / 3.0)
        if self.vwap is None or self.cum_v <= 0 or len(typs) < 5:
            return None
        std = (sum((x - self.vwap) ** 2 for x in typs) / len(typs)) ** 0.5
        return VWAPBands(self.vwap, self.vwap + mult * std, self.vwap - mult * std)
