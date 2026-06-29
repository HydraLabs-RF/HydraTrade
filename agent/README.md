# HydraTrade — Agent knowledge & plugin

Portable **agent knowledge** for HydraTrade — works with any coding assistant, not just one IDE.

## Two files

| File | In git? | Content |
|------|---------|---------|
| `DAYTRADER_AGENT_SKILL.public.md` | **Yes** | Part 1 (trading knowledge) + Part 2 **template** |
| `private/DAYTRADER_AGENT_SKILL.md` | **No** | Your copy with Part 2 **filled in** |

All public skill content is in **English**.

## Universal vs IDE-specific

| Layer | Works everywhere |
|-------|------------------|
| Skill markdown | ✅ Any assistant — project rules, system prompt, docs |
| `agent/plugin/hydra.py` CLI | ✅ Terminal, scripts, any agent with shell |

| IDE install | Status |
|-------------|--------|
| **Cursor** | ✅ `python agent/plugin/install.py` → `.cursor/skills/` + slash-commands |
| **Claude Code** (VS Code) | 🔜 One-click plugin install — **coming soon** |
| **Windsurf**, **GitHub Copilot**, **Cline**, **Continue** | 🔜 Roadmap |

## Install (Cursor)

```bash
python agent/plugin/install.py              # public skill (Part 2 template included)
python agent/plugin/install.py --private    # your private/DAYTRADER_AGENT_SKILL.md
```

**Customize:** copy `.public.md` → `private/DAYTRADER_AGENT_SKILL.md`, fill Part 2, install with `--private`.

See [private/README.md](private/README.md) · [plugin/README.md](plugin/README.md)
