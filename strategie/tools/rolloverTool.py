"""
RolloverTool — decides what to do with an OPEN position as the daily broker
rollover (swap charge) approaches. Pure decision logic (no MT5, no engine).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RolloverAction(str, Enum):
    HOLD = "HOLD"
    CLOSE = "CLOSE"
    CLOSE_GRACEFUL = "CLOSE_GRACEFUL"
    CLOSE_REENTER = "CLOSE_REENTER"


@dataclass
class RolloverConfig:
    enabled: bool = False
    window_min: int = 20
    hold_if_winning_r: float = 1.0
    respect_positive_carry: bool = True
    weekend_force_close: bool = True
    reenter_next_day: bool = True
    graceful: bool = False
    graceful_window_min: int = 5


class RolloverTool:
    def __init__(self, config: Optional[RolloverConfig] = None):
        self.config = config or RolloverConfig()

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def decide(
        self,
        *,
        minutes_to_rollover: Optional[float],
        unrealized_r: float,
        swap_favorable: bool,
        is_weekend_rollover: bool = False,
    ) -> RolloverAction:
        """Pure decision. `minutes_to_rollover` None or outside [0, window] -> HOLD."""
        c = self.config
        if not c.enabled:
            return RolloverAction.HOLD
        if minutes_to_rollover is None or minutes_to_rollover < 0 or minutes_to_rollover > c.window_min:
            return RolloverAction.HOLD

        if swap_favorable and c.respect_positive_carry and not is_weekend_rollover:
            return RolloverAction.HOLD

        if is_weekend_rollover and c.weekend_force_close:
            return self._close_variant()

        if unrealized_r >= c.hold_if_winning_r:
            return RolloverAction.HOLD

        return self._close_variant()

    def _close_variant(self) -> RolloverAction:
        c = self.config
        if c.graceful:
            return RolloverAction.CLOSE_GRACEFUL
        return RolloverAction.CLOSE_REENTER if c.reenter_next_day else RolloverAction.CLOSE

    @staticmethod
    def is_close(action: RolloverAction) -> bool:
        return action in (RolloverAction.CLOSE, RolloverAction.CLOSE_GRACEFUL,
                          RolloverAction.CLOSE_REENTER)
