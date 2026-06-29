"""
Sanity check for a single strategy run — lists every trade in detail.

Checks for simulation artifacts (impossible PnLs, wrong volumes, exits outside
candle range) before trusting results or going live with a new variant.

Usage:
    python run_sanity_check.py --variant example_ema_cross --start 2026-03-08 --end 2026-06-08
"""

import argparse
from datetime import datetime, timezone

from core.config import configConnection
from core.enums import TimeFrame
from core.mt5connection import MT5Connector
from analysis.simulationAnalyzer import AnalyzedSimulation
from analysis.runManager import create_run_dir, write_text
from execution.live.mt5execution import MT5CExecution
from strategie.registry import get_variant


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)

    config = configConnection()
    config.live = False
    symbol = config.getSymbol()

    connector = MT5Connector()
    connector.initialize()
    connector.set_testing_window(start, end)

    spec = get_variant(args.variant)
    sim = AnalyzedSimulation(symbol, start, end, TimeFrame.M5)
    sim.set_strategy(spec.factory())
    sim.run_quiet()

    sym_info = MT5CExecution().get_symbol_info(symbol)
    tick_value = sym_info.tick_value
    tick_size = sym_info.tick_size or 0.00001

    lines = [f"SANITY CHECK {spec.name} [{spec.variant_id}]  {start.date()} -> {end.date()}", ""]
    balance = config.getSimEQ()
    closed = sorted(sim.memory.get_closed_trades(), key=lambda t: t.close_time or t.open_time)
    for i, t in enumerate(closed, 1):
        risk = abs(t.entry_price - (t.initial_stop_loss or 0))
        r = 0.0
        if risk > 0 and t.exit_price is not None:
            direction = 1 if t.type.name.startswith("BUY") else -1
            r = (t.exit_price - t.entry_price) * direction / risk
        risk_money = (risk / tick_size) * tick_value * t.volume if tick_size > 0 else 0.0
        balance += t.pnl or 0
        lines.append(
            f"#{i:2d} {t.type.name:<10} open {t.open_time} close {t.close_time} | "
            f"entry {t.entry_price:.2f} exit {t.exit_price:.2f} initSL {t.initial_stop_loss} TP {t.take_profit} | "
            f"vol {t.volume:.2f} | R {r:+.2f} | risk_eur ~{risk_money:,.0f} | pnl {t.pnl:+,.2f} | "
            f"balance {balance:,.0f} | {t.status.name}"
        )

    lines.append("")
    lines.append(f"End balance: {balance:,.2f} | Trades: {len(closed)}")

    text = "\n".join(lines)
    print(text)
    run_dir = create_run_dir(f"sanity_{spec.variant_id}")
    write_text(run_dir, "sanity.txt", text)
    connector.shutdown()


if __name__ == "__main__":
    main()
