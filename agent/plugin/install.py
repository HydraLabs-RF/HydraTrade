#!/usr/bin/env python3
"""Install HydraTrade agent plugin skills into a coding-assistant skills folder.

Both Cursor and Claude Code use the same SKILL.md format (name/description frontmatter),
so installing is just copying the skill folders into the right place:

    python agent/plugin/install.py                     # Cursor  -> .cursor/skills/
    python agent/plugin/install.py --target claude     # Claude Code (VS Code / CLI) -> .claude/skills/
    python agent/plugin/install.py --target both       # both
    python agent/plugin/install.py --private           # use your filled private skill (Part 2)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = Path(__file__).resolve().parent
SKILLS_SRC = PLUGIN / "skills"
PUBLIC_SKILL = ROOT / "agent" / "DAYTRADER_AGENT_SKILL.public.md"
PRIVATE_SKILL = ROOT / "agent" / "private" / "DAYTRADER_AGENT_SKILL.md"
PRIVATE_EXAMPLE = ROOT / "agent" / "private" / "DAYTRADER_AGENT_SKILL.md.example"

# target -> skills directory (relative to repo root)
TARGET_DIRS = {"cursor": ".cursor/skills", "claude": ".claude/skills"}


def _skill_body(private: bool) -> str:
    if private:
        if PRIVATE_SKILL.is_file():
            return PRIVATE_SKILL.read_text(encoding="utf-8").strip()
        print(
            "ERROR: agent/private/DAYTRADER_AGENT_SKILL.md not found.\n"
            f"  Copy {PRIVATE_EXAMPLE.name} or DAYTRADER_AGENT_SKILL.public.md → private/DAYTRADER_AGENT_SKILL.md",
            file=sys.stderr,
        )
        sys.exit(1)
    return PUBLIC_SKILL.read_text(encoding="utf-8").strip()


def _write_daytrader_skill(dest_root: Path, private: bool) -> None:
    dest = dest_root / "hydratrade-daytrader"
    dest.mkdir(parents=True, exist_ok=True)
    body = _skill_body(private)
    content = f"""---
name: hydratrade-daytrader
description: >-
  HydraTrade day-trading — strategy design, indicators, regime thinking, backtest validation,
  prop rules, live trading, and framework workflows. Use when building, testing, or running
  strategies in this repo.
---

{body}
"""
    (dest / "SKILL.md").write_text(content, encoding="utf-8")
    print(f"  hydratrade-daytrader -> {dest / 'SKILL.md'}")


def install_target(target: str, private: bool) -> None:
    dest_root = ROOT / Path(TARGET_DIRS[target])
    dest_root.mkdir(parents=True, exist_ok=True)
    print(f"Installing to {dest_root} (target={target}, private={private})")
    _write_daytrader_skill(dest_root, private)
    for src in sorted(SKILLS_SRC.glob("hydra-*")):
        if not src.is_dir():
            continue
        dest = dest_root / src.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        print(f"  {src.name} -> {dest}")
    hint = "Open a new agent chat in Cursor" if target == "cursor" else "Restart Claude Code (or run /doctor)"
    print(f"Done ({target}). {hint} to pick up the skills.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install HydraTrade agent skills.")
    parser.add_argument(
        "--target",
        choices=["cursor", "claude", "both"],
        default="cursor",
        help="Where to install: cursor (.cursor/skills), claude (.claude/skills), or both",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Use agent/private/DAYTRADER_AGENT_SKILL.md (full skill with your Part 2, local only)",
    )
    args = parser.parse_args()
    if not PUBLIC_SKILL.is_file():
        print(f"ERROR: missing {PUBLIC_SKILL}", file=sys.stderr)
        sys.exit(1)
    targets = ["cursor", "claude"] if args.target == "both" else [args.target]
    for t in targets:
        install_target(t, args.private)


if __name__ == "__main__":
    main()
