import MetaTrader5 as mt5

from datetime import datetime, timezone

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
        Vergleicht den juengsten Tick (Serverzeit) mit datetime.now(UTC).
        Der Offset ist eine Server-Eigenschaft (symbolunabhaengig); ist der
        Tick des Hauptsymbols veraltet (Markt zu, z.B. Wochenende), wird auf
        24/7-Symbole zurueckgegriffen. Liefert 0, wenn nichts Plausibles da ist."""
        for sym in (symbol, "BTCUSD", "ETHUSD"):
            tick = mt5.symbol_info_tick(sym)
            if tick is None or tick.time == 0:
                continue

            server_now = datetime.fromtimestamp(tick.time, tz=timezone.utc)
            offset = round(
                (server_now - datetime.now(timezone.utc)).total_seconds() / 3600
            )

            # Plausibilitaet: realistische Broker-Offsets liegen in [-12, +14].
            # Ein veralteter Tick liefert riesige Werte -> ueberspringen.
            if abs(offset) <= 14:
                return offset

        return 0

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