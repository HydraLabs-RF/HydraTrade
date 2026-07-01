#!/usr/bin/env python3
"""One-click install of HydraTrade agent skills for **Cursor** (-> .cursor/skills/).

    python agent/plugin/install_cursor.py             # public skill (Part 2 template)
    python agent/plugin/install_cursor.py --private    # your filled private skill (Part 2)

Thin wrapper around install.py --target cursor.
"""
from __future__ import annotations

import argparse

from install import PUBLIC_SKILL, install_target


def main() -> None:
    ap = argparse.ArgumentParser(description="Install HydraTrade skills for Cursor.")
    ap.add_argument("--private", action="store_true", help="Use your filled agent/private skill")
    args = ap.parse_args()
    if not PUBLIC_SKILL.is_file():
        raise SystemExit(f"ERROR: missing {PUBLIC_SKILL}")
    install_target("cursor", args.private)


if __name__ == "__main__":
    main()
