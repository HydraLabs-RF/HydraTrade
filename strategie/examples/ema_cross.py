"""
EXAMPLE STRATEGY — EMA Crossover

Demonstrates:
  - Market entry (TradeAction.ACTION) on a fast/slow EMA cross
  - Stop-loss and take-profit on new positions
  - Manual close via manage_trailing when the cross reverses

NOT for production or live trading. Use as a template for your own strategies.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from core.enums import TimeFrame
from data.trade import Trade, TradeAction, TradeStatus, TradeType
from strategie.examples.base import ExampleStrategyBase
from strategie.tools.indicators import close_ema


class ExampleEmaCross(ExampleStrategyBase):
    VARIANT_ID = "example_ema_cross"
    VARIANT_NAME = "Example: EMA Cross"
    VARIANT_GROUP = "Examples"

    FAST = 9
    SLOW = 21
    RR = 2.0

    def planTradeGrade_A(self, target_date_time: datetime | None) -> Optional[Trade]:
        t = self._now(target_date_time)
        if self._has_open_or_pending():
            return None
        if not self._once_per_bar(t):
            return None

        candles = self._get_candles(TimeFrame.M15, t, 120)
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

        symbol_info = self.liveDataAndTrading.get_symbol_info(self.symbol)
        entry = round(closes[-1], symbol_info.digits)
        atr_proxy = abs(fast_now - slow_now) or entry * 0.002
        sl_dist = max(atr_proxy * 2, entry * 0.001)

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

    def manageActiveTradeGrade_A(self, target_date_time: datetime | None) -> List[Trade] | None:
        """Close open positions when the EMA cross reverses (demonstrates manual close)."""
        t = self._now(target_date_time)
        candles = self._get_candles(TimeFrame.M15, t, 120)
        if len(candles) < self.SLOW + 2:
            return None

        fast_now = close_ema(candles, self.FAST)
        slow_now = close_ema(candles, self.SLOW)
        if fast_now is None or slow_now is None:
            return None

        trades = (
            self.simMemory.get_active_trades()
            if self.simMemory
            else (self.liveTradingTracker.memory.get_active_trades() if self.liveTradingTracker else [])
        )
        if not trades:
            return None

        out: List[Trade] = []
        for tr in trades:
            if not str(tr.comment or "").startswith("EXAMPLE ema_cross"):
                continue
            is_long = tr.type in (TradeType.BUY, TradeType.BUY_LIMIT, TradeType.BUY_STOP, TradeType.BUY_STOP_LIMIT)
            reverse = (is_long and fast_now < slow_now) or (not is_long and fast_now > slow_now)
            if reverse:
                close = Trade(
                    symbol=tr.symbol,
                    type=tr.type,
                    action=TradeAction.ACTION,
                    ticket=tr.ticket,
                    entry_price=candles[-1].close,
                    volume=tr.volume,
                    status=TradeStatus.CLOSED,
                    comment="EXAMPLE ema_cross reverse exit",
                )
                out.append(close)
        return out or None
