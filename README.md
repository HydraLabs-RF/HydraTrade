# HydraTrade

**Your framework for building the trading system you need.**

Backtest, research, and run MetaTrader 5 strategies in Python — from a first experiment to a full platform you design yourself.

HydraTrade is an open-source **framework for developers and researchers**. You implement strategies in Python, run them through a shared simulation engine, execute live via MT5, and analyse results with HTML reports and a local control-center UI. What you build on top of it can grow into your own **system or platform** — the framework is the foundation, not the ceiling.

> **Example strategies:** The shipped templates are **educational only**. They were chosen to perform **roughly neutral to slightly negative** on purpose — they show *how* to use the Strategy interface, not *what* to trade. They are not intended for live trading or production use.
>
> **Professional use:** Building something commercial with HydraTrade yourself is fine under MIT (see [Professional services](#professional-services)). If you want a **ready-made licensed strategy**, development help, or an audit — see the same section.

---

## What you can do today

| Area | What HydraTrade provides |
|------|---------------------------|
| **Develop** | Subclass `Strategy`, implement lifecycle hooks, register variants, reuse indicators and tools |
| **Backtest** | Candle-by-candle simulation, realistic stop/limit fills, optional overnight swap modelling |
| **Benchmark** | Single-window and **multi-period** runs, HTML/JSON reports, consistency and prop-style metrics |
| **Live trade** | MT5 order execution, position tracking, local live loop |
| **Operate** | Local **Web UI** to start jobs, view reports, trade history, and monitor live trading |
| **Analyse** | Trade outcome categories, drawdown stats, capture ratio, grade-split HTML reports |
| **Agent assist** | Portable **agent knowledge** (markdown + CLI) for any coding assistant; **Cursor** and **Claude Code (VS Code)** one-click install; the agent can also run/execute trades via the plugin ([details](agent/README.md)) |
| **Extend** | One codebase for simulation and live; you choose symbols, risk, logic, and how far you take it |

HydraTrade is meant to be **built on**. Use it for private research, internal tools, or as the core of something larger — you decide how far it goes.

More capabilities are planned; see [Roadmap](#roadmap) for what comes next.

---

## Professional services

### Open source (MIT) — developers & researchers

The repository is licensed under [MIT](LICENSE). You may download, use, modify, and **commercialize what you build yourself** — strategies, tooling, and deployments you create are yours, subject to the MIT license terms for the framework code itself.

- Self-serve: examples, docs in this repo, GitHub Issues (best effort)
- **You are responsible** for your strategy logic, risk settings, compliance, and any live deployment

The example strategies in this repo are **not** production offerings. They are deliberately weak performers so nobody mistakes a demo for edge.

### Commercial services (HydraLabs)

Separate from the open-source repo — contact details **will be announced soon** (this repository will be updated when they are available).

| Service | Description |
|---------|-------------|
| **Strategy development** | Design, implement, and backtest strategies on HydraTrade — including help turning your idea into working code |
| **Strategy audits** | Review simulation realism, risk management, and live-readiness |
| **Licensed strategies** | Production-ready systems under separate license terms — **backtested, live-tested, and run with profitable results** (not the demo examples in this repo) |

Commercial services and licensed strategies are **not** included in the MIT license. Example code remains demonstration-only.

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

Opens `http://127.0.0.1:8350` — run backtests, browse report folders, open HTML summaries, and inspect **trade history** per run (**Details & history**). The **Live Trading** tab includes a strategy picker and a live uptime counter that updates automatically. Strategies are still authored in Python.

Live trading requires an explicit `--variant` (CLI and Web UI).

### Custom benchmark

```bash
python run_custom_benchmark.py --variants example_ema_cross,example_supertrend --start 2026-03-01 --end 2026-06-01
python run_custom_benchmark.py --variants example_volume_profile --multi-period --name my_test --export-trades
```

`--export-trades` writes `trades.json` in the run folder (also configurable in Web UI Settings).

### All example strategies at once

```bash
python run_examples.py --export-trades
```

Generates multi-period HTML reports under `reports/runs/` plus `trades.json` for the Web UI trade-history view. Sample reports for the shipped examples are committed there for reference; regenerate with the command above when you change strategies or simulation settings.

---

## Agent knowledge & plugin (optional)

HydraTrade ships **portable agent knowledge** — markdown plus a thin CLI — that works with **any** coding assistant, not only Cursor. Use it as project rules, a system prompt, or via terminal commands.

| Install target | Status |
|----------------|--------|
| **Cursor** | ✅ `python agent/plugin/install_cursor.py` → `.cursor/skills/` + slash-commands (`/hydra-bt`, `/hydra-validate`, …) |
| **Claude Code** (VS Code / CLI) | ✅ `python agent/plugin/install_claude.py` → `.claude/skills/` |
| **Windsurf**, **GitHub Copilot**, **Cline**, **Continue** | 🔜 Roadmap |

```bash
python agent/plugin/install_cursor.py           # Cursor       -> .cursor/skills/
python agent/plugin/install_claude.py           # Claude Code  -> .claude/skills/
python agent/plugin/install.py --target both    # both at once
#   add --private to install your filled Part 2 (agent/private/, gitignored)
```

The agent can also **trade** through the plugin, not just test:
```bash
python agent/plugin/hydra.py live status                      # account / positions / pendings
python agent/plugin/hydra.py live start --variant example_ema_cross --yes   # example only — use your own variant live
python agent/plugin/hydra.py order buy --volume 0.10 --sl 3300 --tp 3400 --yes  # discretionary order
python agent/plugin/hydra.py order modify_position --ticket 123456 --sl 3280 --yes  # change SL/TP on open position
```

- **Part 1** — general day-trading knowledge (shared, framework-safe).
- **Part 2** — **your** strategy notes; the public repo ships an English **template** — copy and fill locally (`agent/private/`).

Full guide: **[agent/README.md](agent/README.md)**

---

## Example strategies

| ID | Name | Demonstrates |
|---|---|---|
| `example_ema_cross` | EMA Cross | Market entries on H1 EMA cross (`TradeAction.ACTION`), SL/TP only |
| `example_supertrend` | SuperTrend | Stop entries on H1 trend flips (`BUY_STOP` / `SELL_STOP`) |
| `example_volume_profile` | Volume Profile | Limit entries at session POC with trend filter (`BUY_LIMIT` / `SELL_LIMIT`) |

These are **intentionally modest demos** — tuned for small size and low frequency, with results typically **near breakeven or slightly negative**. That is by design: they teach the **Strategy interface** and framework behaviour, not a profitable edge. We do not ship profitable logic as copy-paste examples when others may use it commercially.

Source code lives in `strategie/examples/`. Each file has a header explaining what it demonstrates.

---

## Writing your own strategy

This is the **primary way to extend HydraTrade today**.

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

Position sizing goes through the built-in **RiskManager** (grade-based lot calculation from equity, stop distance, and symbol info). Examples use conservative demo risk; your strategies set grades and parameters in code.

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

### Indicator library

Reusable tools live in `strategie/tools/` (one indicator per file — e.g. `ema.py`, `adx.py`, `ATR.py`, `marketPhase.py`, `vwap.py`, volume profile helpers). List everything:

```bash
python agent/plugin/hydra.py catalog
```

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
│   ├── Strategy.py # Abstract base class (Strategy interface)
│   ├── registry.py # Strategy catalog
│   ├── examples/   # Shipped example strategies (demos only)
│   └── tools/      # Indicators (EMA, ATR, SuperTrend, Volume Profile, …)
├── analysis/       # Reports, benchmarks, multi-period tests
├── agent/          # Agent knowledge + plugin CLI (optional)
├── webui/          # Local control center (run & monitor)
├── reports/runs/   # Generated HTML/JSON reports
├── main.py         # CLI simulation entry
├── run_live.py     # CLI live entry (requires --variant)
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

Live trading sends **real orders** to your MT5 account. The Web UI requires typing `LIVE` to confirm. Example strategies use conservative demo sizing via the **RiskManager** but remain **demonstration code only**.

When stopping a live job, open positions and pending orders **remain in MT5** and are no longer managed by the framework.

---

## Roadmap

Planned work is split into **near-term** (current focus) and **long-term direction**. Order within each group may change; near-term items ship before platform-scale features.

### Near-term

- **Multi-symbol support** — run strategies across multiple symbols in one session: shared portfolio view, per-symbol configuration, and reports that compare or aggregate results across instruments (not only a single `symbol` in config).
- **Copy trading & multi-account workflows** — route signals or mirrored execution across accounts; foundation for managed / multi-client setups.
- **MT5 auto-login** — automatic terminal login from secure local config or environment variables, so startup does not depend on manually opening MT5 and clicking through the login dialog. Terminal must still be installed.
- **Broker API integration (MT5-optional)** — pluggable execution and data layer for direct broker or market-data APIs where available (historical and live data; order placement for live trading). Simulation and live paths would keep the same Strategy interface; MT5 remains the default path.
- **Buy & hold benchmark** — automated comparison baseline in validation reports.

### Shipped recently

- Indicator library (`strategie/tools/`, one file per indicator)
- Web UI trade history export and **Details & history** view
- Live Trading tab: strategy picker and auto-updating uptime while a job runs
- Expandable grade-split rows in HTML reports
- Explicit variant selection for live trading
- Agent plugin: Cursor **and Claude Code (VS Code)** skill install (`install_cursor.py` / `install_claude.py`)
- Agent can trade via the plugin — `hydra.py live status|start` and `hydra.py order …` (real orders, `--yes` gated)

### Long-term direction

- **Strategy studio** — visual / UI-assisted strategy building on top of the framework
- **Deeper AI-assisted workflows** — extended agents, skills, and tooling beyond the current plugin
- **Machine learning** — integrated training and evaluation pipelines where they fit the architecture
- **Broader platform features** — additional product surface beyond today’s CLI + control center

---

## License

[MIT License](LICENSE) — Copyright (c) 2026 HydraLabs.

You may use, copy, modify, merge, publish, distribute, sublicense, and sell copies of the software, provided the copyright notice and permission notice are included in all copies or substantial portions.

**Professional services and commercially licensed strategies** are offered separately and are not part of this repository’s MIT license. See [Professional services](#professional-services).
