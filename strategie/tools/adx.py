"""
ADX (Average Directional Index, Wilder).

Measures trend strength (not direction). One theme, full service: the ADX value
plus the directional indicators +DI / -DI on the latest bar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from data.candle import Candle


@dataclass
class ADXResult:
    value: float       # ADX (trend strength)
    plus_di: float     # +DI on the latest bar
    minus_di: float    # -DI on the latest bar


def _wilder_smooth(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return []
    out: List[float] = [sum(values[:period])]
    for v in values[period:]:
        out.append(out[-1] - (out[-1] / period) + v)
    return out


class ADXIndicator:
    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, candles: List[Candle]) -> Optional[ADXResult]:
        period = self.period
        if len(candles) < period * 2 + 1:
            return None

        plus_dm: List[float] = []
        minus_dm: List[float] = []
        tr: List[float] = []
        for i in range(1, len(candles)):
            cur, prev = candles[i], candles[i - 1]
            up_move = cur.high - prev.high
            down_move = prev.low - cur.low
            plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
            minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0.0)
            tr.append(max(
                cur.high - cur.low,
                abs(cur.high - prev.close),
                abs(cur.low - prev.close),
            ))

        tr_s = _wilder_smooth(tr, period)
        plus_s = _wilder_smooth(plus_dm, period)
        minus_s = _wilder_smooth(minus_dm, period)
        if not tr_s or len(tr_s) != len(plus_s):
            return None

        dx: List[float] = []
        last_di_plus = last_di_minus = 0.0
        for trv, pv, mv in zip(tr_s, plus_s, minus_s):
            if trv <= 0:
                continue
            di_plus = 100.0 * pv / trv
            di_minus = 100.0 * mv / trv
            last_di_plus, last_di_minus = di_plus, di_minus
            denom = di_plus + di_minus
            dx.append(0.0 if denom <= 0 else 100.0 * abs(di_plus - di_minus) / denom)

        if len(dx) < period:
            return None
        adx_val = sum(dx[:period]) / period
        for v in dx[period:]:
            adx_val = (adx_val * (period - 1) + v) / period
        return ADXResult(value=adx_val, plus_di=last_di_plus, minus_di=last_di_minus)
