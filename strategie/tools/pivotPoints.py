from typing import List, Optional
from dataclasses import dataclass
from core.enums import StructureState, Signal, MarketStructure, MarketBias

from data.candle import Candle


@dataclass
class StructureLevels:
    last_high: Optional[float]
    prev_high: Optional[float]
    last_low: Optional[float]
    prev_low: Optional[float]

    last_high_index: Optional[int]
    last_low_index: Optional[int]

    state: Optional[str]
    structure: Optional[str]
    bias: Optional[str]
    signal: Optional[str]

    # --- Vorlaeufiger (unbestaetigter) Extremwert ---------------------------
    # Im rechten Pivot-Fenster (die letzten `right` Kerzen) kann noch keine
    # Bestaetigung erfolgen. Bildet sich dort bereits ein neues Higher-High
    # oder Lower-Low (ueber/unter dem letzten BESTAETIGTEN Pivot), wird es
    # NICHT als Pivot gespeichert, aber hier als "aktueller Extremwert" nach
    # aussen gereicht. Reine Ausgabe-Info: die Struktur-Logik selbst weiss
    # nichts davon, bis das Pivot bestaetigt ist.
    provisional_high: Optional[float] = None
    provisional_high_index: Optional[int] = None
    provisional_low: Optional[float] = None
    provisional_low_index: Optional[int] = None
    is_provisional: bool = False


class MarketStructureEngine:

    def __init__(self, left: int = 3, right: int = 3):
        self.left = left
        self.right = right

        # confirmed pivots (like Pine arrays)
        self.highs: List[float] = []
        self.high_idx: List[int] = []

        self.lows: List[float] = []
        self.low_idx: List[int] = []

        self.current_state = StructureState.SEEK_HIGH

        self.last_signal = Signal.NONE
        self.market_structure = MarketStructure.RANGE
        self.market_bias = MarketBias.NEUTRAL

        # Vorlaeufiger (unbestaetigter) Extremwert aus dem rechten Fenster.
        # Wird in build() neu berechnet und NUR in get_levels() ausgegeben.
        self.provisional_high: Optional[float] = None
        self.provisional_high_idx: Optional[int] = None
        self.provisional_low: Optional[float] = None
        self.provisional_low_idx: Optional[int] = None

    # -------------------------------------------------
    # 1. Pivot Detection (same logic as ta.pivothigh/low)
    # -------------------------------------------------
    def detect_pivots(self, candles: List[Candle]):

        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        pivot_highs = [None] * len(candles)
        pivot_lows = [None] * len(candles)

        for i in range(self.left, len(candles) - self.right):

            # --- pivot high ---
            window_high = highs[i - self.left:i + self.right + 1]

            if highs[i] == max(window_high) and window_high.count(highs[i]) == 1:
                pivot_highs[i] = highs[i]

            # --- pivot low ---
            window_low = lows[i - self.left:i + self.right + 1]

            if lows[i] == min(window_low) and window_low.count(lows[i]) == 1:
                pivot_lows[i] = lows[i]

        return pivot_highs, pivot_lows

    # -------------------------------------------------
    # 2. Build structure (Pine array logic)
    # -------------------------------------------------
    def build(self, candles: List[Candle]):
        self.highs.clear()
        self.high_idx.clear()
        self.lows.clear()
        self.low_idx.clear()
        self.current_state = StructureState.SEEK_HIGH
        self.last_signal = Signal.NONE
        self.market_structure = MarketStructure.RANGE
        self.market_bias = MarketBias.NEUTRAL
        self.provisional_high = None
        self.provisional_high_idx = None
        self.provisional_low = None
        self.provisional_low_idx = None

        pivot_highs, pivot_lows = self.detect_pivots(candles)

        for i in range(len(candles)):

            # ---------------- HIGH ----------------
            if pivot_highs[i] is not None:

                ph = pivot_highs[i]

                if self.highs:
                    last_h = self.highs[-1]

                    # replace logic (wie dein Pine Fix)
                    if ph > last_h:
                        self.highs.pop()
                        self.high_idx.pop()

                self.highs.append(ph)
                self.high_idx.append(i)

            # ---------------- LOW ----------------
            if pivot_lows[i] is not None:

                pl = pivot_lows[i]

                if self.lows:
                    last_l = self.lows[-1]

                    # replace logic
                    if pl < last_l:
                        self.lows.pop()
                        self.low_idx.pop()

                self.lows.append(pl)
                self.low_idx.append(i)

        self.update_structure_state()
        self.detect_market_structure()
        self.detect_market_bias()
        self.generate_signal()

        # Zum Schluss: das unbestaetigte rechte Fenster auf einen neuen
        # Extremwert pruefen. Aendert KEINEN bestaetigten Zustand.
        self.detect_provisional_extreme(candles)

    # -------------------------------------------------
    # 2b. Vorlaeufiger Extremwert (unbestaetigt)
    # -------------------------------------------------
    def detect_provisional_extreme(self, candles: List[Candle]):
        """Prueft das rechte (noch nicht bestaetigbare) Fenster auf ein neues
        Higher-High / Lower-Low jenseits des letzten bestaetigten Pivots.

        Speichert das Ergebnis NUR als vorlaeufige Ausgabe-Info; die Pivot-
        Listen und der Struktur-/Trend-/Signal-Zustand bleiben unberuehrt.
        Solange noch nicht genug Kerzen fuer ein linkes Fenster da sind,
        gibt es nichts Sinnvolles zu melden."""
        n = len(candles)
        if n == 0:
            return

        # Die letzten `right` Kerzen koennen per Definition noch nicht als
        # Pivot bestaetigt werden (es fehlen die Kerzen rechts davon).
        tail_start = n - self.right
        if tail_start < 0:
            tail_start = 0
        if tail_start >= n:
            return

        max_high = None
        max_high_idx = None
        min_low = None
        min_low_idx = None
        for i in range(tail_start, n):
            h = candles[i].high
            l = candles[i].low
            if max_high is None or h > max_high:
                max_high = h
                max_high_idx = i
            if min_low is None or l < min_low:
                min_low = l
                min_low_idx = i

        last_high = self.highs[-1] if self.highs else None
        last_low = self.lows[-1] if self.lows else None

        # Higher-High: neuer Hoechstwert ueber dem letzten bestaetigten High.
        # Ohne bestaetigtes High gibt es noch keine Referenzstruktur -> nichts
        # melden (sonst wuerde jede Anfangskerze als "Extrem" gelten).
        if last_high is not None and max_high is not None and max_high > last_high:
            self.provisional_high = max_high
            self.provisional_high_idx = max_high_idx

        # Lower-Low: neuer Tiefstwert unter dem letzten bestaetigten Low.
        if last_low is not None and min_low is not None and min_low < last_low:
            self.provisional_low = min_low
            self.provisional_low_idx = min_low_idx

    # -------------------------------------------------
    # 3. Levels (dein Ziel)
    # -------------------------------------------------
    def get_levels(self) -> StructureLevels:

        return StructureLevels(
            last_high=self.highs[-1] if self.highs else None,
            prev_high=self.highs[-2] if len(self.highs) > 1 else None,

            last_low=self.lows[-1] if self.lows else None,
            prev_low=self.lows[-2] if len(self.lows) > 1 else None,

            last_high_index=self.high_idx[-1] if self.high_idx else None,
            last_low_index=self.low_idx[-1] if self.low_idx else None,

            state=self.current_state.value,
            structure=self.market_structure.value,
            bias=self.market_bias.value,
            signal=self.last_signal.value,

            provisional_high=self.provisional_high,
            provisional_high_index=self.provisional_high_idx,
            provisional_low=self.provisional_low,
            provisional_low_index=self.provisional_low_idx,
            is_provisional=(self.provisional_high is not None
                            or self.provisional_low is not None),
        )

    # -------------------------------------------------
    # 4. Market Structure helpers
    # -------------------------------------------------
    def is_higher_low(self) -> bool:
        if len(self.lows) < 2:
            return False
        return self.lows[-1] > self.lows[-2]

    def is_lower_high(self) -> bool:
        if len(self.highs) < 2:
            return False
        return self.highs[-1] < self.highs[-2]

    def trend(self) -> str:
        hl = self.is_higher_low()
        lh = self.is_lower_high()

        if hl and not lh:
            return "UP"
        elif lh and not hl:
            return "DOWN"
        return "SIDEWAYS"

    def update_structure_state(self):

        if not self.high_idx or not self.low_idx:
            return

        last_high_idx = self.high_idx[-1]
        last_low_idx = self.low_idx[-1]

        # letztes bestätigtes Pivot war High
        # -> jetzt suchen wir Low
        if last_high_idx > last_low_idx:
            self.current_state = StructureState.SEEK_LOW
        else:
            self.current_state = StructureState.SEEK_HIGH

    def is_higher_high(self) -> bool:
        if len(self.highs) < 2:
            return False
        return self.highs[-1] > self.highs[-2]


    def is_lower_low(self) -> bool:
        if len(self.lows) < 2:
            return False
        return self.lows[-1] < self.lows[-2]

    def detect_market_structure(self):

        hh = self.is_higher_high()
        hl = self.is_higher_low()

        lh = self.is_lower_high()
        ll = self.is_lower_low()

        # sauberer Trend
        if (hh and hl) or (lh and ll):
            self.market_structure = MarketStructure.TREND
            return

        # beide Richtungen brechen
        if hh and ll:
            self.market_structure = MarketStructure.CHOPPY
            return

        # komprimierende Struktur
        if lh and hl:
            self.market_structure = MarketStructure.RANGE
            return

        self.market_structure = MarketStructure.RANGE

    def generate_signal(self):

        self.last_signal = Signal.NONE

        # Niemals in schlechten Marktphasen traden
        if self.market_structure != MarketStructure.TREND:
            return

        hh = self.is_higher_high()
        hl = self.is_higher_low()

        lh = self.is_lower_high()
        ll = self.is_lower_low()

        # BUY
        if hh and hl:
            self.last_signal = Signal.BUY
            return

        # SELL
        if lh and ll:
            self.last_signal = Signal.SELL
            return

    def detect_market_bias(self):

        hh = self.is_higher_high()
        hl = self.is_higher_low()

        lh = self.is_lower_high()
        ll = self.is_lower_low()

        # bullish pressure
        if hh or hl:
            if not (lh and ll):
                self.market_bias = MarketBias.BULLISH
                return

        # bearish pressure
        if lh or ll:
            if not (hh and hl):
                self.market_bias = MarketBias.BEARISH
                return

        self.market_bias = MarketBias.NEUTRAL
