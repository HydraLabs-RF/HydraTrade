from typing import Dict, Optional
from datetime import datetime, timezone
from data.candle import Candle
from data.models import VolumeNode
from core.enums import TimeFrame
from core.config import configConnection

config = configConnection()

class SessionProfile:
    def __init__(self, bin_size: float):
        self.bin_size = bin_size
        self.profile: Dict[float, float] = {}

    def _get_bin(self, price: float) -> float:
        # Garantiert saubere mathematische Schritte basierend auf der bin_size
        return round(round(price / self.bin_size) * self.bin_size, 4)

    def add_candle(self, candle: Candle):
        low = candle.low
        high = candle.high
        volume = candle.tick_volume

        if volume <= 0:
            return

        steps = max(1, int(round((high - low) / self.bin_size)))
        vol_per_bin = volume / steps

        for i in range(steps):
            price = low + (i + 0.5) * self.bin_size
            bin_price = self._get_bin(price)
            # Runden auf 2 Nachkommastellen für saubere USD-Werte im Orderbuch
            bin_price = round(bin_price, 2)
            self.profile[bin_price] = self.profile.get(bin_price, 0.0) + vol_per_bin

    def build_for_specific_day(self, start_time: datetime, end_time: datetime) -> "SessionProfile":
        """Holt Daten für ein exaktes Zeitfenster und filtert gnadenlos alles außerhalb heraus"""
        from execution.live.mt5execution import MT5CExecution
        execution_layer = MT5CExecution()

        self.profile.clear()

        # Hole die Kerzen vom MT5-Layer
        candles = execution_layer.getCandlesBetween(
            timeframe=TimeFrame.M15, 
            start=start_time, 
            end=end_time, 
            Symbol=config.getSymbol()
        )

        for candle in candles:
            candle_time = candle.time
            if candle_time.tzinfo is None:
                candle_time = candle_time.replace(tzinfo=timezone.utc)

            # STRIKTE FILTERUNG: Gehört die Kerze sekundennahe in DIESEN Tag?
            if start_time <= candle_time <= end_time:
                self.add_candle(candle)

        return self

    def get_poc(self) -> Optional[VolumeNode]:
        if not self.profile:
            return None
        price = max(self.profile, key=self.profile.get)
        return VolumeNode(price=price, volume=self.profile[price])

    def get_nearest_node(self, price: float, direction: str = "both") -> Optional[VolumeNode]:
        if not self.profile:
            return None

        levels = sorted(self.profile.keys())
        below = [p for p in levels if p <= price]
        above = [p for p in levels if p > price]

        node_below = VolumeNode(price=below[-1], volume=self.profile[below[-1]]) if below else None
        node_above = VolumeNode(price=above[0], volume=self.profile[above[0]]) if above else None

        if direction == "above":
            return node_above
        if direction == "below":
            return node_below

        candidates = [n for n in [node_below, node_above] if n is not None]
        if not candidates:
            return None
            
        return min(candidates, key=lambda x: abs(x.price - price))