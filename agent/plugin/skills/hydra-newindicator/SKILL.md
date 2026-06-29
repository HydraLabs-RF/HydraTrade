---
name: hydra-newindicator
description: Scaffold a new indicator tool under strategie/tools/ (one file per indicator).
disable-model-invocation: true
---

# New indicator (`/newindicator`)

```bash
python agent/plugin/hydra.py newindicator "My Indicator"
```

Style: `strategie/tools/ATR.py` — Indicator class + Result dataclass, `calculate_by_time` + `calculate`.
Never add indicators inline in a strategy or in a shared `indicators.py`.

Run `python agent/plugin/hydra.py catalog` to list existing tools.
