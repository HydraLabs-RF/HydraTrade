from dataclasses import dataclass

from datetime import datetime


@dataclass
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int

    def __repr__(self):

        return (
            f"Candle("
            f"time={self.time.strftime('%Y-%m-%d %H:%M')}, "
            f"open={self.open}, "
            f"high={self.high}, "
            f"low={self.low}, "
            f"close={self.close}, "
            f"volume={self.tick_volume}, "
            f"spread={self.spread}, "
            f"real_volume={self.real_volume}"
            f")"
        )