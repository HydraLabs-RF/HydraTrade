# HydraTrade Agent Plugin

Thin CLI + IDE skills that wrap existing framework entry points. The plugin does **not**
implement trading logic — it orchestrates backtests, reports, scaffolds, and (when you ask)
live trading via the framework.

See [Agent knowledge & plugin](../README.md).

## Install

**Cursor** and **Claude Code (VS Code / CLI)** use the same `SKILL.md` format:

```bash
python agent/plugin/install_cursor.py           # Cursor       -> .cursor/skills/
python agent/plugin/install_claude.py           # Claude Code  -> .claude/skills/
python agent/plugin/install.py --target both    # both at once
#   add --private for your filled agent/private/DAYTRADER_AGENT_SKILL.md (Part 2, local)
```

Optional — your private strategy notes (Part 2, gitignored):

```bash
cp agent/DAYTRADER_AGENT_SKILL.public.md agent/private/DAYTRADER_AGENT_SKILL.md
# edit Part 2 in the private file
python agent/plugin/install_cursor.py --private   # or install_claude.py / install.py --target both --private
```

Skills are copied into local IDE config (`.cursor/skills/` or `.claude/skills/`) — not committed.
After installing for Claude Code, restart Claude Code or run `/doctor`.

## CLI reference

### Research & scaffolding

| Skill | CLI | Output |
|-------|-----|--------|
| Backtest | `python agent/plugin/hydra.py bt --variants id --multi-period --export-trades` | `reports/runs/.../multi_period_summary.html` |
| Validate | `python agent/plugin/hydra.py validate --variants id` | `validation_report.html` |
| FTMO check | `python agent/plugin/hydra.py ftmo --run reports/runs/...` | `ftmo_report.html` |
| Phase map | `python agent/plugin/hydra.py phasemap --start YYYY-MM-DD --end YYYY-MM-DD` | `phasemap.html` |
| Sanity | `python agent/plugin/hydra.py sanity --variant id --start … --end …` | `sanity_check.txt` |
| New strategy | `python agent/plugin/hydra.py newstrategy "Name"` | `strategie/variants/...` |
| New indicator | `python agent/plugin/hydra.py newindicator "Name"` | `strategie/tools/...` |
| Catalog | `python agent/plugin/hydra.py catalog` | stdout |

### Live trading (real MT5 orders)

| Skill | CLI | Notes |
|-------|-----|-------|
| Live status | `python agent/plugin/hydra.py live status` | Read-only — account, positions, pendings |
| Live start | `python agent/plugin/hydra.py live start --variant id --yes` | Launches `run_live.py`; refuses example strategies |
| Market order | `python agent/plugin/hydra.py order buy\|sell --volume … [--sl][--tp] --yes` | Discretionary single order |
| Pending order | `python agent/plugin/hydra.py order buy_limit\|sell_limit\|buy_stop\|sell_stop --price … --volume … --yes` | Requires `--price` |
| Close position | `python agent/plugin/hydra.py order close --ticket … --yes` | |
| Cancel pending | `python agent/plugin/hydra.py order cancel --ticket … --yes` | |
| Modify position SL/TP | `python agent/plugin/hydra.py order modify_position --ticket … --sl … [--tp …] --yes` | Open position |
| Modify pending | `python agent/plugin/hydra.py order modify_pending --ticket … [--price …] [--sl …] [--tp …] --yes` | Pending order |

`live start` and all `order` actions that send or change orders require `--yes` (otherwise dry-run
preview only). Trading skills (`hydra-live`, `hydra-order`) are `disable-model-invocation` — they run only when
you explicitly ask.

Commands print `REPORT_DIR=`, `VALIDATION_REPORT=`, etc. — pass those paths to the user.

## Public vs. private skill content

| Install | Skill source |
|---------|----------------|
| default | `DAYTRADER_AGENT_SKILL.public.md` (Part 1 + Part 2 template) |
| `--private` | `private/DAYTRADER_AGENT_SKILL.md` (your filled Part 2) |

Slash-command skills (`hydra-bt`, `hydra-validate`, `hydra-live`, …) are always installed; they
tell the agent which CLI to run.

Technical spec: [PLUGIN_SPEC.md](../PLUGIN_SPEC.md)
