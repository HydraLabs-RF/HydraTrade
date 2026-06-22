from dataclasses import dataclass
from typing import Optional


@dataclass
class VolumeNode:
    price: float
    volume: float