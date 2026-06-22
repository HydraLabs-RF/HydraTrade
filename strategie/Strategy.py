from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List
from data.trade import Trade
from execution.simulation.simulationMemory import simMemory

class Strategy(ABC):

    def __init__(self):
        # Der Simulations-Kontext ist standardmäßig None (= Live-Modus)
        self.simMemory = None
        self.liveTradingTracker = None
        self.version = None

    def setSimMemory(self, memory: simMemory):
        self.simMemory = memory

    def setLiveTracker(self, tracker) -> None:
        self.liveTradingTracker = tracker

    # ------------------------------------------------------------
    # 1. ENTRY LOGIC (Signale erzeugen)
    # ------------------------------------------------------------
    def planTradeGrade_A(self, target_date_time: datetime | None) -> List[Trade] | None:
        return None

    def planTradeGrade_B(self) -> List[Trade] | None:
        return None

    def planTradeGrade_C(self) -> List[Trade] | None:
        return None
    
    def on_tick(self, current_time: datetime) -> List[Trade]:
        signal_trades: List[Trade] = []
        t = self.planTradeGrade_A(current_time)
        if t:
            signal_trades.append(t)
            if not self.quiet:
                print(f"[{self.version}] Signal: {t}")
        for planner in (self.planTradeGrade_B, self.planTradeGrade_C):
            t = planner()
            if t:
                signal_trades.append(t)
                if not self.quiet:
                    print(f"[{self.version}] Signal: {t}")
        return signal_trades
    
    # ------------------------------------------------------------
    # 2. PENDING MANAGEMENT (Grade-spezifische Hooks)
    # ------------------------------------------------------------
    def adjustPendingTradeGrade_A(self, target_date_time: datetime | None = None) -> List[Trade] | None:
        return None

    def adjustPendingTradeGrade_B(self) -> List[Trade] | None:
        return None

    def adjustPendingTradeGrade_C(self) -> List[Trade] | None:
        return None

    def adjust_pending(self, current_time: datetime) -> List[Trade]:
        """
        Prüft alle aktuell offenen Pending Orders.
        Gibt die Liste der Trades zurück, die AKTUALISIERT oder BEIBEHALTEN werden sollen.

        Tipp: Wenn ein Trade nicht mehr in der Rückgabeliste ist,
        interpretiert die Engine das als 'Stornieren'.
        """
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        adjustedPendingTrades: List[Trade] = []
        adjustedPendingTradesTemp = self.adjustPendingTradeGrade_A(current_time)
        if adjustedPendingTradesTemp:
            adjustedPendingTrades.extend(adjustedPendingTradesTemp)
        adjustedPendingTradesTemp = self.adjustPendingTradeGrade_B()
        if adjustedPendingTradesTemp:
            adjustedPendingTrades.extend(adjustedPendingTradesTemp)
        adjustedPendingTradesTemp = self.adjustPendingTradeGrade_C()
        if adjustedPendingTradesTemp:
            adjustedPendingTrades.extend(adjustedPendingTradesTemp)
        return adjustedPendingTrades

    # ------------------------------------------------------------
    # 3. ACTIVE TRADE MANAGEMENT (Grade-spezifische Hooks)
    # ------------------------------------------------------------
    def manageActiveTradeGrade_A(self, target_date_time: datetime | None) -> List[Trade] | None:
        return None

    def manageActiveTradeGrade_B(self) -> List[Trade] | None:
        return None

    def manageActiveTradeGrade_C(self) -> List[Trade] | None:
        return None

    def manage_trailing(self, current_time: datetime) -> List[Trade]:
        """
        Prüft alle aktiven Trades auf SL/TP-Anpassungen.
        Gibt eine Liste der modifizierten Trades mit neuen SL/TP-Werten zurück.
        Leere Liste = Keine Anpassungen notwendig.
        """
        managedActiveTrades: List[Trade] = []
        managedActiveTradesTemp = self.manageActiveTradeGrade_A(current_time)
        if managedActiveTradesTemp:
            managedActiveTrades.extend(managedActiveTradesTemp)
        managedActiveTradesTemp = self.manageActiveTradeGrade_B()
        if managedActiveTradesTemp:
            managedActiveTrades.extend(managedActiveTradesTemp)
        managedActiveTradesTemp = self.manageActiveTradeGrade_C()
        if managedActiveTradesTemp:
            managedActiveTrades.extend(managedActiveTradesTemp)
        return managedActiveTrades