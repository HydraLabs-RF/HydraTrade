from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5



from core.mt5connection import MT5Connector

from core.config import configConnection, TimeFrame

from data.candle import Candle

from data.trade import Trade, TradeType, TradeAction, TradeStatus, LONG_TYPES

from core.riskManagment import SymbolInfo



mt5Connetion = MT5Connector()

config = configConnection()



class MT5CExecution:



    def _ensure_symbol(self, symbol: str) -> None:

        info = mt5.symbol_info(symbol)

        if info is None:

            raise RuntimeError(f"Symbol nicht gefunden: {symbol}")

        if not info.visible:

            if not mt5.symbol_select(symbol, True):

                raise RuntimeError(f"Symbol konnte nicht aktiviert werden: {symbol}")



    @staticmethod

    def _resolve_filling_mode(symbol: str) -> int:

        info = mt5.symbol_info(symbol)

        if info is None:

            return mt5.ORDER_FILLING_RETURN

        mode = info.filling_mode

        if mode & mt5.ORDER_FILLING_IOC:

            return mt5.ORDER_FILLING_IOC

        if mode & mt5.ORDER_FILLING_FOK:

            return mt5.ORDER_FILLING_FOK

        return mt5.ORDER_FILLING_RETURN



    def _build_request_base(self, symbol: str) -> dict:

        self._ensure_symbol(symbol)

        return {

            "symbol": symbol,

            "deviation": config.getOrderDeviation(),

            "magic": config.getMagicNumber(),

            "type_time": mt5.ORDER_TIME_GTC,

            "type_filling": self._resolve_filling_mode(symbol),

        }



    def place_market_order(self, trade: Trade) -> int:
        """Place a market buy/sell and return the position ticket."""
        tick = mt5.symbol_info_tick(trade.symbol)
        if tick is None:
            raise RuntimeError(f"No tick for {trade.symbol}")

        if trade.type == TradeType.BUY:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        elif trade.type == TradeType.SELL:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            raise RuntimeError(f"Not a market order type: {trade.type}")

        request = self._build_request_base(trade.symbol)
        request.update({
            "action": mt5.TRADE_ACTION_DEAL,
            "volume": float(trade.volume),
            "type": order_type,
            "price": float(price),
            "comment": trade.comment or "",
        })
        if trade.stop_loss is not None:
            request["sl"] = float(trade.stop_loss)
        if trade.take_profit is not None:
            request["tp"] = float(trade.take_profit)

        result = mt5.order_send(request)
        if result is None:
            raise RuntimeError(f"order_send failed: {mt5.last_error()}")
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"Market order rejected: {result.retcode} - {result.comment}")
        return int(result.order)

    def place_pending_order(self, trade: Trade) -> int:
        """Place a pending order in MT5 and return the order ticket."""
        request = self._build_request_base(trade.symbol)
        request.update({
            "action": mt5.TRADE_ACTION_PENDING,
            "volume": float(trade.volume),
            "type": trade.type.value,
            "price": float(trade.entry_price),
            "comment": trade.comment or "",
        })
        # Stop-limit: entry_price = limit, trigger_price = stop trigger
        if trade.type in (TradeType.BUY_STOP_LIMIT, TradeType.SELL_STOP_LIMIT):
            trigger = trade.trigger_price if trade.trigger_price is not None else trade.entry_price
            request["stoplimit"] = float(trigger)
        if trade.stop_loss is not None:
            request["sl"] = float(trade.stop_loss)
        if trade.take_profit is not None:
            request["tp"] = float(trade.take_profit)



        result = mt5.order_send(request)

        if result is None:

            raise RuntimeError(f"order_send fehlgeschlagen: {mt5.last_error()}")

        if result.retcode != mt5.TRADE_RETCODE_DONE:

            raise RuntimeError(f"Pending-Order abgelehnt: {result.retcode} - {result.comment}")

        return int(result.order)



    def modify_pending_order(self, ticket: int, trade: Trade) -> bool:

        request = self._build_request_base(trade.symbol)

        request.update({

            "action": mt5.TRADE_ACTION_MODIFY,

            "order": int(ticket),

            "price": float(trade.entry_price),

            "comment": trade.comment or "",

        })

        if trade.stop_loss is not None:

            request["sl"] = float(trade.stop_loss)

        if trade.take_profit is not None:

            request["tp"] = float(trade.take_profit)



        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:

            print(f"[MT5CExecution] Pending-Modify fehlgeschlagen ({ticket}): "

                  f"{None if result is None else result.retcode}")

            return False

        return True



    def remove_pending_order(self, ticket: int, symbol: str) -> bool:

        request = self._build_request_base(symbol)

        request.update({

            "action": mt5.TRADE_ACTION_REMOVE,

            "order": int(ticket),

        })

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:

            print(f"[MT5CExecution] Pending-Remove fehlgeschlagen ({ticket}): "

                  f"{None if result is None else result.retcode}")

            return False

        return True



    def modify_position_sl_tp(self, ticket: int, symbol: str,

                              sl: float | None, tp: float | None) -> bool:

        request = self._build_request_base(symbol)

        request.update({

            "action": mt5.TRADE_ACTION_SLTP,

            "position": int(ticket),

        })

        if sl is not None:

            request["sl"] = float(sl)

        if tp is not None:

            request["tp"] = float(tp)



        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:

            print(f"[MT5CExecution] SL/TP-Modify fehlgeschlagen ({ticket}): "

                  f"{None if result is None else result.retcode}")

            return False

        return True



    def close_position(self, ticket: int, symbol: str, volume: float,

                       position_type: TradeType) -> bool:

        tick = mt5.symbol_info_tick(symbol)

        if tick is None:

            print(f"[MT5CExecution] No tick for {symbol}")

            return False



        if position_type in LONG_TYPES:

            order_type = mt5.ORDER_TYPE_SELL

            price = tick.bid

        else:

            order_type = mt5.ORDER_TYPE_BUY

            price = tick.ask



        request = self._build_request_base(symbol)

        request.update({

            "action": mt5.TRADE_ACTION_DEAL,

            "position": int(ticket),

            "volume": float(volume),

            "type": order_type,

            "price": float(price),

            "comment": "close",

        })



        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:

            print(f"[MT5CExecution] Close fehlgeschlagen ({ticket}): "

                  f"{None if result is None else result.retcode}")

            return False

        return True



    def execute_trade_request(self, trade: Trade) -> Trade | None:

        """Führt eine Strategie-Trade-Anfrage aus (Pending, Modify, Remove, SL/TP, Close)."""

        try:

            if trade.action == TradeAction.ACTION and trade.status == TradeStatus.RUNNING:
                ticket = self.place_market_order(trade)
                trade.ticket = ticket
                trade.status = TradeStatus.RUNNING
                return trade

            if trade.action == TradeAction.PENDING:

                ticket = self.place_pending_order(trade)

                trade.ticket = ticket

                trade.status = TradeStatus.OPEN

                return trade



            if trade.action == TradeAction.PENDING_MODIFY:

                if self.modify_pending_order(trade.ticket, trade):

                    return trade

                return None



            if trade.action == TradeAction.PENDING_REMOVE:

                if self.remove_pending_order(trade.ticket, trade.symbol):

                    return trade

                return None



            if trade.action == TradeAction.ACTION_MODIFY_SL_TP:

                if self.modify_position_sl_tp(

                    trade.ticket, trade.symbol, trade.stop_loss, trade.take_profit

                ):

                    return trade

                return None



            if trade.status == TradeStatus.CLOSED:

                if self.close_position(trade.ticket, trade.symbol, trade.volume, trade.type):

                    return trade

                return None



        except Exception as e:

            print(f"[MT5CExecution] execute_trade_request error: {e}")

        return None



    def getCurrentPrice(self) -> float:

        return mt5Connetion.get_live_tick_price()

    

    def getCurrentPriceSymbole(self, Symbol: str) -> float:

        return mt5Connetion.get_live_tick_price(Symbol)

    

    def spotExecution(self, Trade: Trade):

        return self.execute_trade_request(Trade)

    

    def getCandles(

            self,

            timeframe: TimeFrame = TimeFrame.M15,

            Symbol: str | None = config.getSymbol(),

            start: datetime = None,

            end: datetime = None,

            reference_time: datetime | None = None

            )->list[Candle]:

        default_start, default_end = self.get_default_candle_window(reference_time)

        if start is None:

            start = default_start

        if end is None:

            end = default_end

        return mt5Connetion.get_candles(Symbol, timeframe, start, end)

    def getLatestCandles(
        self,
        timeframe: TimeFrame = TimeFrame.M15,
        Symbol: str | None = config.getSymbol(),
        count: int = 1
    ) -> list[Candle]:
        return mt5Connetion.get_latest_candles(Symbol, timeframe, count)

    def getLatestCandle(
        self,
        timeframe: TimeFrame = TimeFrame.M15,
        Symbol: str | None = config.getSymbol()
    ) -> Candle | None:
        candles = self.getLatestCandles(timeframe, Symbol, 1)
        return candles[-1] if candles else None

    def get_broker_utc_offset_hours(
        self,
        Symbol: str | None = config.getSymbol()
    ) -> int:
        return mt5Connetion.get_broker_utc_offset_hours(Symbol)

    @staticmethod

    def getAllOpenPendingOrder():

        """Statisch, da vom TradeTracker direkt via Klasse aufgerufen."""

        return mt5Connetion.getAllOpenPending()

    

    @staticmethod

    def getAllOpenActivOrder():

        """Statisch, da vom TradeTracker direkt via Klasse aufgerufen."""

        return mt5Connetion.getAllOpenTrades()



    @staticmethod

    def get_default_candle_window(reference_time: datetime | None = None):

        if reference_time is None:

            reference_time = datetime.now(timezone.utc)

        if reference_time.tzinfo is None:

            reference_time = reference_time.replace(tzinfo=timezone.utc)

        end = reference_time

        start = end - timedelta(days=3)



        return start, end

    

    def getCandlesBetween(

        self,

        timeframe: TimeFrame,

        start: datetime,

        end: datetime,

        Symbol: str | None = config.getSymbol()

        ) -> list[Candle]:



        return mt5Connetion.get_candles(

            Symbol,

            timeframe,

            start,

            end

        )

    

    def getCandleAt(

        self,

        timeframe: TimeFrame,

        reference_time: datetime,

        Symbol: str | None = config.getSymbol()

        ) -> Candle | None:



        candles = self.getCandles(

            timeframe=timeframe,

            Symbol=Symbol,

            reference_time=reference_time

        )



        if len(candles) == 0:

            return None



        return candles[-1]

    



    def getHistoricalCandles(

        self,

        timeframe: TimeFrame,

        reference_time: datetime,

        candle_count: int,

        Symbol: str | None = config.getSymbol()

        ) -> list[Candle]:



        candles = self.getCandles(

            timeframe=timeframe,

            Symbol=Symbol,

            reference_time=reference_time

        )



        return candles[-candle_count:]



    def get_symbol_info(self, symbol: str) -> SymbolInfo:

        raw_info = mt5Connetion.get_symbol_info(symbol)

        

        return SymbolInfo(

            name=str(raw_info.name),

            tick_value=float(raw_info.trade_tick_value),

            tick_size=float(raw_info.trade_tick_size),

            contract_size=float(raw_info.trade_contract_size),

            volume_step=float(raw_info.volume_step),

            min_volume=float(raw_info.volume_min),

            currency_profit=str(raw_info.currency_profit),

            digits=int(raw_info.digits),

            stops_level=int(raw_info.trade_stops_level)

        )



    def get_account_equity(self) -> float:

        account_info = mt5.account_info()

        if account_info is None:

            return 10000.0  

        return float(account_info.equity)



    def get_account_currency(self) -> str:

        account_info = mt5.account_info()

        if account_info is None:

            return "USD"

        return str(account_info.currency)

    

    @staticmethod

    def getAllClosedDeals(

        start: datetime,

        end: datetime

    ):

        return mt5Connetion.getAllClosedDeals(start, end)



    @staticmethod

    def getAllClosedOrders(

        start: datetime,

        end: datetime

    ):

        return mt5Connetion.getAllClosedOrders(start, end)

    

    @staticmethod

    def _get_closed_deals_by_comment(

        comment_string: str,

        start: datetime,

        end: datetime

    ):

        deals = MT5CExecution.getAllClosedDeals(start, end)



        if not deals:

            return []



        search_str = comment_string.strip().lower()



        return [

            deal

            for deal in deals

            if getattr(deal, "comment", None)

            and deal.comment.strip().lower() == search_str

        ]


