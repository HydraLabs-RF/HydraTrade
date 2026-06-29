---
name: hydra-newstrategy
description: Scaffold a new HydraTrade strategy file under strategie/variants/.
disable-model-invocation: true
---

# New strategy (`/newstrategy`)

```bash
python agent/plugin/hydra.py newstrategy "My Strategy Name"
```

Then:
1. Implement `planTradeGrade_A`, `adjustPendingTradeGrade_A`, `manageActiveTradeGrade_A`
2. Register `VariantSpec` in `strategie/registry.py`
3. Run `hydra-sanity` then `hydra-bt`

One strategy = one file. Follow `strategie/examples/base.py` patterns.
