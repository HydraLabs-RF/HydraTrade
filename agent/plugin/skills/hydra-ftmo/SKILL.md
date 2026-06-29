---
name: hydra-ftmo
description: FTMO prop firm PASS/FAIL check from a multi-period run.
disable-model-invocation: true
---

# FTMO check (`/ftmo`)

After a multi-period backtest:

```bash
python agent/plugin/hydra.py ftmo --run reports/runs/<folder>
```

Or latest run (omit `--run`). Return `FTMO_REPORT=` HTML path.

Criteria: all windows profitable, worst DD &lt; 10%, worst daily DD &lt; 5%, `all_prop_ok`.
