"""
EXAMPLE STRATEGY — Volume Profile

Demonstrates:
  - Limit entry orders (BUY_LIMIT / SELL_LIMIT) at the Point of Control (POC)
  - Volume profile built from recent session candles

NOT for production or live trading. Use as a template for your own strategies.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from core.config import configConnection
from core.enums import TimeFrame
from data.trade import Trade, TradeAction, TradeStatus, TradeType
from strategie.examples.base import ExampleStrategyBase
from strategie.tools.volumeProfile import VolumeProfile


class ExampleVolumeProfile(ExampleStrategyBase):
    VARIANT_ID = "example_volume_profile"
    VARIANT_NAME = "Example: Volume Profile"
    VARIANT_GROUP = "Examples"

    LOOKBACK_HOURS = 24
    RR = 2.0

    def planTradeGrade_A(self, target_date_time: datetime | None) -> Optional[Trade]:
        t = self._now(target_date_time)
        if self._has_open_or_pending():
            return None
        if not self._cooldown_ok(t, minutes=360):
            return None
        if not self._once_per_bar(t):
            return None

        start = t - timedelta(hours=self.LOOKBACK_HOURS)
        candles = self.liveDataAndTrading.getCandlesBetween(
            TimeFrame.M15, start, t, self.symbol
        )
        if len(candles) < 20:
            return None

        cfg = configConnection()
        vp = VolumeProfile(cfg.getVolumeProfileBinSize())
        vp.build(candles)
        poc = vp.get_poc()
        if poc is None:
            return None

        symbol_info = self.liveDataAndTrading.get_symbol_info(self.symbol)
        price = round(candles[-1].close, symbol_info.digits)
        poc_price = round(poc.price, symbol_info.digits)

        # Fade toward POC: buy below POC, sell above POC
        dist = abs(price - poc_price)
        if dist < price * 0.003:
            return None  # too close to POC — skip

        sl_dist = max(dist * 0.5, price * 0.001)
        if price < poc_price:
            trade_type = TradeType.BUY_LIMIT
            entry = poc_price
            sl = round(entry - sl_dist, symbol_info.digits)
            tp = round(entry + sl_dist * self.RR, symbol_info.digits)
        else:
            trade_type = TradeType.SELL_LIMIT
            entry = poc_price
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
            comment="EXAMPLE vol_profile poc limit",
        )
