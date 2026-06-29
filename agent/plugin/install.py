#!/usr/bin/env python3
"""Install HydraTrade agent plugin into .cursor/skills/ (local Cursor config)."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = Path(__file__).resolve().parent
SKILLS_SRC = PLUGIN / "skills"
CURSOR_SKILLS = ROOT / ".cursor" / "skills"
AGENT_SKILL = ROOT / "agent" / "DAYTRADER_AGENT_SKILL.md"
PRIVATE_SKILL = ROOT / "agent" / "private" / "STRATEGY_KNOWLEDGE.md"


def _split_agent_skill(private: bool) -> str:
    teil1_marker = "# TEIL 1 — Allgemeines Trading-Wissen"
    teil2_marker = "# TEIL 2 — Your private strategy knowledge (optional)"
    text = AGENT_SKILL.read_text(encoding="utf-8")

    if teil1_marker not in text:
        return text
    start = text.index(teil1_marker)
    body = text[start:]
    if teil2_marker in body:
        teil1_only = body.split(teil2_marker)[0].rstrip()
    else:
        teil1_only = body

    if not private:
        return teil1_only + (
            "\n\n---\n\n"
            "*Optional private strategy notes: see `agent/private/README.md` "
            "and run `install.py --private` after creating `STRATEGY_KNOWLEDGE.md`.*\n"
        )

    if PRIVATE_SKILL.is_file():
        teil2 = PRIVATE_SKILL.read_text(encoding="utf-8").strip()
        return teil1_only + "\n\n---\n---\n\n" + teil2 + "\n"

    return body.strip() + (
        "\n\n---\n\n"
        "*No `agent/private/STRATEGY_KNOWLEDGE.md` found — copy from "
        "`STRATEGY_KNOWLEDGE.md.example` and re-run with `--private`.*\n"
    )


def _write_daytrader_skill(private: bool) -> None:
    dest = CURSOR_SKILLS / "hydratrade-daytrader"
    dest.mkdir(parents=True, exist_ok=True)
    body = _split_agent_skill(private)
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
        help="Include agent/private/STRATEGY_KNOWLEDGE.md in the day-trader skill",
    )
    args = parser.parse_args()
    install(args.private)


if __name__ == "__main__":
    main()
