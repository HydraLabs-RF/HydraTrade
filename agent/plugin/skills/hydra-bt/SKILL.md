---
name: hydra-bt
description: Run a HydraTrade multi-period backtest and return report paths.
disable-model-invocation: true
---

# Backtest (`/bt`)

Run from repo root:

```bash
python agent/plugin/hydra.py bt --variants <variant_id> --multi-period --export-trades --name <run_name>
```

- Comma-separate multiple variants: `--variants a,b,c`
- Always use `--multi-period` unless the user asked for one custom window (then `--start` / `--end`)
- Read `REPORT_DIR=` and `SUMMARY_HTML=` from stdout and give the user the HTML path
- Mention Web UI: **Details & history** for trade list (`trades.json`)

Do not reimplement simulation — only call `hydra.py`.
