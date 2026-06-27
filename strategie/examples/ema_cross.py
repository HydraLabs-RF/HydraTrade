"""
EXAMPLE STRATEGY — EMA Crossover

Demonstrates:
  - Market entry (TradeAction.ACTION) on a fast/slow EMA cross (H1)
  - Stop-loss and take-profit on new positions
  - Low trade frequency via cooldown and minimum EMA separation

NOT for production or live trading. Use as a template for your own strategies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.enums import TimeFrame
from data.trade import Trade, TradeAction, TradeStatus, TradeType
from strategie.examples.base import ExampleStrategyBase
from strategie.tools.indicators import close_ema


class ExampleEmaCross(ExampleStrategyBase):
    VARIANT_ID = "example_ema_cross"
    VARIANT_NAME = "Example: EMA Cross"
    VARIANT_GROUP = "Examples"

    FAST = 12
    SLOW = 26
    RR = 1.2
    MIN_SEP_PCT = 0.0008  # skip tiny crosses in chop

    def planTradeGrade_A(self, target_date_time: datetime | None) -> Optional[Trade]:
        t = self._now(target_date_time)
        if self._has_open_or_pending():
            return None
        if not self._cooldown_ok(t, minutes=720):
            return None
        if not self._once_per_bar(t):
            return None

        candles = self._get_candles(self.SIGNAL_TIMEFRAME, t, 80)
        if len(candles) < self.SLOW + 5:
            return None

        closes = [c.close for c in candles]
        fast_now = close_ema(candles, self.FAST)
        slow_now = close_ema(candles, self.SLOW)
        fast_prev = close_ema(candles[:-1], self.FAST)
        slow_prev = close_ema(candles[:-1], self.SLOW)
        if None in (fast_now, slow_now, fast_prev, slow_prev):
            return None

        bullish = fast_prev <= slow_prev and fast_now > slow_now
        bearish = fast_prev >= slow_prev and fast_now < slow_now
        if not bullish and not bearish:
            return None

        entry = closes[-1]
        if abs(fast_now - slow_now) < entry * self.MIN_SEP_PCT:
            return None

        symbol_info = self.liveDataAndTrading.get_symbol_info(self.symbol)
        entry = round(entry, symbol_info.digits)
        sl_dist = max(abs(fast_now - slow_now) * 1.5, entry * 0.0025)

        if bullish:
            trade_type = TradeType.BUY
            sl = round(entry - sl_dist, symbol_info.digits)
            tp = round(entry + sl_dist * self.RR, symbol_info.digits)
        else:
            trade_type = TradeType.SELL
            sl = round(entry + sl_dist, symbol_info.digits)
            tp = round(entry - sl_dist * self.RR, symbol_info.digits)

        volume = self._lot_size(sl_dist, symbol_info)
        if not volume:
            return None

        self._mark_trade_placed(t)
        return Trade(
            symbol=self.symbol,
            type=trade_type,
            action=TradeAction.ACTION,
            ticket=0,
            entry_price=entry,
            volume=volume,
            volume_initial=volume,
            stop_loss=sl,
            take_profit=tp,
            initial_stop_loss=sl,
            status=TradeStatus.RUNNING,
            comment=f"EXAMPLE ema_cross {'long' if bullish else 'short'}",
        )
