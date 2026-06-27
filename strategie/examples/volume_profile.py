"""
EXAMPLE STRATEGY — Volume Profile

Demonstrates:
  - Limit entry orders (BUY_LIMIT / SELL_LIMIT) at the session POC
  - Pending orders waiting for a pullback to the point of control
  - Volume profile built from recent session candles

NOT for production or live trading. Use as a template for your own strategies.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from core.config import configConnection
from data.trade import Trade, TradeAction, TradeStatus, TradeType
from strategie.examples.base import ExampleStrategyBase
from strategie.tools.indicators import close_ema
from strategie.tools.volumeProfile import VolumeProfile


class ExampleVolumeProfile(ExampleStrategyBase):
    VARIANT_ID = "example_volume_profile"
    VARIANT_NAME = "Example: Volume Profile"
    VARIANT_GROUP = "Examples"

    LOOKBACK_HOURS = 24
    HISTORY_HOURS = 120
    TREND_EMA = 50
    RR = 0.85
    PENDING_TTL_HOURS = 24

    def adjustPendingTradeGrade_A(self, target_date_time: datetime | None) -> List[Trade] | None:
        """Drop stale POC limits so a non-filling order does not block the demo."""
        t = self._now(target_date_time)
        memory = self.simMemory
        if memory is None:
            return None
        out: List[Trade] = []
        for order in memory.get_pending_orders():
            if not str(order.comment or "").startswith("EXAMPLE vol_profile"):
                continue
            opened = order.initial_time or t
            if (t - opened).total_seconds() >= self.PENDING_TTL_HOURS * 3600:
                out.append(Trade(
                    symbol=order.symbol,
                    type=order.type,
                    action=TradeAction.PENDING_REMOVE,
                    ticket=order.ticket,
                    entry_price=order.entry_price,
                    volume=order.volume,
                    status=TradeStatus.OPEN,
                    comment=order.comment,
                ))
        return out or None

    def planTradeGrade_A(self, target_date_time: datetime | None) -> Optional[Trade]:
        t = self._now(target_date_time)
        if self._has_open_or_pending():
            return None
        if not self._cooldown_ok(t, minutes=1440):
            return None
        if not self._once_per_bar(t):
            return None

        history_start = t - timedelta(hours=self.HISTORY_HOURS)
        profile_start = t - timedelta(hours=self.LOOKBACK_HOURS)
        history = self.liveDataAndTrading.getCandlesBetween(
            self.SIGNAL_TIMEFRAME, history_start, t, self.symbol
        )
        if len(history) < self.TREND_EMA + 5:
            return None
        profile_candles = [c for c in history if c.time >= profile_start]
        if len(profile_candles) < 20:
            return None

        cfg = configConnection()
        vp = VolumeProfile(cfg.getVolumeProfileBinSize())
        vp.build(profile_candles)
        poc = vp.get_poc()
        if poc is None:
            return None

        trend_ema = close_ema(history, self.TREND_EMA)
        if trend_ema is None:
            return None

        symbol_info = self.liveDataAndTrading.get_symbol_info(self.symbol)
        price = round(history[-1].close, symbol_info.digits)
        poc_price = round(poc.price, symbol_info.digits)
        if abs(price - poc_price) < price * 0.001:
            return None  # already at POC — nothing to demonstrate

        sl_dist = max(abs(price - poc_price) * 0.4, price * 0.0025)

        if price > poc_price and price > trend_ema:
            trade_type = TradeType.BUY_LIMIT
            # Pullback toward POC, but not farther than 0.6% below spot (more fills in demo).
            entry = round(max(poc_price, price * 0.994), symbol_info.digits)
            sl = round(entry - sl_dist, symbol_info.digits)
            tp = round(entry + sl_dist * self.RR, symbol_info.digits)
        elif price < poc_price and price < trend_ema:
            trade_type = TradeType.SELL_LIMIT
            entry = round(min(poc_price, price * 1.006), symbol_info.digits)
            sl = round(entry + sl_dist, symbol_info.digits)
            tp = round(entry - sl_dist * self.RR, symbol_info.digits)
        else:
            return None

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
            comment="EXAMPLE vol_profile poc limit",
        )
