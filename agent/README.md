# HydraTrade — Agent knowledge & plugin

Portable **agent knowledge** for HydraTrade — works with any coding assistant, not just one IDE.

## Two files

| File | In git? | Content |
|------|---------|---------|
| `DAYTRADER_AGENT_SKILL.public.md` | **Yes** | Part 1 (trading knowledge) + Part 2 **template** |
| `private/DAYTRADER_AGENT_SKILL.md` | **No** | Your copy with Part 2 **filled in** (local only) |

All public skill content is in **English**.

## Universal vs IDE-specific

| Layer | Works everywhere |
|-------|------------------|
| Skill markdown | ✅ Any assistant — project rules, system prompt, docs |
| `agent/plugin/hydra.py` CLI | ✅ Terminal, scripts, any agent with shell |

| IDE install | Status |
|-------------|--------|
| **Cursor** | ✅ `python agent/plugin/install_cursor.py` → `.cursor/skills/` + slash-commands |
| **Claude Code** (VS Code / CLI) | ✅ `python agent/plugin/install_claude.py` → `.claude/skills/` |
| **Windsurf**, **GitHub Copilot**, **Cline**, **Continue** | 🔜 Roadmap |

## Install

```bash
python agent/plugin/install_cursor.py           # Cursor      -> .cursor/skills/
python agent/plugin/install_claude.py           # Claude Code -> .claude/skills/
python agent/plugin/install.py --target both    # both at once
#   add --private to use your filled agent/private/DAYTRADER_AGENT_SKILL.md (Part 2)
```

**Customize:** copy `.public.md` → `private/DAYTRADER_AGENT_SKILL.md`, fill Part 2, install with `--private`.

## Skills

**Research:** `hydra-bt`, `hydra-validate`, `hydra-ftmo`, `hydra-phasemap`, `hydra-sanity`,
`hydra-catalog`, `hydra-newstrategy`, `hydra-newindicator`

**Live trading:** `hydra-live` (monitor / start a strategy live), `hydra-order` (discretionary
market, pending, **modify** SL/TP or pending price, close, cancel). Trading skills are
`disable-model-invocation` — they run only when you ask; real MT5 actions need `--yes`.

See [private/README.md](private/README.md) · [plugin/README.md](plugin/README.md)
