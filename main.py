"""HydraTrade — simulation entry point."""

from core.branding import log, print_banner
from core.config import configConnection
from core.enums import TimeFrame
from core.mt5connection import MT5Connector
from execution.simulation.simulationMain import SimulationExecution
from strategie.registry import get_variant


def main():
    print_banner()
    config = configConnection()
    connector = MT5Connector()
    connector.initialize()
    connector.set_testing_window(config.getSimulationStart(), config.getSimulationEnd())

    variant_id = "example_ema_cross"
    spec = get_variant(variant_id)
    log(f"Running example simulation: {spec.name} [{variant_id}]")

    sim = SimulationExecution(
        config.getSymbol(),
        config.getSimulationStart(),
        config.getSimulationEnd(),
        TimeFrame.M5,
    )
    sim.set_strategy(spec.factory())
    sim.run_simulation()
    connector.shutdown()


if __name__ == "__main__":
    main()
