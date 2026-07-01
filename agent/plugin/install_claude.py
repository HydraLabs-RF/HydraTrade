#!/usr/bin/env python3
"""One-click install of HydraTrade agent skills for **Claude Code (VS Code / CLI)**
(-> .claude/skills/).

    python agent/plugin/install_claude.py             # public skill (Part 2 template)
    python agent/plugin/install_claude.py --private    # your filled private skill (Part 2)

Thin wrapper around install.py --target claude. After installing, restart Claude Code
(or run /doctor) to pick up the skills.
"""
from __future__ import annotations

import argparse

from install import PUBLIC_SKILL, install_target


def main() -> None:
    ap = argparse.ArgumentParser(description="Install HydraTrade skills for Claude Code.")
    ap.add_argument("--private", action="store_true", help="Use your filled agent/private skill")
    args = ap.parse_args()
    if not PUBLIC_SKILL.is_file():
        raise SystemExit(f"ERROR: missing {PUBLIC_SKILL}")
    install_target("claude", args.private)


if __name__ == "__main__":
    main()
