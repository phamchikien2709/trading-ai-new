"""Signal types shared by every strategy plugin."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Direction(IntEnum):
    BUY = 1
    SELL = -1


@dataclass(frozen=True)
class Signal:
    direction: Direction
    variant: str                 # "A" | "B" | "C" (RSI-FVG) or "SWING" (RSI2 swing)
    signal_bar: int
    anchor_bar: int
    ref_price: float
    sl_price: float
    bars_in_wait: int
    fvg_zone: tuple[float, float] | None = None
    pivot_price: float | None = None
    swing_price: float | None = None
