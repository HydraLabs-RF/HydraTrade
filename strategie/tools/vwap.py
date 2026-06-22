from typing import List, Optional
from data.candle import Candle


class VWAPEngine:

    def __init__(self):
        self.cum_pv = 0.0   # price * volume
        self.cum_v = 0.0    # volume

        self.vwap = None

    # -----------------------------
    # RESET (z.B. neuer Trading Day)
    # -----------------------------
    def reset(self):
        self.cum_pv = 0.0
        self.cum_v = 0.0
        self.vwap = None

    # -----------------------------
    # UPDATE (ein Candle rein)
    # -----------------------------
    def update(self, candle: Candle) -> float:

        price = (candle.high + candle.low + candle.close) / 3.0
        volume = float(candle.tick_volume)

        if volume == 0:
            return self.vwap

        self.cum_pv += price * volume
        self.cum_v += volume

        self.vwap = self.cum_pv / self.cum_v
        return self.vwap

    # -----------------------------
    # BATCH (historische Berechnung)
    # -----------------------------
    def calculate(self, candles: List[Candle]) -> List[Optional[float]]:

        self.reset()

        vwap_series = []

        for c in candles:
            vwap_series.append(self.update(c))

        return vwap_series