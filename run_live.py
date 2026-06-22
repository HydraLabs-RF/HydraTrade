"""HydraTrade — live trading entry point."""

import argparse

from core.branding import log, print_banner
from core.config import configConnection
from core.enums import TimeFrame
from core.mt5connection import MT5Connector
from execution.live.liveExecution import LiveExecution
from strategie.registry import get_variant


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HydraTrade live trading")
    parser.add_argument(
        "--variant",
        default="example_ema_cross",
        help="Strategy variant ID (default: example_ema_cross)",
    )
    args = parser.parse_args()

    print_banner()
    config = configConnection()
    config.live = True

    spec = get_variant(args.variant)
    log(f"Live strategy: {spec.name} [{spec.variant_id}]")
    log("WARNING: Example strategies are for demonstration only.")

    connector = MT5Connector()
    connector.initialize()

    live = LiveExecution(config.getSymbol(), TimeFrame.M5)
    live.set_strategy(spec.factory())

    try:
        live.run()
    finally:
        connector.shutdown()
