# HydraTrade Plugin — technical spec

## Purpose

Bundle **agent knowledge** + workflow commands so an AI can research, operate, and (when the user
asks) trade on HydraTrade. Trading logic stays in the framework; the plugin orchestrates existing
entry points.

## Components

1. **Skill** = `DAYTRADER_AGENT_SKILL.public.md` (Part 1 public, Part 2 template) and optional
   `agent/private/DAYTRADER_AGENT_SKILL.md` (filled Part 2, local).
2. **CLI** = `agent/plugin/hydra.py` — works with any assistant that can run shell commands.
3. **IDE installs** (same skill folders, different target paths)
   - **Cursor** — `install_cursor.py` or `install.py --target cursor` → `.cursor/skills/`
   - **Claude Code (VS Code / CLI)** — `install_claude.py` or `install.py --target claude` → `.claude/skills/`
   - **Both** — `install.py --target both`
   - **Windsurf, GitHub Copilot, Cline, Continue** — roadmap

## Commands (CLI / slash-skills)

### Research & scaffolding

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

### Live trading (real MT5)

| Command | Role | Framework |
|---|---|---|
| `/live status` | Read-only account / positions / pendings | `MT5CExecution`, MT5 API |
| `/live start` | Launch live strategy loop (`--yes`) | `run_live.py` |
| `/order` | Discretionary order: market, pending, modify SL/TP or pending, close, cancel (`--yes`) | `MT5CExecution` |

Not covered by `/order`: multi-bar trailing logic or regime-based management — use a live strategy for that.

`live start` and `order` require `--yes` for real orders. Example strategies are refused for
live start. Trading skills use `disable-model-invocation: true`.

Entry point: `python agent/plugin/hydra.py <command> …`

## Requirements

- Test commands produce viewable reports; return paths.
- Standard windows from config, not hardcoded per command.
- Symbol/settings from `configConnection`.
- Commands stay thin — no trading logic in the plugin.
- Live/order commands gate on explicit user confirmation (`--yes`).
