"""
EXAMPLE STRATEGY — SuperTrend (TradingView-style)

Demonstrates:
  - Stop entry orders (TradeType.BUY_STOP / SELL_STOP) on H1 trend flips
  - Pending order placement at the SuperTrend line
  - Cooldown to keep trade count realistic for a demo

NOT for production or live trading. Use as a template for your own strategies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from data.trade import Trade, TradeAction, TradeStatus, TradeType
from strategie.examples.base import ExampleStrategyBase
from strategie.tools.supertrend import supertrend


class ExampleSuperTrend(ExampleStrategyBase):
    VARIANT_ID = "example_supertrend"
    VARIANT_NAME = "Example: SuperTrend"
    VARIANT_GROUP = "Examples"

    PERIOD = 14
    MULT = 3.5
    RR = 1.0

    def planTradeGrade_A(self, target_date_time: datetime | None) -> Optional[Trade]:
        t = self._now(target_date_time)
        if self._has_open_or_pending():
            return None
        if not self._cooldown_ok(t, minutes=960):
            return None
        if not self._once_per_bar(t):
            return None

        candles = self._get_candles(self.SIGNAL_TIMEFRAME, t, 120)
        st_now = supertrend(candles, self.PERIOD, self.MULT)
        st_prev = supertrend(candles[:-1], self.PERIOD, self.MULT)
        if st_now is None or st_prev is None:
            return None

        flip_long = st_prev.direction == -1 and st_now.direction == 1
        flip_short = st_prev.direction == 1 and st_now.direction == -1
        if not flip_long and not flip_short:
            return None

        symbol_info = self.liveDataAndTrading.get_symbol_info(self.symbol)
        entry = round(st_now.value, symbol_info.digits)
        sl_dist = max(abs(candles[-1].close - entry), entry * 0.0025)

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

        self._mark_trade_placed(t)
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
