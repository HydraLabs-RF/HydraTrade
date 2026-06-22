import math
from tools.vwap import VWAPEngine
from data.candle import Candle


class VWAPBandsEngine(VWAPEngine):

    def __init__(self, stdev_mult=1.0):
        super().__init__()
        self.values = []
        self.stdev_mult = stdev_mult

    def update(self, candle: Candle):

        price = (candle.high + candle.low + candle.close) / 3.0
        volume = float(candle.tick_volume)

        if volume == 0:
            return self.vwap, None, None

        self.cum_pv += price * volume
        self.cum_v += volume

        self.vwap = self.cum_pv / self.cum_v

        # store for deviation
        self.values.append(price)

        mean = self.vwap
        variance = sum((x - mean) ** 2 for x in self.values) / len(self.values)
        stdev = math.sqrt(variance)

        upper = self.vwap + self.stdev_mult * stdev
        lower = self.vwap - self.stdev_mult * stdev

        return self.vwap, upper, lower