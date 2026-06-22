import time
from datetime import datetime, timezone

from core.enums import TimeFrame
from core.config import configConnection
from data.trade import Trade, TradeAction, TradeStatus, TradeType
from execution.live.mt5execution import MT5CExecution
from execution.live.mt5TradeTracker import mt5TradeTracker
from core.branding import log, print_banner
from strategie.Strategy import Strategy


class LiveExecution:
    """Live-Trading-Loop – spiegelt die Simulation, sendet Orders an MT5."""

    def __init__(self, symbol: str | None = None, timeframe: TimeFrame = TimeFrame.M5):
        config = configConnection()
        self.symbol = symbol or config.getSymbol()
        self.timeframe = timeframe
        self.poll_interval_sec = 300

        self.execution = MT5CExecution()
        self.tracker = mt5TradeTracker()
        self.strategy: Strategy | None = None
        self._last_processed_bar: datetime | None = None
        self._running = False

    def set_strategy(self, strategy: Strategy) -> None:
        self.strategy = strategy
        if hasattr(strategy, "setLiveTracker"):
            strategy.setLiveTracker(self.tracker)
        else:
            strategy.liveTradingTracker = self.tracker

    def run(self) -> None:
        if not self.strategy:
            raise ValueError("No strategy assigned.")

        config = configConnection()
        if not config.isLive():
            log("config.live is False — enabling live mode.")
            config.live = True

        self._running = True
        print_banner()
        log(f"Live engine started — {self.symbol} ({self.timeframe.name})")

        while self._running:
            try:
                bar_time = self._get_current_bar_time()
                if bar_time is None:
                    time.sleep(self.poll_interval_sec)
                    continue

                # Die Brokerzeit der neuesten Kerze ist unsere "aktuelle Zeit".
                self.tracker.sync(bar_time)

                if bar_time == self._last_processed_bar:
                    time.sleep(self.poll_interval_sec)
                    continue

                self._last_processed_bar = bar_time
                self._on_new_bar(bar_time)

            except KeyboardInterrupt:
                log("Live engine stopped by user.")
                break
            except Exception as e:
                log(f"Loop error: {e}")

            time.sleep(self.poll_interval_sec)

    def stop(self) -> None:
        self._running = False

    def _get_current_bar_time(self) -> datetime | None:
        candle = self.execution.getLatestCandle(self.timeframe, self.symbol)
        if candle is None:
            return None
        bar_time = candle.time
        if bar_time.tzinfo is None:
            bar_time = bar_time.replace(tzinfo=timezone.utc)
        return bar_time

    def _on_new_bar(self, current_time: datetime) -> None:
        self._manage_active_trades(current_time)
        self._manage_pending_trades(current_time)

        new_signals = self.strategy.on_tick(current_time)
        if new_signals:
            for trade in new_signals:
                self._process_new_strategy_signal(trade, current_time)

    def _process_new_strategy_signal(self, trade: Trade, current_time: datetime) -> None:
        trade.initial_time = current_time
        result = self.execution.execute_trade_request(trade)
        if result is None:
            log(f"Signal not executed: {trade.comment}")
            return

        if result.action == TradeAction.PENDING or result.status == TradeStatus.OPEN:
            self.tracker.register_pending(result)
            log(f"Pending placed — ticket={result.ticket} {result.comment}")
        elif result.status == TradeStatus.RUNNING:
            self.tracker.register_active(result)
            log(f"Position open — ticket={result.ticket}")

    def _manage_pending_trades(self, current_time: datetime) -> None:
        pending_requests = self.strategy.adjust_pending(current_time)
        if not pending_requests:
            return

        for request in pending_requests:
            if isinstance(request, list):
                items = request
            else:
                items = [request]

            for item in items:
                if not item or not item.ticket:
                    continue

                if item.action == TradeAction.PENDING_MODIFY:
                    if self.execution.modify_pending_order(item.ticket, item):
                        self.tracker.memory.update_from_mt5_pending(
                            item.ticket, item.entry_price, item.stop_loss, item.take_profit
                        )

                elif item.action == TradeAction.PENDING_REMOVE:
                    if self.execution.remove_pending_order(item.ticket, item.symbol):
                        self.tracker.unregister_pending(item.ticket)

    def _manage_active_trades(self, current_time: datetime) -> None:
        active_requests = self.strategy.manage_trailing(current_time)
        if not active_requests:
            return

        for request in active_requests:
            if not request.ticket:
                continue

            if request.action == TradeAction.ACTION_MODIFY_SL_TP:
                if self.execution.modify_position_sl_tp(
                    request.ticket, request.symbol, request.stop_loss, request.take_profit
                ):
                    self.tracker.memory.update_sl_tp(
                        request.ticket, request.stop_loss, request.take_profit
                    )

            elif request.status == TradeStatus.CLOSED:
                original = self.tracker.memory.find_trade_by_ticket(request.ticket)
                volume = original.volume if original else request.volume
                trade_type = original.type if original else request.type
                if self.execution.close_position(request.ticket, request.symbol, volume, trade_type):
                    self.tracker.sync(current_time)
