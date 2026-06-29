"""
Volume Profile analytics: Value Area (VAH/VAL/POC) and HVN/LVN from a profile
dict {bin_price: volume}. Complements VolumeProfile/SessionProfile, which only
expose POC + nearest_node.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ValueArea:
    poc: float
    vah: float
    val: float
    total_volume: float


def value_area(profile: Dict[float, float], pct: float = 0.70) -> Optional[ValueArea]:
    """Value Area around the POC: keep adding the larger of the two neighbouring
    bins until `pct` of total volume is covered."""
    if not profile:
        return None
    prices = sorted(profile.keys())
    if not prices:
        return None
    vols = profile
    total = sum(vols.values())
    if total <= 0:
        return None

    poc = max(vols, key=vols.get)
    i = prices.index(poc)
    lo = hi = i
    acc = vols[poc]
    target = total * pct
    n = len(prices)
    while acc < target and (lo > 0 or hi < n - 1):
        below = vols[prices[lo - 1]] if lo > 0 else -1.0
        above = vols[prices[hi + 1]] if hi < n - 1 else -1.0
        if above >= below:
            hi += 1
            acc += vols[prices[hi]]
        else:
            lo -= 1
            acc += vols[prices[lo]]
    return ValueArea(poc=poc, vah=prices[hi], val=prices[lo], total_volume=total)


def hvn_nodes(profile: Dict[float, float], frac: float = 0.7) -> List[float]:
    """Local volume maxima (acceptance) with volume >= frac * max volume,
    sorted by volume descending."""
    if not profile:
        return []
    prices = sorted(profile.keys())
    mx = max(profile.values())
    if mx <= 0:
        return []
    out = []
    for k, p in enumerate(prices):
        v = profile[p]
        left = profile[prices[k - 1]] if k > 0 else -1.0
        right = profile[prices[k + 1]] if k < len(prices) - 1 else -1.0
        if v >= frac * mx and v >= left and v >= right:
            out.append(p)
    out.sort(key=lambda p: profile[p], reverse=True)
    return out


def nearest_hvn(profile: Dict[float, float], price: float, direction: str, frac: float = 0.7) -> Optional[float]:
    """Nearest HVN above ('above') or below ('below') the given price."""
    nodes = hvn_nodes(profile, frac)
    if direction == "above":
        cands = [p for p in nodes if p > price]
        return min(cands) if cands else None
    cands = [p for p in nodes if p < price]
    return max(cands) if cands else None
