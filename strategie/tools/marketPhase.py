"""
Market Phase Classifier.

Labels the current market into one of four phases from DAILY candles (no lookahead,
uses only closed D1 bars). The discriminator was found empirically: trend strength
(ADX) separates trending from non-trending; the Lo-MacKinlay variance ratio (VR)
then separates a mean-reverting FLAT range (VR<1, fades revert) from a momentum-y
WHIPSAW (VR>=1, price overshoots without reverting).

  ADX >= ADX_TREND                         -> TREND_UP / TREND_DOWN (by close vs EMA)
  ADX <  ADX_TREND and VR >= VR_WHIPSAW     -> WHIPSAW   (overshoot, fades get chopped)
  ADX <  ADX_TREND and VR <  VR_WHIPSAW     -> FLAT_RANGE (mean-reverting, fades work)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from data.candle import Candle
from strategie.tools.adx import ADXIndicator
from strategie.tools.ema import EMAIndicator


class Phase(Enum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    FLAT_RANGE = "flat_range"
    WHIPSAW = "whipsaw"


@dataclass
class PhaseResult:
    phase: Phase
    adx: float
    vr: Optional[float]
    direction: int   # +1 up, -1 down, 0 flat (close vs EMA)


def variance_ratio(returns: List[float], q: int = 5) -> Optional[float]:
    """Lo-MacKinlay variance ratio VR(q) = Var(q-period sums) / (q * Var(1-period)).
    >1 = trending/momentum (overshoot), <1 = mean-reverting."""
    n = len(returns)
    if n < q * 3:
        return None
    m1 = sum(returns) / n
    v1 = sum((r - m1) ** 2 for r in returns) / n
    if v1 <= 0:
        return None
    qsums = [sum(returns[i:i + q]) for i in range(0, n - q + 1)]
    mq = sum(qsums) / len(qsums)
    vq = sum((s - mq) ** 2 for s in qsums) / len(qsums)
    return vq / (q * v1)


class MarketPhaseClassifier:
    def __init__(self, adx_period: int = 14, adx_trend: float = 25.0,
                 vr_lookback: int = 30, vr_q: int = 5, vr_whipsaw: float = 1.0,
                 ema_period: int = 50):
        self.adx_period = adx_period
        self.adx_trend = adx_trend
        self.vr_lookback = vr_lookback
        self.vr_q = vr_q
        self.vr_whipsaw = vr_whipsaw
        self.ema_period = ema_period

    def calculate(self, daily: List[Candle]) -> Optional[PhaseResult]:
        if len(daily) < max(self.adx_period * 2 + 1, self.vr_lookback + 1, self.ema_period + 1):
            return None
        adx_res = ADXIndicator(self.adx_period).calculate(daily[-60:] if len(daily) >= 60 else daily)
        if adx_res is None:
            return None
        adx = adx_res.value

        closes = [c.close for c in daily[-(self.vr_lookback + 1):]]
        rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
        vr = variance_ratio(rets, self.vr_q)

        ema_res = EMAIndicator(self.ema_period).close(daily)
        ema = ema_res.value if ema_res else None
        last = daily[-1].close
        direction = 0 if ema is None else (1 if last > ema else (-1 if last < ema else 0))

        if adx >= self.adx_trend:
            phase = Phase.TREND_UP if direction >= 0 else Phase.TREND_DOWN
        elif vr is not None and vr >= self.vr_whipsaw:
            phase = Phase.WHIPSAW
        else:
            phase = Phase.FLAT_RANGE
        return PhaseResult(phase=phase, adx=adx, vr=vr, direction=direction)
