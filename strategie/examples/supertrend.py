"""
EXAMPLE STRATEGY — SuperTrend (TradingView-style)

Demonstrates:
  - Stop entry orders (TradeType.BUY_STOP / SELL_STOP) on trend flips
  - Pending order placement at the SuperTrend line

NOT for production or live trading. Use as a template for your own strategies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.enums import TimeFrame
from data.trade import Trade, TradeAction, TradeStatus, TradeType
from strategie.examples.base import ExampleStrategyBase
from strategie.tools.supertrend import supertrend


class ExampleSuperTrend(ExampleStrategyBase):
    VARIANT_ID = "example_supertrend"
    VARIANT_NAME = "Example: SuperTrend"
    VARIANT_GROUP = "Examples"

    PERIOD = 10
    MULT = 3.0
    RR = 2.5

    def planTradeGrade_A(self, target_date_time: datetime | None) -> Optional[Trade]:
        t = self._now(target_date_time)
        if self._has_open_or_pending():
            return None
        if not self._once_per_bar(t):
            return None

        candles = self._get_candles(TimeFrame.M15, t, 150)
        st_now = supertrend(candles, self.PERIOD, self.MULT)
        st_prev = supertrend(candles[:-1], self.PERIOD, self.MULT)
        if st_now is None or st_prev is None:
            return None

        # Trend flip: bearish -> bullish or bullish -> bearish
        flip_long = st_prev.direction == -1 and st_now.direction == 1
        flip_short = st_prev.direction == 1 and st_now.direction == -1
        if not flip_long and not flip_short:
            return None

        symbol_info = self.liveDataAndTrading.get_symbol_info(self.symbol)
        entry = round(st_now.value, symbol_info.digits)
        sl_dist = abs(candles[-1].close - entry) or entry * 0.002
        sl_dist = max(sl_dist, entry * 0.001)

        if flip_long:
            trade_type = TradeType.BUY_STOP
            sl = round(entry - sl_dist, symbol_info.digits)
            tp = round(entry + sl_dist * self.RR, symbol_info.digits)
        else:
            trade_type = TradeType.SELL_STOP
            sl = round(entry + sl_dist, symbol_info.digits)
            tp = round(entry - sl_dist * self.RR, symbol_info.digits)

        volume = self._lot_size(sl_dist, symbol_info)
        if not volume:
            return None

        return Trade(
            symbol=self.symbol,
            type=trade_type,
            action=TradeAction.PENDING,
            ticket=0,
            entry_price=entry,
            volume=volume,
            volume_initial=volume,
            stop_loss=sl,
            take_profit=tp,
            initial_stop_loss=sl,
            status=TradeStatus.OPEN,
            comment=f"EXAMPLE supertrend {'long' if flip_long else 'short'} stop",
        )
