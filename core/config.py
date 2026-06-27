import json
from datetime import datetime, timezone
from pathlib import Path

from core.enums import TimeFrame

# Optionale Overrides aus der Web-Oberflaeche (webui_config.json im Projektroot).
# Fehlt die Datei oder ist sie defekt, gelten exakt die bisherigen Defaults.
_OVERRIDE_FILE = Path(__file__).resolve().parent.parent / "webui_config.json"


def _load_overrides() -> dict:
    try:
        if _OVERRIDE_FILE.exists():
            with open(_OVERRIDE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _parse_date(value, fallback: datetime) -> datetime:
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return fallback


class configConnection:

    def __init__(self):
        self.live = False
        self.symbol = "XAUUSD"
        self.timeframe = TimeFrame.H1

        self.simulation_start_date = datetime(2026, 4, 30, tzinfo=timezone.utc)
        self.simulation_end_date = datetime(2026, 6, 5, tzinfo=timezone.utc)
        self.simEQ = 100000
        self.simAccCurency = "EUR"
        # Rollover/Swap in der Simulation modellieren (Werte live aus MT5).
        # Default an (= Realität); pro Run abschaltbar (z.B. um den reinen
        # Strategie-Edge ohne Haltekosten zu messen).
        self.simSwapEnabled = True

        self.volumeProfileBinSIze = 31
        self.magic_number = 260608
        self.order_deviation = 20

        self._apply_overrides(_load_overrides())

    def _apply_overrides(self, ov: dict) -> None:
        if not ov:
            return
        if isinstance(ov.get("symbol"), str) and ov["symbol"].strip():
            self.symbol = ov["symbol"].strip()
        if isinstance(ov.get("timeframe"), str) and ov["timeframe"] in TimeFrame.__members__:
            self.timeframe = TimeFrame[ov["timeframe"]]
        if ov.get("simulation_start_date"):
            self.simulation_start_date = _parse_date(ov["simulation_start_date"], self.simulation_start_date)
        if ov.get("simulation_end_date"):
            self.simulation_end_date = _parse_date(ov["simulation_end_date"], self.simulation_end_date)
        if isinstance(ov.get("simEQ"), (int, float)) and ov["simEQ"] > 0:
            self.simEQ = ov["simEQ"]
        if isinstance(ov.get("simAccCurency"), str) and ov["simAccCurency"].strip():
            self.simAccCurency = ov["simAccCurency"].strip()
        if isinstance(ov.get("magic_number"), int) and ov["magic_number"] > 0:
            self.magic_number = ov["magic_number"]
        if isinstance(ov.get("order_deviation"), int) and ov["order_deviation"] > 0:
            self.order_deviation = ov["order_deviation"]
        if isinstance(ov.get("simSwapEnabled"), bool):
            self.simSwapEnabled = ov["simSwapEnabled"]

    def isLive(self):
        return self.live

    def setLive(self, live: bool):
        self.live = live

    def getSymbol(self):
        return self.symbol

    def getTimeframe(self):
        return self.timeframe

    def getSimulationStart(self):
        return self.simulation_start_date

    def getSimulationEnd(self):
        return self.simulation_end_date
    
    def getVolumeProfileBinSize(self):
        return self.volumeProfileBinSIze
    
    def getSimEQ(self):
        return self.simEQ
    
    def getSimAccCurency(self):
        return self.simAccCurency

    def getMagicNumber(self) -> int:
        return self.magic_number

    def getSwapEnabled(self) -> bool:
        return self.simSwapEnabled

    def getOrderDeviation(self) -> int:
        return self.order_deviation