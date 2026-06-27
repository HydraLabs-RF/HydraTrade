import MetaTrader5 as mt5

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from core.enums import TimeFrame
from core.config import configConnection
from data.candle import Candle
from core.riskManagment import SymbolInfo  # Import der benötigten Dataclass

config = configConnection()


class MT5Connector:

    def __init__(self):

        self.connected = False
        self.testing_mode = True

        self.test_start = None
        self.test_end = None

        # Cache fuer die Broker-DST-Erkennung ("?" = noch nicht erkannt,
        # None = fixer Broker ohne DST, sonst IANA-Zonenname).
        self._broker_tz_cache = "?"

    # ---------------------------------
    # CONNECTION
    # ---------------------------------

    def initialize(self):

        if not mt5.initialize():
            raise Exception(
                f"MT5 initialization failed: {mt5.last_error()}"
            )

        self.connected = True

        print("MT5 initialized")

    def shutdown(self):

        mt5.shutdown()

        self.connected = False

    # ---------------------------------
    # TESTING WINDOW
    # ---------------------------------

    def set_testing_window(
        self,
        start: datetime,
        end: datetime
    ):

        self.test_start = start
        self.test_end = end

    # ---------------------------------
    # MARKET DATA
    # ---------------------------------

    def get_candles(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start: datetime = None,
        end: datetime = None
    ) -> list[Candle]:

        if start is None:
            start = self.test_start

        if end is None:
            end = self.test_end

        rates = mt5.copy_rates_range(
            symbol,
            timeframe.value,
            start,
            end
        )

        if rates is None:
            raise Exception(
                f"Failed loading candles: {mt5.last_error()}"
            )

        return [self._row_to_candle(row) for row in rates]

    @staticmethod
    def _row_to_candle(row) -> Candle:
        # MT5 liefert Bar-Zeiten in Server-/Brokerzeit. Wir stempeln sie als
        # tz-aware (UTC-Label), damit der Wert PC-unabhaengig und fuer
        # datetime-Rechnungen eindeutig ist. Das ist KEINE Umrechnung - die
        # angezeigte Uhrzeit bleibt die Brokerzeit.
        return Candle(
            time=datetime.fromtimestamp(row["time"], tz=timezone.utc),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            tick_volume=int(row["tick_volume"]),
            spread=int(row["spread"]),
            real_volume=int(row["real_volume"]),
        )

    def get_latest_candles(
        self,
        symbol: str,
        timeframe: TimeFrame,
        count: int = 1
    ) -> list[Candle]:
        """Neueste Kerzen OHNE Datumsangabe (Position 0 = aktuellste Bar).
        Immun gegen Zeitzonen-Verschiebungen: liefert immer die aktuellsten
        Bars des Brokers."""
        rates = mt5.copy_rates_from_pos(symbol, timeframe.value, 0, count)

        if rates is None:
            raise Exception(
                f"Failed loading latest candles: {mt5.last_error()}"
            )

        return [self._row_to_candle(row) for row in rates]

    def get_broker_utc_offset_hours(self, symbol: str) -> int:
        """Offset Broker-/Serverzeit -> echtes UTC in Stunden.
        Der Offset ist eine reine Server-Eigenschaft (symbolunabhaengig). Er wird
        BEVORZUGT aus einem 24/7-Symbol (Krypto) abgeleitet, dessen Tick IMMER
        frisch ist - so stimmt der Offset auch am Wochenende/Feiertag, wenn der
        Tick des Hauptsymbols (z.B. Gold) veraltet waere und sonst einen falschen
        Wert lieferte (alter Bug: ein nur wenige Stunden alter Freitags-Tick gab
        am Samstag einen plausibel aussehenden, aber FALSCHEN Offset und der
        Krypto-Fallback griff nie). Das Hauptsymbol ist nur Rueckfall (Broker
        ohne Krypto). Liefert 0, wenn nichts Plausibles da ist."""
        now = datetime.now(timezone.utc)
        for sym in ("BTCUSD", "ETHUSD", symbol):
            tick = mt5.symbol_info_tick(sym)
            if tick is None or tick.time == 0:
                continue

            server_now = datetime.fromtimestamp(tick.time, tz=timezone.utc)
            offset = round((server_now - now).total_seconds() / 3600)

            # Plausibilitaet: realistische Broker-Offsets liegen in [-14, +14];
            # ein stark veralteter Tick liefert grosse Werte -> ueberspringen.
            if abs(offset) <= 14:
                return offset

        return 0

    # ---------------------------------
    # BROKER-DST-ERKENNUNG (vollautomatisch, kein hartkodierter Tag, keine API)
    # ---------------------------------
    def detect_broker_timezone(
        self,
        ref_symbols=("BTCUSD", "ETHUSD"),
        candidate_zones=("Europe/Berlin", "America/New_York", "Australia/Sydney"),
        lookback_days: int = 400,
    ) -> Optional[str]:
        """Erkennt automatisch, ob die Broker-Serverzeit eine Sommer-/Winterzeit
        mitmacht. Rueckgabe: IANA-Zonenname, dessen DST der Broker folgt, sonst None
        (fixer Broker). Idee: ein 24/7-Symbol handelt DURCH den Umstell-Sonntag;
        stellt der Broker um, zeigt sein M5-Strom an genau diesem Tag eine fehlende/
        doppelte Stunde bzw. einen Zeitsprung. Geprueft werden NUR die bekannten
        Umstelltage (aus zoneinfo) -> wenige Abfragen. Ergebnis wird gecacht."""
        if self._broker_tz_cache != "?":
            return self._broker_tz_cache
        now = datetime.now(timezone.utc)
        result = None
        for zone in candidate_zones:
            try:
                z = ZoneInfo(zone)
            except Exception:
                continue
            hit = False
            for trans in self._dst_transitions(z, now - timedelta(days=lookback_days), now):
                if self._has_clock_shift(ref_symbols, trans) is True:
                    hit = True
                    break
            if hit:
                result = zone
                break
        self._broker_tz_cache = result
        return result

    @staticmethod
    def _dst_transitions(z: ZoneInfo, start: datetime, end: datetime):
        """Umstelltage einer Zone im Zeitraum (utcoffset wechselt)."""
        out = []
        d = start.replace(hour=0, minute=0, second=0, microsecond=0)
        prev = z.utcoffset(d)
        while d <= end:
            d += timedelta(days=1)
            cur = z.utcoffset(d)
            if cur != prev:
                out.append(d)
            prev = cur
        return out

    def _has_clock_shift(self, ref_symbols, day: datetime) -> Optional[bool]:
        """True/False, ob am Umstelltag ein Uhren-Sprung im 24/7-M5-Strom sichtbar
        ist (fehlende/doppelte Stunde oder Zeitsprung); None falls keine Daten."""
        from collections import Counter
        a = day.replace(hour=0, minute=0, second=0, microsecond=0)
        b = a + timedelta(days=1)
        for sym in ref_symbols:
            rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, a, b)
            if rates is None or len(rates) < 200:
                continue
            times = [datetime.fromtimestamp(r["time"], tz=timezone.utc) for r in rates]
            cnt = Counter(t.hour for t in times)
            for h in range(24):
                c = cnt.get(h, 0)
                if c == 0 or c >= 20:  # normal M5 = 12/h: fehlend oder doppelt
                    return True
            for i in range(1, len(times)):
                delta = (times[i] - times[i - 1]).total_seconds() / 60
                if delta < 0 or delta > 10:  # rueckwaerts oder Luecke
                    return True
            return False
        return None

    def broker_offset_at(self, dt: datetime, symbol: str) -> int:
        """Broker->UTC-Offset fuer ein (historisches) Datum. Fixer Broker ->
        konstanter Live-Offset; DST-Broker -> Live-Offset + saisonale Differenz der
        erkannten Zone (zoneinfo). Vollautomatisch, broker-/standortunabhaengig."""
        base = self.get_broker_utc_offset_hours(symbol)
        zone = self.detect_broker_timezone()
        if zone is None:
            return base
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        z = ZoneInfo(zone)
        now = datetime.now(timezone.utc)
        delta = (z.utcoffset(dt).total_seconds() - z.utcoffset(now).total_seconds()) / 3600.0
        return base + round(delta)

    # ---------------------------------
    # SYMBOL INFO
    # ---------------------------------

    def get_symbol_info(self, symbol: str):

        info = mt5.symbol_info(symbol)

        if info is None:
            raise Exception(
                f"Symbol not found: {symbol}"
            )

        return info

    def get_clean_symbol_info(self, symbol: str) -> SymbolInfo:
        """
        Fragt die rohen MT5-Symbolinformationen ab und transformiert sie
        in das saubere, typisierte SymbolInfo-Objekt für den RiskManager.
        """
        raw_info = self.get_symbol_info(symbol)
        
        return SymbolInfo(
            tick_value=float(raw_info.trade_tick_value),
            tick_size=float(raw_info.trade_tick_size),
            volume_step=float(raw_info.volume_step),
            min_volume=float(raw_info.volume_min)
        )

    # ---------------------------------
    # AVAILABLE SYMBOLS
    # ---------------------------------

    def get_symbols(self):

        symbols = mt5.symbols_get()

        return [s.name for s in symbols]
    
    def get_current_price_from_candles(candle_list: list) -> float:
        """Gibt den aktuellsten Close-Preis aus der übergebenen Kerzenliste zurück."""
        if not candle_list:
            raise ValueError("Die Kerzenliste ist leer!")
        return candle_list[-1].close


    def get_live_tick_price(self, symbol: str=config.getSymbol()) -> float:
        """
        Holt den absolut neuesten, echten Live-Preis (Bid) direkt vom MT5-Terminal.
        Erfordert, dass MetaTrader 5 initialisiert ist.
        """
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise ConnectionError(f"Failed to fetch tick for {symbol}. Is the symbol valid?")
        return tick.bid
    

    def getAllOpenPending(self):
        return mt5.orders_get()
    
    def getAllOpenTrades(self):
        return mt5.positions_get()
    
    def getAllClosedDeals(
        self,
        start: datetime,
        end: datetime
    ):
        """
        Liefert alle historischen Deals im angegebenen Zeitraum.
        """
        return mt5.history_deals_get(start, end)


    def getAllClosedOrders(
        self,
        start: datetime,
        end: datetime
    ):
        """
        Liefert alle historischen Orders im angegebenen Zeitraum.
        """
        return mt5.history_orders_get(start, end)