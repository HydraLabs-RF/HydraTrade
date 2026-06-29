#!/usr/bin/env python3
"""Install HydraTrade agent plugin into .cursor/skills/ (local Cursor config)."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = Path(__file__).resolve().parent
SKILLS_SRC = PLUGIN / "skills"
CURSOR_SKILLS = ROOT / ".cursor" / "skills"
PUBLIC_SKILL = ROOT / "agent" / "DAYTRADER_AGENT_SKILL.public.md"
PRIVATE_SKILL = ROOT / "agent" / "private" / "DAYTRADER_AGENT_SKILL.md"
PRIVATE_EXAMPLE = ROOT / "agent" / "private" / "DAYTRADER_AGENT_SKILL.md.example"


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
    body = PUBLIC_SKILL.read_text(encoding="utf-8").strip()
    return body


def _write_daytrader_skill(private: bool) -> None:
    dest = CURSOR_SKILLS / "hydratrade-daytrader"
    dest.mkdir(parents=True, exist_ok=True)
    body = _skill_body(private)
    content = f"""---
name: hydratrade-daytrader
description: >-
  HydraTrade day-trading — strategy design, indicators, regime thinking, backtest validation,
  prop rules, and framework workflows. Use when building or testing strategies in this repo.
---

{body}
"""
    (dest / "SKILL.md").write_text(content, encoding="utf-8")
    print(f"  hydratrade-daytrader -> {dest / 'SKILL.md'}")


def install(private: bool) -> None:
    if not PUBLIC_SKILL.is_file():
        print(f"ERROR: missing {PUBLIC_SKILL}", file=sys.stderr)
        sys.exit(1)
    CURSOR_SKILLS.mkdir(parents=True, exist_ok=True)
    print(f"Installing to {CURSOR_SKILLS} (private={private})")
    _write_daytrader_skill(private)
    for src in sorted(SKILLS_SRC.glob("hydra-*")):
        if not src.is_dir():
            continue
        dest = CURSOR_SKILLS / src.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        print(f"  {src.name} -> {dest}")
    print("Done. Open a new agent chat in Cursor to pick up skills.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--private",
        action="store_true",
        help="Use agent/private/DAYTRADER_AGENT_SKILL.md (full skill, local only)",
    )
    args = parser.parse_args()
    install(args.private)


if __name__ == "__main__":
    main()
