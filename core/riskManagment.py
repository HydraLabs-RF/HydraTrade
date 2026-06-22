from dataclasses import dataclass
import math

@dataclass
class SymbolInfo:
    name: str                    # z.B. "XAUUSD", "ETHUSD", "DE40"
    tick_value: float            # Geldwert pro Tick und pro Kontrakt
    tick_size: float             # Preisbewegung pro Tick
    contract_size: float         # Kontraktgröße (z.B. 100 für Gold)
    volume_step: float = 0.01    # Mindestschrittgröße (VOLUME_STEP)
    min_volume: float = 0.01     # Mindest-Lotsize (VOLUME_MIN)
    currency_profit: str = "USD" # Währung des Gewinns (z.B. "USD" oder "EUR")
    digits: int = 2              # NEU: Nachkommastellen des Symbols (für Rundungen)
    stops_level: int = 10        # NEU: Mindestabstand für SL/TP in Punkten

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
        fx_rate_provider = None  # Hier übergeben wir MT5CExecution
    ) -> float:

        if risk_grade not in self.risk_map:
            raise ValueError("Risk grade must be A, B or C")

        if sl_points <= 0:
            raise ValueError("SL points must be > 0")

        # 1. Zu riskierendes Geld in KONTOWÄHRUNG berechnen
        risk_percent = self.risk_map[risk_grade]
        risk_money = equity * risk_percent

        # 2. Verlust pro Lot in SYMBOL-GEWINNWÄHRUNG
        loss_per_lot_symbol_currency = sl_points * (symbol_info.tick_value / symbol_info.tick_size)

        # 3. Währungsausgleich, falls Kontowährung != Symbol-Gewinnwährung
        if account_currency != symbol_info.currency_profit:
            if fx_rate_provider is not None:
                # Weg A: "EURUSD" (Standard)
                pair_direct = f"{account_currency}{symbol_info.currency_profit}"
                # Weg B: "USDEUR" -> Reziprok ("EURUSD")
                pair_inverse = f"{symbol_info.currency_profit}{account_currency}"
                
                conversion_rate = None
                
                # Versuch 1: Direktes Paar abfragen
                try:
                    price = fx_rate_provider.getCurrentPriceSymbole(pair_direct)
                    if price and price > 0:
                        conversion_rate = price
                except Exception:
                    pass
                
                # Versuch 2: Wenn direkt nicht existiert, umgekehrtes Paar abfragen und invertieren
                if conversion_rate is None:
                    try:
                        price = fx_rate_provider.getCurrentPriceSymbole(pair_inverse)
                        if price and price > 0:
                            # Wenn Kurs für EURUSD 1.08 ist, ist der Wert von USDEUR = 1 / 1.08
                            conversion_rate = 1.0 / price
                    except Exception as e:
                        print(f"[RiskManager] Critical: could not fetch currency pairs {pair_direct} or {pair_inverse}: {e}")
                
                # Konvertierung durchführen
                if conversion_rate is not None:
                    risk_money = risk_money * conversion_rate
                else:
                    print(f"[RiskManager] Warning: no FX conversion for {account_currency} -> {symbol_info.currency_profit}, using 1.0")
            else:
                print("[RiskManager] Warning: currency mismatch but no fx_rate_provider supplied!")

        if loss_per_lot_symbol_currency == 0:
            raise ValueError("Invalid SL calculation")

        # 4. Lots berechnen
        raw_lot_size = risk_money / loss_per_lot_symbol_currency

        # --- Broker Limits & Steps anpassen ---
        lot_size = math.floor(raw_lot_size / symbol_info.volume_step) * symbol_info.volume_step
        lot_size = round(lot_size, 4)

        if lot_size < symbol_info.min_volume:
            lot_size = symbol_info.min_volume

        return lot_size