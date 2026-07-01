---
name: hydra-live
description: Start and monitor LIVE trading (real MT5 orders). Use to run a validated strategy live and to check the live account.
disable-model-invocation: true
---

# Live trading (`/live`)

> ⚠️ **Real money.** `live start` sends real orders to the connected MT5 account. Never run it
> for an example strategy, and never without the user's explicit go-ahead. This skill is
> `disable-model-invocation` on purpose — only run it when the user asks.

## Monitor (read-only, safe)

```bash
python agent/plugin/hydra.py live status
```

Prints account balance/equity, open positions (side, volume, entry, SL/TP, PnL) and pending
orders. Use it before starting, and to watch a running strategy.

## Start (real orders)

```bash
python agent/plugin/hydra.py live start --variant <variant_id>          # dry run: prints what would start
python agent/plugin/hydra.py live start --variant <variant_id> --yes    # actually launches the live engine
```

Rules the command enforces:
- `--variant` is **required** and must be a **registered, non-example** variant (example strategies
  are refused — they are demos).
- Without `--yes` it only prints a dry-run summary; `--yes` actually starts.
- It launches the framework live loop (`run_live.py`), which runs until stopped.

## Before going live — checklist
1. `hydra.py bt --variants <id> --multi-period` → then `hydra.py validate` and `hydra.py ftmo` PASS.
2. `hydra.py sanity --variant <id> ...` → trades look plausible.
3. `hydra.py live status` → account/positions as expected, MT5 connected, symbol visible.
4. Confirm the **variant, symbol and risk** with the user, then `live start --variant <id> --yes`.

## Watch the first bars
In the live log you should see `Live strategy: … [<variant_id>]` and orders being **placed**
(`Pending placed …` / a market ticket). If you see `Signal not executed`, stop and check the log
(order rejection, filling mode, disabled symbol, volume/stop limits).

## Stopping
The live loop runs until interrupted (Ctrl+C / stop the process, or the Web UI stop button).
**Stopping does NOT close open positions or pending orders** — they stay in MT5 and are no longer
managed. Flatten manually in MT5 / the Web UI if you want to be flat.
