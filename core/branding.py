"""HydraTrade terminal branding — banners and log prefixes."""

from __future__ import annotations

BANNER = """
  HH   HH YY   YY DDDDD   RRRRR    AAAAA  TTTTT  RRRRR   AAAAA  DDDDD  EEEEE
  HH   HH  YY YY  DD  DD  RR  RR  AA   AA   TTT   RR  RR AA   AA DD  DD EE
  HHHHHHH   YYY   DD   DD RRRRR   AAAAAAA   TTT   RRRRR  AAAAAAA DD   DD EEEE
  HH   HH   YYY   DD  DD  RR RR   AA   AA   TTT   RR RR  AA   AA DD  DD EE
  HH   HH   YYY   DDDDD   RR  RR  AA   AA   TTT   RR  RR AA   AA DDDDD  EEEEE

  Empowering Intelligent Trading
"""

TAG = "[HydraTrade]"


def print_banner() -> None:
    print(BANNER)


def log(msg: str) -> None:
    print(f"{TAG} {msg}")
