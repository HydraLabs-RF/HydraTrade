# HydraTrade Agent Plugin

Thin CLI + Cursor skills that wrap existing framework entry points. The plugin does **not**
implement trading logic — it orchestrates backtests, reports, and scaffolds.

See also: [Agent & Cursor skills](../README.md) (overview for users).

## Install into Cursor

From the repository root:

```bash
python agent/plugin/install.py
```

With your private strategy notes (optional):

```bash
cp agent/private/STRATEGY_KNOWLEDGE.md.example agent/private/STRATEGY_KNOWLEDGE.md
# edit STRATEGY_KNOWLEDGE.md
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

| Install | Day-trader skill contains |
|---------|---------------------------|
| `install.py` | TEIL 1 — general knowledge in `DAYTRADER_AGENT_SKILL.md` |
| `install.py --private` | TEIL 1 + `agent/private/STRATEGY_KNOWLEDGE.md` |

Slash-command skills (`hydra-bt`, `hydra-validate`, …) are always installed; they only tell
the agent which CLI to run.

Technical spec: [PLUGIN_SPEC.md](../PLUGIN_SPEC.md)
