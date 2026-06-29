# HydraTrade — Agent & Cursor skills

HydraTrade ships an **optional agent plugin** for [Cursor](https://cursor.com): a day-trading
knowledge skill plus slash-commands that run backtests, validation, and scaffolds through the
existing Python CLI.

Nothing here replaces the framework — it gives an AI assistant the context and shortcuts to
work productively in this repository.

## What you get

| Component | Purpose |
|-----------|---------|
| **Day-trader skill** (`hydratrade-daytrader`) | Broad trading + research knowledge (TEIL 1) and optional your own notes (TEIL 2) |
| **Command skills** (`hydra-bt`, `hydra-validate`, …) | Explicit `/` shortcuts that run `agent/plugin/hydra.py` |
| **CLI** (`agent/plugin/hydra.py`) | Backtest, validate, FTMO check, phase map, sanity, scaffolds, catalog |

Command skills are intentionally **thin** (how to invoke the CLI). The day-trader skill is
**thick** (how to think about edges, regimes, validation, and framework hooks).

## Requirements

- Cursor IDE with agent / skills support
- HydraTrade cloned and Python dependencies installed (see root [README](../README.md))
- MT5 for commands that run simulations

## Install

From the repository root:

```bash
python agent/plugin/install.py
```

Skills are copied to `.cursor/skills/` (local to your machine). Re-run after updating the repo
or editing skill sources.

### Optional: private strategy knowledge

To attach **your** tested edges, configs, and lessons (not shipped with examples):

```bash
cp agent/private/STRATEGY_KNOWLEDGE.md.example agent/private/STRATEGY_KNOWLEDGE.md
# edit agent/private/STRATEGY_KNOWLEDGE.md
python agent/plugin/install.py --private
```

`STRATEGY_KNOWLEDGE.md` is gitignored by default so it stays on your machine.

## Usage in Cursor

1. Open this repository in Cursor.
2. Start a new **Agent** chat (skills load per project).
3. Either:
   - Type **`/hydra-bt`** (or `/hydra-validate`, `/hydra-sanity`, …) for a fixed workflow, or
   - Ask naturally: *“Run a multi-period backtest on example_volume_profile and show report paths.”*

The agent should run CLI commands from the repo root and return report paths under
`reports/runs/`.

### Slash-commands (after install)

| Type in chat | Action |
|--------------|--------|
| `/hydra-bt` | Multi-period backtest via CLI |
| `/hydra-validate` | OOS validation report |
| `/hydra-ftmo` | Prop-style PASS/FAIL from a run folder |
| `/hydra-phasemap` | Market phase classification report |
| `/hydra-sanity` | Per-trade sanity check |
| `/hydra-newstrategy` | Scaffold `strategie/variants/` file |
| `/hydra-newindicator` | Scaffold `strategie/tools/` file |
| `/hydra-catalog` | List timeframes, tools, registered variants |

Exact prompts live in `agent/plugin/skills/hydra-*/SKILL.md`.

### Web UI

Reports appear under `reports/runs/`. You can also use `python run_webui.py` → **Runs &
Reports** → **Details & history** for the trade list (`trades.json`).

## Repository layout

```
agent/
├── README.md                      ← this file
├── DAYTRADER_AGENT_SKILL.md       ← TEIL 1 source (public knowledge)
├── PLUGIN_SPEC.md                 ← contributor spec for the plugin
├── private/
│   ├── README.md
│   ├── STRATEGY_KNOWLEDGE.md.example
│   └── STRATEGY_KNOWLEDGE.md      ← your file (gitignored)
└── plugin/
    ├── hydra.py                   ← CLI
    ├── install.py                 ← copy skills into .cursor/
    ├── README.md
    └── skills/                    ← command skill templates
```

## Public vs. private content

| Content | In git? | In default install? |
|---------|---------|---------------------|
| TEIL 1 (`DAYTRADER_AGENT_SKILL.md`) | Yes | Yes |
| TEIL 2 template (`private/*.example`, section in skill file) | Yes | No (pointer only) |
| Your `private/STRATEGY_KNOWLEDGE.md` | No (gitignored) | Only with `--private` |
| `.cursor/skills/` after install | No (local IDE) | — |

## Further reading

- [Plugin CLI details](plugin/README.md)
- [PLUGIN_SPEC.md](PLUGIN_SPEC.md) — design constraints for contributors
