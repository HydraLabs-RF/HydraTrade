"""
Shared base for HydraTrade example strategies.

These classes demonstrate how to plug into the Strategy lifecycle
(entry signals, pending management, active trade management).
They are intentionally simple and are NOT intended for production use.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from core.config import configConnection
from core.enums import TimeFrame
from core.riskManagment import RiskManager, SymbolInfo
from execution.live.mt5execution import MT5CExecution
from strategie.Strategy import Strategy


class ExampleStrategyBase(Strategy):
    """Common wiring: config, data access, risk sizing, quiet mode."""

    VARIANT_ID = "example_base"
    VARIANT_NAME = "Example Base"
    VARIANT_GROUP = "Examples"
    RISK_PCT = 0.002  # 0.2% — small size for demo backtests
    SIGNAL_TIMEFRAME = TimeFrame.H1

    def __init__(self, quiet: bool = True):
        super().__init__()
        self.quiet = quiet
        self.config = configConnection()
        self.symbol = self.config.getSymbol()
        self.liveDataAndTrading = MT5CExecution()
        self.riskManager = RiskManager()
        self.riskManager.risk_map["A"] = self.RISK_PCT
        self.version = self.VARIANT_NAME
        self._last_signal_bar: datetime | None = None
        self._last_trade_time: datetime | None = None

    def _cooldown_ok(self, current_time: datetime, minutes: int = 720) -> bool:
        if self._last_trade_time is None:
            return True
        delta = (current_time - self._last_trade_time).total_seconds()
        return delta >= minutes * 60

    def _mark_trade_placed(self, current_time: datetime) -> None:
        self._last_trade_time = current_time

    def _now(self, target_date_time: datetime | None) -> datetime:
        if target_date_time is None:
            return datetime.now(timezone.utc)
        if target_date_time.tzinfo is None:
            return target_date_time.replace(tzinfo=timezone.utc)
        return target_date_time

    def _signal_bar_time(self, current_time: datetime) -> datetime:
        """Collapse simulation ticks to the active signal timeframe bar."""
        tf = self.SIGNAL_TIMEFRAME
        if tf == TimeFrame.H1:
            return current_time.replace(minute=0, second=0, microsecond=0)
        if tf == TimeFrame.M15:
            minute = (current_time.minute // 15) * 15
            return current_time.replace(minute=minute, second=0, microsecond=0)
        if tf == TimeFrame.M5:
            minute = (current_time.minute // 5) * 5
            return current_time.replace(minute=minute, second=0, microsecond=0)
        return current_time.replace(hour=0, minute=0, second=0, microsecond=0)

    def _get_candles(self, timeframe: TimeFrame, current_time: datetime, count: int = 200):
        candles = self.liveDataAndTrading.getHistoricalCandles(
            timeframe, current_time, count, self.symbol
        )
        return candles or []

    def _account(self) -> tuple[float, str]:
        if self.simMemory is not None:
            return self.simMemory.getBalance(), self.simMemory.getBalanceCurency()
        return (
            self.liveDataAndTrading.get_account_equity(),
            self.liveDataAndTrading.get_account_currency(),
        )

    def _lot_size(self, sl_points: float, symbol_info: SymbolInfo) -> Optional[float]:
        if sl_points <= 0:
            return None
        equity, currency = self._account()
        try:
            return self.riskManager.get_lot_size(
                equity=equity,
                risk_grade="A",
                sl_points=sl_points,
                symbol_info=symbol_info,
                account_currency=currency,
                fx_rate_provider=self.liveDataAndTrading,
            )
        except Exception as e:
            if not self.quiet:
                print(f"[{self.version}] lot size error: {e}")
            return None

    def _has_open_or_pending(self) -> bool:
        if self.simMemory is not None:
            return bool(self.simMemory.get_active_trades() or self.simMemory.get_pending_orders())
        if self.liveTradingTracker is not None:
            return bool(
                self.liveTradingTracker.memory.get_active_trades()
                or self.liveTradingTracker.memory.get_pending_orders()
            )
        return False

    def _once_per_bar(self, current_time: datetime) -> bool:
        """Avoid duplicate signals on the same signal-timeframe bar."""
        bar_time = self._signal_bar_time(current_time)
        if self._last_signal_bar == bar_time:
            return False
        self._last_signal_bar = bar_time
        return True

    def on_tick(self, current_time: datetime) -> List:
        signals = super().on_tick(current_time)
        return [s for s in signals if s is not None]
