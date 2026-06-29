---
name: hydra-phasemap
description: Market phase classification report (trend / flat / whipsaw) for routing edges.
disable-model-invocation: true
---

# Phase map (`/phasemap`)

```bash
python agent/plugin/hydra.py phasemap --start YYYY-MM-DD --end YYYY-MM-DD
```

Uses `MarketPhaseClassifier` on D1 bars. Return `PHASEMAP_REPORT=` path.
Use for routing: trend edges in TREND_*, fades in FLAT_RANGE, avoid fades in WHIPSAW.
