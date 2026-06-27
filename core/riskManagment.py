from dataclasses import dataclass
import math

@dataclass
class SymbolInfo:
    name: str                    # e.g. "XAUUSD", "ETHUSD", "DE40"
    tick_value: float            # monetary value per tick per contract
    tick_size: float             # price movement per tick
    contract_size: float         # contract size (e.g. 100 for gold)
    volume_step: float = 0.01    # minimum step size (VOLUME_STEP)
    min_volume: float = 0.01     # minimum lot size (VOLUME_MIN)
    currency_profit: str = "USD" # profit currency (e.g. "USD" or "EUR")
    digits: int = 2              # decimal places of the symbol (for rounding)
    stops_level: int = 10        # minimum distance for SL/TP in points

class RiskManager:

    def __init__(self):
        self.risk_map = {
            "A": 0.01,
            "B": 0.005,
            "C": 0.002
        }

    def get_lot_size(
        self,
        equity: float,
        risk_grade: str,
        sl_points: float,
        symbol_info: SymbolInfo,
        account_currency: str = "USD",
        fx_rate_provider = None  # Pass MT5CExecution here
    ) -> float:

        if risk_grade not in self.risk_map:
            raise ValueError("Risk grade must be A, B or C")

        if sl_points <= 0:
            raise ValueError("SL points must be > 0")

        # 1. Calculate money at risk in ACCOUNT CURRENCY
        risk_percent = self.risk_map[risk_grade]
        risk_money = equity * risk_percent

        # 2. Loss per lot in SYMBOL PROFIT CURRENCY
        loss_per_lot_symbol_currency = sl_points * (symbol_info.tick_value / symbol_info.tick_size)

        # 3. Currency conversion if account currency != symbol profit currency
        if account_currency != symbol_info.currency_profit:
            if fx_rate_provider is not None:
                # Path A: "EURUSD" (standard)
                pair_direct = f"{account_currency}{symbol_info.currency_profit}"
                # Path B: "USDEUR" -> reciprocal ("EURUSD")
                pair_inverse = f"{symbol_info.currency_profit}{account_currency}"
                
                conversion_rate = None
                
                # Attempt 1: query direct pair
                try:
                    price = fx_rate_provider.getCurrentPriceSymbole(pair_direct)
                    if price and price > 0:
                        conversion_rate = price
                except Exception:
                    pass
                
                # Attempt 2: if direct pair does not exist, query inverse pair and invert
                if conversion_rate is None:
                    try:
                        price = fx_rate_provider.getCurrentPriceSymbole(pair_inverse)
                        if price and price > 0:
                            # If EURUSD rate is 1.08, USDEUR value = 1 / 1.08
                            conversion_rate = 1.0 / price
                    except Exception as e:
                        print(f"[RiskManager] Critical: could not fetch currency pairs {pair_direct} or {pair_inverse}: {e}")
                
                # Perform conversion
                if conversion_rate is not None:
                    risk_money = risk_money * conversion_rate
                else:
                    print(f"[RiskManager] Warning: no FX conversion for {account_currency} -> {symbol_info.currency_profit}, using 1.0")
            else:
                print("[RiskManager] Warning: currency mismatch but no fx_rate_provider supplied!")

        if loss_per_lot_symbol_currency == 0:
            raise ValueError("Invalid SL calculation")

        # 4. Calculate lots
        raw_lot_size = risk_money / loss_per_lot_symbol_currency

        # --- Adjust for broker limits & steps ---
        lot_size = math.floor(raw_lot_size / symbol_info.volume_step) * symbol_info.volume_step
        lot_size = round(lot_size, 4)

        if lot_size < symbol_info.min_volume:
            lot_size = symbol_info.min_volume

        return lot_size