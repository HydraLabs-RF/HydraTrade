---
name: hydra-order
description: Place and manage discretionary MT5 orders (real money). Market, pending, modify SL/TP or pending price, close, cancel — without a coded strategy.
disable-model-invocation: true
---

# Discretionary order (`/order`)

> ⚠️ **Real money, no strategy.** Single orders the agent decides on. Every change needs `--yes`;
> without it you get a dry-run preview. Never send real orders without the user's explicit go-ahead.
> `disable-model-invocation` on purpose.

## Market entry
```bash
python agent/plugin/hydra.py order buy  --volume 0.10 [--sl 3300] [--tp 3400] --yes
python agent/plugin/hydra.py order sell --volume 0.10 [--sl 3400] [--tp 3300] --yes
```

## Pending entry (limit / stop)
```bash
python agent/plugin/hydra.py order sell_limit --price 3390 --volume 0.10 [--sl][--tp] --yes
python agent/plugin/hydra.py order buy_stop   --price 3405 --volume 0.10 [--sl][--tp] --yes
```
`*_limit` = better price, `*_stop` = breakout price. Pending orders require `--price`.

## Modify (open position or pending)
```bash
python agent/plugin/hydra.py order modify_position --ticket 123456 --sl 3280 [--tp 3400] --yes
python agent/plugin/hydra.py order modify_pending  --ticket 123457 --price 3385 [--sl][--tp] --yes
```
- **`modify_position`** — change SL and/or TP on an **open** position (`--ticket` from `live status`).
- **`modify_pending`** — change entry price and/or SL/TP on a **pending** order (omit `--price` to keep current entry).

## Close / cancel
```bash
python agent/plugin/hydra.py order close  --ticket 123456 --yes   # close open position
python agent/plugin/hydra.py order cancel --ticket 123457 --yes   # remove pending
python agent/plugin/hydra.py live status                          # tickets, PnL, pendings
```

## Agent workflow
1. `hydra.py live status` — account, positions, pendings.
2. `hydra.py phasemap --start … --end …` — regime (optional bias).
3. Plan direction, entry, stop, target, size. Dry-run first (no `--yes`).
4. Confirm with the user, then re-run with `--yes`.
5. Monitor with `live status`; adjust with `modify_*`, exit with `close` / `cancel`.

Notes: symbol from `configConnection`. Volume in lots — no auto risk-sizing on this path. Wrong
market fill mode is retried automatically (retcode 10030).
