from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from data.candle import Candle
from core.enums import TimeFrame
from core.config import configConnection
from execution.live.mt5execution import MT5CExecution

@dataclass
class ATRResult:
    value: float
    values: List[float]  # Verlauf der ATR-Werte


class ATRIndicator:
    def __init__(self, period: int = 14, timeframe: TimeFrame = TimeFrame.H1):
        self.period = period
        self.timeframe = timeframe
        self.config = configConnection()
        # Execution Layer für autarken Datenbezug instanziieren
        self.execution = MT5CExecution()

    def calculate_by_time(self, reference_time: Optional[datetime] = None) -> ATRResult:
        """
        Holt sich die benötigten historischen Kerzen selbstständig anhand einer 
        datetime und berechnet den ATR-Wert.
        """
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)
        elif reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        # Wir benötigen für die Wilder's Smoothing Berechnung genaustens:
        # 1 (für True Range des ersten Vergleichs) + period (für Initial-ATR) + zusätzliche historische Kerzen,
        # um den geglätteten Wert für das aktuelle Target präzise aufzubauen.
        # Ein Puffer von period * 2 sorgt für mathematisch saubere Glättung.
        needed_candles = self.period * 3

        candles = self.execution.getHistoricalCandles(
            timeframe=self.timeframe,
            reference_time=reference_time,
            candle_count=needed_candles,
            Symbol=self.config.getSymbol()
        )

        return self.calculate(candles)

    def calculate(self, candles: List[Candle]) -> ATRResult:
        """
        Mathematische Kernberechnung der ATR basierend auf einer übergebenen Kerzenliste.
        Falls weniger Kerzen als die Standard-Periode übergeben werden, passt sich 
        die Berechnung dynamisch an die verfügbaren Daten an.
        """
        # Absoluter Fallback: Wenn wir weniger als 2 Kerzen haben, können wir keine True Range berechnen
        if len(candles) < 2:
            return ATRResult(value=0.0, values=[0.0])

        # 1. Berechne alle verfügbaren True Ranges
        true_ranges = []
        for i in range(1, len(candles)):
            current = candles[i]
            previous = candles[i - 1]

            tr = max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
            true_ranges.append(tr)

        # 2. Dynamische Perioden-Anpassung
        # Wir können maximal so viele Perioden berechnen, wie wir True Ranges haben.
        # Wenn self.period = 14 ist, wir aber nur 7 True Ranges haben, nutzen wir effektiv eine 7er-Periode.
        effective_period = min(self.period, len(true_ranges))

        atr_values = []

        # Initial ATR (einfacher Durchschnitt der ersten 'effective_period' True Ranges)
        first_atr = sum(true_ranges[:effective_period]) / effective_period
        atr_values.append(first_atr)

        # 3. Wilder's Smoothing Logik (wird nur ausgeführt, wenn noch restliche True Ranges übrig sind)
        for i in range(effective_period, len(true_ranges)):
            prev_atr = atr_values[-1]
            current_tr = true_ranges[i]

            # Hier nutzen wir die angepasste effektive Periode für die Glättung
            atr = (prev_atr * (effective_period - 1) + current_tr) / effective_period
            atr_values.append(atr)

        return ATRResult(
            value=atr_values[-1],
            values=atr_values
        )