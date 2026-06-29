# Private strategy knowledge (optional, local)

This folder is for **your own** strategy research — edges you tested, parameters that worked,
lessons learned. It is **not required** for HydraTrade and is **not** shipped with example
strategies.

## Setup

1. Copy the template:
   ```bash
   cp agent/private/STRATEGY_KNOWLEDGE.md.example agent/private/STRATEGY_KNOWLEDGE.md
   ```
2. Fill in `STRATEGY_KNOWLEDGE.md` with your notes (variant IDs, bake-offs, configs, reports).
3. Install skills with the private section included:
   ```bash
   python agent/plugin/install.py --private
   ```

`STRATEGY_KNOWLEDGE.md` is listed in `.gitignore` — it stays on your machine unless you
choose to commit it.

## Public vs. private install

| Command | Cursor skill contains |
|---------|------------------------|
| `python agent/plugin/install.py` | TEIL 1 only (general day-trading knowledge) |
| `python agent/plugin/install.py --private` | TEIL 1 + your `STRATEGY_KNOWLEDGE.md` |

TEIL 1 lives in `agent/DAYTRADER_AGENT_SKILL.md` and is safe to share. TEIL 2 is whatever
you write here.
