"""
MT5 status queries for the web UI.

All access to the MetaTrader5 module goes through a lock (the module is
not thread-safe) and connection status is briefly cached so the UI does
not touch the terminal on every poll.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

_lock = threading.Lock()
_status_cache: dict = {}
_status_cache_time: float = 0.0
STATUS_CACHE_SECONDS = 30


def _namedtuple_to_dict(obj) -> dict:
    if obj is None:
        return {}
    try:
        return dict(obj._asdict())
    except Exception:
        return {}


def check_status(symbol: str, force: bool = False) -> dict:
    """Connection check: terminal, account, auto-trading, symbol, data coverage."""
    global _status_cache, _status_cache_time

    if not MT5_AVAILABLE:
        return {
            "package_installed": False,
            "connected": False,
            "error": "Python package 'MetaTrader5' is not installed.",
        }

    with _lock:
        now = time.time()
        if not force and _status_cache and now - _status_cache_time < STATUS_CACHE_SECONDS \
                and _status_cache.get("symbol_checked") == symbol:
            return _status_cache

        result: dict = {"package_installed": True, "connected": False, "symbol_checked": symbol}
        try:
            if not mt5.initialize():
                result["error"] = f"MT5 initialization failed: {mt5.last_error()}"
            else:
                result["connected"] = True
                term = mt5.terminal_info()
                acc = mt5.account_info()
                if term:
                    result["terminal"] = {
                        "name": term.name,
                        "company": term.company,
                        "build": term.build,
                        "market_connected": bool(term.connected),
                        "trade_allowed": bool(term.trade_allowed),
                        "path": term.path,
                    }
                if acc:
                    result["account"] = {
                        "login": acc.login,
                        "server": acc.server,
                        "currency": acc.currency,
                        "balance": acc.balance,
                        "equity": acc.equity,
                        "margin_free": acc.margin_free,
                        "leverage": acc.leverage,
                        "trade_mode": acc.trade_mode,  # 0=Demo, 1=Contest, 2=Real
                    }
                info = mt5.symbol_info(symbol)
                if info is None:
                    result["symbol_ok"] = False
                    result["symbol_error"] = f"Symbol '{symbol}' not found in terminal."
                else:
                    result["symbol_ok"] = True
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        result["last_price"] = tick.bid
                        result["last_tick_time"] = datetime.fromtimestamp(
                            tick.time, tz=timezone.utc).isoformat(timespec="seconds")
                    # How far back do M5 data extend? (important for backtests)
                    # copy_rates_from_pos instead of copy_rates_range: large ranges
                    # exceed the terminal's MaxBars limit.
                    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 99999)
                    if rates is not None and len(rates) > 0:
                        result["m5_history_start"] = datetime.fromtimestamp(
                            int(rates[0]["time"]), tz=timezone.utc).date().isoformat()
                        result["m5_last_candle"] = datetime.fromtimestamp(
                            int(rates[-1]["time"]), tz=timezone.utc).isoformat(timespec="seconds")
        except Exception as e:
            result["error"] = f"MT5 query failed: {e}"
        finally:
            try:
                mt5.shutdown()
            except Exception:
                pass

        result["checked_at"] = datetime.now().isoformat(timespec="seconds")
        _status_cache = result
        _status_cache_time = now
        return result


def get_live_overview(symbol: str) -> dict:
    """Current positions, pending orders, and account balance (always fresh)."""
    if not MT5_AVAILABLE:
        return {"error": "Python-Paket 'MetaTrader5' ist nicht installiert."}

    with _lock:
        try:
            if not mt5.initialize():
                return {"error": f"MT5-Initialisierung fehlgeschlagen: {mt5.last_error()}"}

            acc = mt5.account_info()
            positions = mt5.positions_get() or []
            orders = mt5.orders_get() or []

            type_names = {0: "BUY", 1: "SELL", 2: "BUY LIMIT", 3: "SELL LIMIT",
                          4: "BUY STOP", 5: "SELL STOP"}

            def pos_dict(p):
                return {
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "type": type_names.get(p.type, str(p.type)),
                    "volume": p.volume,
                    "price_open": p.price_open,
                    "price_current": p.price_current,
                    "sl": p.sl,
                    "tp": p.tp,
                    "profit": p.profit,
                    "magic": p.magic,
                    "time": datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(timespec="seconds"),
                }

            def order_dict(o):
                return {
                    "ticket": o.ticket,
                    "symbol": o.symbol,
                    "type": type_names.get(o.type, str(o.type)),
                    "volume": o.volume_current,
                    "price_open": o.price_open,
                    "sl": o.sl,
                    "tp": o.tp,
                    "magic": o.magic,
                    "time_setup": datetime.fromtimestamp(o.time_setup, tz=timezone.utc).isoformat(timespec="seconds"),
                }

            result = {
                "positions": [pos_dict(p) for p in positions],
                "pending_orders": [order_dict(o) for o in orders],
                "checked_at": datetime.now().isoformat(timespec="seconds"),
            }
            if acc:
                result["account"] = {
                    "login": acc.login,
                    "server": acc.server,
                    "currency": acc.currency,
                    "balance": acc.balance,
                    "equity": acc.equity,
                    "profit": acc.profit,
                    "margin_free": acc.margin_free,
                    "trade_mode": acc.trade_mode,
                }
            return result
        except Exception as e:
            return {"error": f"MT5-Abfrage fehlgeschlagen: {e}"}
        finally:
            try:
                mt5.shutdown()
            except Exception:
                pass
