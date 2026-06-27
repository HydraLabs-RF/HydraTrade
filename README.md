# HydraTrade Framework

**Empowering Intelligent Trading**

HydraTrade is a Python trading framework built on MetaTrader 5. It provides a unified simulation engine, live execution layer, HTML reporting, and a local web UI — so you can develop, backtest, and deploy strategies from one codebase.

> **Important:** The strategies in this repository are **example templates only**. They demonstrate how to use the framework API. They are **not** intended for live trading or production use.

---

## Quick start

### Requirements

- Python 3.10+
- MetaTrader 5 terminal (logged in, symbol visible)
- `pip install MetaTrader5`

### Run a simulation (CLI)

```bash
python main.py
```

Runs the default example strategy (`example_ema_cross`) over the configured simulation window.

### Web UI

```bash
python run_webui.py
```

Opens `http://127.0.0.1:8350` — run backtests, view reports, and monitor live trading without editing code.

### Custom benchmark

```bash
python run_custom_benchmark.py --variants example_ema_cross,example_supertrend --start 2026-03-01 --end 2026-06-01
python run_custom_benchmark.py --variants example_volume_profile --multi-period --name my_test
```

### All example strategies at once

```bash
python run_examples.py
```

Generates multi-period HTML reports under `reports/runs/`. Sample reports for the shipped examples are committed there for reference; regenerate with `python run_examples.py` when you change strategies or simulation settings.

---

## Example strategies

| ID | Name | Demonstrates |
|---|---|---|
| `example_ema_cross` | EMA Cross | Market entries on H1 EMA cross (`TradeAction.ACTION`), SL/TP only |
| `example_supertrend` | SuperTrend | Stop entries on H1 trend flips (`BUY_STOP` / `SELL_STOP`) |
| `example_volume_profile` | Volume Profile | Limit entries at session POC with trend filter (`BUY_LIMIT` / `SELL_LIMIT`) |

These are **educational demos**, not tuned for profit. Expect roughly breakeven results with modest drawdown — enough to show how the framework behaves, not to imply edge.

Source code lives in `strategie/examples/`. Each file has a header explaining what it demonstrates.

---

## Writing your own strategy

1. Subclass `strategie.Strategy` (or `strategie.examples.base.ExampleStrategyBase` for common wiring).
2. Implement hooks:
   - `planTradeGrade_A/B/C` — entry signals
   - `adjustPendingTradeGrade_*` — pending order management
   - `manageActiveTradeGrade_*` — trailing, SL/TP updates, manual close
3. Register in `strategie/registry.py`.
4. Run a sanity check before trusting results:

```bash
python run_sanity_check.py --variant your_id --start 2026-03-01 --end 2026-06-01
```

### Order types supported

| Type | Simulation | Live (MT5) |
|---|---|---|
| Market buy/sell | `TradeAction.ACTION` + `TradeType.BUY/SELL` | ✅ |
| Limit buy/sell | `TradeAction.PENDING` + `BUY_LIMIT/SELL_LIMIT` | ✅ |
| Stop buy/sell | `TradeAction.PENDING` + `BUY_STOP/SELL_STOP` | ✅ |
| Stop-limit | `PENDING` + `BUY_STOP_LIMIT/SELL_STOP_LIMIT` + `trigger_price` | ✅ |
| Modify pending | `TradeAction.PENDING_MODIFY` | ✅ |
| Remove pending | `TradeAction.PENDING_REMOVE` | ✅ |
| Modify SL/TP | `TradeAction.ACTION_MODIFY_SL_TP` | ✅ |
| Close position | `TradeStatus.CLOSED` in `manage_trailing` | ✅ |

---

## Project structure

```
HydraTrade/
├── core/           # Config, MT5 connection, risk management, branding
├── data/           # Trade model, candles, enums
├── execution/
│   ├── simulation/ # Backtest engine
│   └── live/       # Live loop + MT5 order execution
├── strategie/
│   ├── Strategy.py # Abstract base class
│   ├── registry.py # Strategy catalog
│   ├── examples/   # Shipped example strategies
│   └── tools/      # Indicators (EMA, ATR, SuperTrend, Volume Profile, …)
├── analysis/       # Reports, benchmarks, multi-period tests
├── webui/          # Local web control center
├── reports/runs/   # Generated HTML/JSON reports
├── main.py         # CLI simulation entry
├── run_live.py     # CLI live entry
└── run_webui.py    # Web UI entry
```

---

## Configuration

Defaults are in `core/config.py`. Override via `webui_config.json` (created from the Web UI Settings page):

```json
{
  "symbol": "XAUUSD",
  "timeframe": "H1",
  "simulation_start_date": "2026-04-30",
  "simulation_end_date": "2026-06-05",
  "simEQ": 100000,
  "simAccCurency": "EUR",
  "simSwapEnabled": true
}
```

`simSwapEnabled` models overnight swap in backtests (live values from MT5). Disable it to isolate signal quality from holding costs.

---

## Live trading warning

Live trading sends **real orders** to your MT5 account. The Web UI requires typing `LIVE` to confirm. Example strategies ship with conservative risk (0.5%) but are still **demonstration code only**.

When stopping a live job, open positions and pending orders **remain in MT5** and are no longer managed by the framework.

---

## Planned updates

The following features are on the roadmap. They are **not implemented yet** — listed here for transparency and direction.

### Multi-symbol support

Run strategies across **multiple symbols** in one session: shared portfolio view, per-symbol configuration, and reports that compare or aggregate results across instruments (not only a single `symbol` in config).

### MT5 auto-login

**Automatic login** into the MetaTrader 5 terminal from the framework (credentials via secure local config or environment variables), so startup does not depend on manually opening MT5 and clicking through the login dialog. Terminal must still be installed; this removes the manual login step.

### Broker API integration (MT5-optional)

A **pluggable execution and data layer** so advanced users can connect **direct broker or market-data APIs** instead of MetaTrader 5. This would require:

- A broker (or data provider) API that supports **historical and live market data**
- For live trading: an API that allows **placing and managing orders**

The goal is optional operation **without the MT5 terminal** for users who have such API access. Simulation and live paths would share the same strategy interface; MT5 would remain the default path for users who already use MetaTrader.

---

## License

[MIT License](LICENSE) — Copyright (c) 2026 HydraLabs.

You may use, copy, modify, merge, publish, distribute, sublicense, and sell copies of this software, provided the copyright notice and permission notice are included in all copies or substantial portions.
