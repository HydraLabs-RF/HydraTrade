---
name: hydra-validate
description: OOS validation report for HydraTrade strategies (floor, consistency, drawdown).
disable-model-invocation: true
---

# Validate (`/validate`)

```bash
python agent/plugin/hydra.py validate --variants <variant_id> --export-trades
```

Or on an existing run:

```bash
python agent/plugin/hydra.py validate --run reports/runs/<folder>
```

Return `VALIDATION_REPORT=` path. Note: Buy & Hold comparison is not in the framework yet.
