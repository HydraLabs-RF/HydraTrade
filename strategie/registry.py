"""
HydraTrade strategy registry — example strategies only.

Register your own strategies here by adding a VariantSpec entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Type

from strategie.examples.ema_cross import ExampleEmaCross
from strategie.examples.supertrend import ExampleSuperTrend
from strategie.examples.volume_profile import ExampleVolumeProfile


@dataclass
class VariantSpec:
    variant_id: str
    name: str
    group: str
    factory: Callable[[], object]
    description: str = ""


GROUP_INFO = {
    "Examples": {
        "title": "Example Strategies",
        "text": "Educational templates shipped with HydraTrade. They demonstrate entry types "
                "(market, stop, limit), risk sizing, and trade management. "
                "NOT intended for live trading — copy and adapt them for your own ideas.",
    },
}


def _spec(cls: Type, description: str = "") -> VariantSpec:
    return VariantSpec(
        variant_id=cls.VARIANT_ID,
        name=cls.VARIANT_NAME,
        group=cls.VARIANT_GROUP,
        factory=lambda c=cls: c(quiet=True),
        description=description,
    )


ALL_VARIANTS: List[VariantSpec] = [
    _spec(
        ExampleEmaCross,
        "H1 EMA cross with market entries, modest RR, and cooldown (demo sizing).",
    ),
    _spec(
        ExampleSuperTrend,
        "H1 SuperTrend flips with stop entries and 1:1 reward/risk (demo sizing).",
    ),
    _spec(
        ExampleVolumeProfile,
        "H1 limit orders at session POC, aligned with EMA trend filter.",
    ),
]


def get_variant(variant_id: str) -> VariantSpec:
    for v in ALL_VARIANTS:
        if v.variant_id == variant_id:
            return v
    raise KeyError(variant_id)


def list_variants() -> List[VariantSpec]:
    return list(ALL_VARIANTS)
