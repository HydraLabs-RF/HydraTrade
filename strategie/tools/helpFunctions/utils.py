from typing import Dict, List
from data.models import VolumeNode


def normalize_profile(profile: Dict[float, float]) -> Dict[float, float]:
    total = sum(profile.values())
    if total == 0:
        return profile

    return {k: v / total for k, v in profile.items()}


def sort_profile(profile: Dict[float, float]) -> List[VolumeNode]:
    return [
        VolumeNode(price=p, volume=v)
        for p, v in sorted(profile.items(), key=lambda x: x[0])
    ]