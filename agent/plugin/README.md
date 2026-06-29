# HydraTrade Agent Plugin

Thin CLI + IDE skills that wrap existing framework entry points. The plugin does **not**
implement trading logic — it orchestrates backtests, reports, and scaffolds.

**Cursor** install is available today; **Claude Code for VS Code** one-click install is coming soon.
See [Agent knowledge & plugin](../README.md).

## Install into Cursor

From the repository root:

```bash
python agent/plugin/install.py
```

With your private strategy notes (optional):

```bash
cp agent/DAYTRADER_AGENT_SKILL.public.md agent/private/DAYTRADER_AGENT_SKILL.md
# edit Part 2 in the private file
python agent/plugin/install.py --private
```

This copies skills into `.cursor/skills/` on your machine (local IDE config, not committed).

## CLI reference

| Skill command | CLI | Output |
|---------------|-----|--------|
| Backtest | `python agent/plugin/hydra.py bt --variants id --multi-period --export-trades` | `reports/runs/.../multi_period_summary.html` |
| Validate | `python agent/plugin/hydra.py validate --variants id` | `validation_report.html` |
| FTMO check | `python agent/plugin/hydra.py ftmo --run reports/runs/...` | `ftmo_report.html` |
| Phase map | `python agent/plugin/hydra.py phasemap --start YYYY-MM-DD --end YYYY-MM-DD` | `phasemap.html` |
| Sanity | `python agent/plugin/hydra.py sanity --variant id --start … --end …` | `sanity_check.txt` |
| New strategy | `python agent/plugin/hydra.py newstrategy "Name"` | `strategie/variants/...` |
| New indicator | `python agent/plugin/hydra.py newindicator "Name"` | `strategie/tools/...` |
| Catalog | `python agent/plugin/hydra.py catalog` | stdout |

Commands print `REPORT_DIR=`, `VALIDATION_REPORT=`, etc. — pass those paths to the user.

## Public vs. private skill content

| Install | Skill source |
|---------|----------------|
| `install.py` | `DAYTRADER_AGENT_SKILL.public.md` (Part 1 + Part 2 template) |
| `install.py --private` | `private/DAYTRADER_AGENT_SKILL.md` (your Part 2) |

Slash-command skills (`hydra-bt`, `hydra-validate`, …) are always installed; they only tell
the agent which CLI to run.

Technical spec: [PLUGIN_SPEC.md](../PLUGIN_SPEC.md)
