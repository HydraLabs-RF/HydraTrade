from typing import Dict, List, Optional

from data.candle import Candle
from data.models import VolumeNode


class VolumeProfile:

    def __init__(self, bin_size: float):
        self.bin_size = bin_size
        self.profile: Dict[float, float] = {}

    # -----------------------------
    # internal helper
    # -----------------------------
    def _get_bin(self, price: float) -> float:
        return round(price / self.bin_size) * self.bin_size

    # -----------------------------
    # add single candle
    # -----------------------------
    def add_candle(self, candle: Candle):
        low = candle.low
        high = candle.high
        volume = candle.tick_volume

        steps = max(1, int((high - low) / self.bin_size))
        vol_per_bin = volume / steps

        for i in range(steps + 1):
            price = low + i * self.bin_size
            bin_price = self._get_bin(price)

            self.profile[bin_price] = (
                self.profile.get(bin_price, 0) + vol_per_bin
            )

    # -----------------------------
    # build full profile
    # -----------------------------
    def build(self, candles: List[Candle]) -> Dict[float, float]:
        for c in candles:
            self.add_candle(c)

        return self.profile

    # -----------------------------
    # POC
    # -----------------------------
    def get_poc(self) -> Optional[VolumeNode]:
        if not self.profile:
            return None

        price = max(self.profile, key=self.profile.get)
        return VolumeNode(price=price, volume=self.profile[price])

    # -----------------------------
    # nearest node
    # -----------------------------
    def get_nearest_node(
        self,
        price: float,
        direction: str = "both"
    ) -> Optional[VolumeNode]:

        if not self.profile:
            return None

        levels = sorted(self.profile.items(), key=lambda x: x[0])

        above = None
        below = None

        for p, v in levels:
            if p <= price:
                below = (p, v)
            elif p > price and above is None:
                above = (p, v)

        if direction == "above":
            return VolumeNode(*above) if above else None

        if direction == "below":
            return VolumeNode(*below) if below else None

        candidates = [above, below]
        candidates = [c for c in candidates if c is not None]

        if not candidates:
            return None

        return min(
            (VolumeNode(p, v) for p, v in candidates),
            key=lambda x: abs(x.price - price)
        )