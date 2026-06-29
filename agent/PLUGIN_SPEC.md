# HydraTrade Plugin — technical spec

## Purpose

Bundle **agent knowledge** + workflow commands so an AI can research and operate HydraTrade
productively. Trading logic stays in the framework; the plugin orchestrates existing entry points.

## Components

1. **Skill** = `DAYTRADER_AGENT_SKILL.public.md` (Part 1 public, Part 2 template) and optional
   `agent/private/DAYTRADER_AGENT_SKILL.md` (filled Part 2, local).
2. **CLI** = `agent/plugin/hydra.py` — works with any assistant.
3. **IDE installs**
   - **Cursor** — `install.py` → `.cursor/skills/` (available)
   - **Claude Code for VS Code** — plugin packaging (planned next)
   - **Windsurf, GitHub Copilot, Cline, Continue** — roadmap

## Commands (CLI / slash-skills)

| Command | Role | Framework |
|---|---|---|
| `/bt` | Multi-period backtest + HTML reports | `multiPeriod`, `htmlReport`, `runManager` |
| `/validate` | OOS validation report | `multiPeriod` aggregate |
| `/ftmo` | Prop PASS/FAIL | prop metrics in reports |
| `/phasemap` | Market phase report | `marketPhase.py` |
| `/sanity` | Per-trade sanity check | `run_sanity_check.py` |
| `/newstrategy` | Strategy scaffold | `Strategy` base |
| `/newindicator` | Indicator scaffold | `strategie/tools/` |
| `/catalog` | List tools & variants | `registry`, `tools/` |

Entry point: `python agent/plugin/hydra.py <command> …`

## Requirements

- Test commands produce viewable reports; return paths.
- Standard windows from config, not hardcoded per command.
- Symbol/settings from `configConnection`.
- Commands stay thin — no trading logic in the plugin.
