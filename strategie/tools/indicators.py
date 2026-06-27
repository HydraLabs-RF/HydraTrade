"""
Additional trend indicators for benchmark variants (Group 2 + 3).

Deliberately rule-based (no chart fitting): EMA, ADX, Donchian channel and
Chandelier exit. All functions operate on a candle list, analogous to ATR.py.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from data.candle import Candle


def ema(values: List[float], period: int) -> Optional[float]:
    """Exponential moving average of the last value."""
    if not values or len(values) < period:
        return None
    k = 2.0 / (period + 1.0)
    seed = sum(values[:period]) / period
    e = seed
    for v in values[period:]:
        e = v * k + e * (1.0 - k)
    return e


def ema_series(values: List[float], period: int) -> List[float]:
    """Full EMA series (same length from the first valid point onward)."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1.0)
    out: List[float] = [sum(values[:period]) / period]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1.0 - k))
    return out


def close_ema(candles: List[Candle], period: int) -> Optional[float]:
    return ema([c.close for c in candles], period)


def _wilder_smooth(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return []
    out: List[float] = [sum(values[:period])]
    for v in values[period:]:
        out.append(out[-1] - (out[-1] / period) + v)
    return out


def adx(candles: List[Candle], period: int = 14) -> Optional[float]:
    """Average Directional Index (Wilder). Measures trend strength, not direction."""
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
    for trv, pv, mv in zip(tr_s, plus_s, minus_s):
        if trv <= 0:
            continue
        di_plus = 100.0 * pv / trv
        di_minus = 100.0 * mv / trv
        denom = di_plus + di_minus
        if denom <= 0:
            dx.append(0.0)
        else:
            dx.append(100.0 * abs(di_plus - di_minus) / denom)

    if len(dx) < period:
        return None
    adx_val = sum(dx[:period]) / period
    for v in dx[period:]:
        adx_val = (adx_val * (period - 1) + v) / period
    return adx_val


def efficiency_ratio(candles: List[Candle], period: int = 20) -> Optional[float]:
    """Kaufman Efficiency Ratio on close: |net move| / sum(|steps|).

    ~1.0 = very direct (clean) trend, ~0.0 = back-and-forth (chop). Direct
    regime filter for trend following: only trade when the market is actually
    moving, instead of binding to ADX (lags, also reacts to directional noise).
    """
    if len(candles) < period + 1:
        return None
    closes = [c.close for c in candles[-(period + 1):]]
    net = abs(closes[-1] - closes[0])
    path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
    if path <= 0:
        return None
    return net / path


def donchian(candles: List[Candle], period: int, exclude_current: bool = True) -> Optional[Tuple[float, float]]:
    """Donchian channel (upper/lower band). exclude_current for breakout logic."""
    window = candles[:-1] if exclude_current else candles
    if len(window) < period:
        return None
    last = window[-period:]
    return (max(c.high for c in last), min(c.low for c in last))


def chandelier_exit(
    candles: List[Candle],
    atr: float,
    multiplier: float,
    lookback: int,
    for_long: bool,
    digits: int,
) -> Optional[float]:
    """Chandelier exit: highest high (long) or lowest low (short) minus/plus N*ATR."""
    if atr <= 0 or len(candles) < lookback:
        return None
    window = candles[-lookback:]
    if for_long:
        return round(max(c.high for c in window) - multiplier * atr, digits)
    return round(min(c.low for c in window) + multiplier * atr, digits)
