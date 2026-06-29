# Private agent files (local)

| Layer | File | In git? |
|-------|------|---------|
| Part 1 + Part 2 **template** | `../DAYTRADER_AGENT_SKILL.public.md` | Yes |
| Part 2 **filled in** | `DAYTRADER_AGENT_SKILL.md` | **No** (gitignored) |

## Setup

```bash
cp agent/DAYTRADER_AGENT_SKILL.public.md agent/private/DAYTRADER_AGENT_SKILL.md
# Replace Part 2 placeholders with your strategy notes
python agent/plugin/install.py --private
```

When the framework updates Part 1: merge **only Part 1** from `.public.md` into your private file; keep your Part 2 unchanged.

## Install

```bash
python agent/plugin/install.py              # public file
python agent/plugin/install.py --private    # your private/DAYTRADER_AGENT_SKILL.md
```
