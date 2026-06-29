---
name: hydra-sanity
description: Per-trade sanity check before trusting a strategy or going live.
disable-model-invocation: true
---

# Sanity check (`/sanity`)

```bash
python agent/plugin/hydra.py sanity --variant <variant_id> --start YYYY-MM-DD --end YYYY-MM-DD
```

Return `SANITY_REPORT=` path. Run this after implementing a new strategy and before live.
