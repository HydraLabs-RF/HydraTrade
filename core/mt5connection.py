import MetaTrader5 as mt5

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from core.enums import TimeFrame
from core.config import configConnection
from data.candle import Candle
from core.riskManagment import SymbolInfo  # Import of the required dataclass

config = configConnection()


class MT5Connector:

    def __init__(self):

        self.connected = False
        self.testing_mode = True

        self.test_start = None
        self.test_end = None

        # Cache for broker DST detection ("?" = not yet detected,
        # None = fixed broker without DST, otherwise IANA zone name).
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
        # MT5 returns bar times in server/broker time. We stamp them as
        # tz-aware (UTC label) so the value is machine-independent and
        # unambiguous for datetime arithmetic. This is NOT a conversion - the
        # displayed clock time remains broker time.
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
        """Latest candles WITHOUT a date range (position 0 = most recent bar).
        Immune to timezone shifts: always returns the broker's most recent
        bars."""
        rates = mt5.copy_rates_from_pos(symbol, timeframe.value, 0, count)

        if rates is None:
            raise Exception(
                f"Failed loading latest candles: {mt5.last_error()}"
            )

        return [self._row_to_candle(row) for row in rates]

    def get_broker_utc_offset_hours(self, symbol: str) -> int:
        """Offset from broker/server time to true UTC in hours.
        The offset is a pure server property (symbol-independent). It is
        PREFERRED to derive it from a 24/7 symbol (crypto) whose tick is ALWAYS
        fresh - so the offset is correct on weekends/holidays when the main
        symbol's tick (e.g. gold) would be stale and otherwise yield a wrong
        value (old bug: a Friday tick only a few hours old gave a plausible but
        WRONG offset on Saturday and the crypto fallback never kicked in). The
        main symbol is only a fallback (brokers without crypto). Returns 0 when
        nothing plausible is available."""
        now = datetime.now(timezone.utc)
        for sym in ("BTCUSD", "ETHUSD", symbol):
            tick = mt5.symbol_info_tick(sym)
            if tick is None or tick.time == 0:
                continue

            server_now = datetime.fromtimestamp(tick.time, tz=timezone.utc)
            offset = round((server_now - now).total_seconds() / 3600)

            # Plausibility: realistic broker offsets lie in [-14, +14];
            # a heavily stale tick yields large values -> skip.
            if abs(offset) <= 14:
                return offset

        return 0

    # ---------------------------------
    # BROKER DST DETECTION (fully automatic, no hardcoded date, no API)
    # ---------------------------------
    def detect_broker_timezone(
        self,
        ref_symbols=("BTCUSD", "ETHUSD"),
        candidate_zones=("Europe/Berlin", "America/New_York", "Australia/Sydney"),
        lookback_days: int = 400,
    ) -> Optional[str]:
        """Automatically detects whether broker server time follows daylight saving.
        Returns: IANA zone name whose DST the broker follows, otherwise None
        (fixed broker). Idea: a 24/7 symbol trades THROUGH the transition Sunday;
        if the broker switches, its M5 stream on that exact day shows a missing/
        duplicate hour or a time jump. ONLY known transition days (from zoneinfo)
        are checked -> few queries. Result is cached."""
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
        """Transition days of a zone in the period (utcoffset changes)."""
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
        """True/False whether a clock jump is visible in the 24/7 M5 stream on the
        transition day (missing/duplicate hour or time jump); None if no data."""
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
                if c == 0 or c >= 20:  # normal M5 = 12/h: missing or duplicate
                    return True
            for i in range(1, len(times)):
                delta = (times[i] - times[i - 1]).total_seconds() / 60
                if delta < 0 or delta > 10:  # backwards or gap
                    return True
            return False
        return None

    def broker_offset_at(self, dt: datetime, symbol: str) -> int:
        """Broker->UTC offset for a (historical) date. Fixed broker ->
        constant live offset; DST broker -> live offset + seasonal difference of the
        detected zone (zoneinfo). Fully automatic, broker/location independent."""
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
        Fetches raw MT5 symbol information and transforms it
        into the clean, typed SymbolInfo object for the RiskManager.
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
        """Returns the most recent close price from the given candle list."""
        if not candle_list:
            raise ValueError("Die Kerzenliste ist leer!")
        return candle_list[-1].close


    def get_live_tick_price(self, symbol: str=config.getSymbol()) -> float:
        """
        Fetches the absolute latest real live price (bid) directly from the MT5 terminal.
        Requires MetaTrader 5 to be initialized.
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
        Returns all historical deals in the given time range.
        """
        return mt5.history_deals_get(start, end)


    def getAllClosedOrders(
        self,
        start: datetime,
        end: datetime
    ):
        """
        Returns all historical orders in the given time range.
        """
        return mt5.history_orders_get(start, end)