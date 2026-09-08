"""Fair Value Gap on 3 consecutive same-colour candles (spec §2.2)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .indicators import candle_color


@dataclass
class FvgArrays:
    bull: np.ndarray  # bool, True at C3 index
    bear: np.ndarray  # bool
    lo: np.ndarray    # zone low at C3 index, NaN elsewhere
    hi: np.ndarray    # zone high


def detect_fvg(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> FvgArrays:
    n = close.shape[0]
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    lo = np.full(n, np.nan)
    hi = np.full(n, np.nan)
    if n < 3:
        return FvgArrays(bull, bear, lo, hi)
    color = candle_color(open_, close)
    c1, c2, c3 = color[:-2], color[1:-1], color[2:]
    all_green = (c1 == 1) & (c2 == 1) & (c3 == 1)
    all_red = (c1 == -1) & (c2 == -1) & (c3 == -1)
    gap_up = high[:-2] < low[2:]
    gap_down = low[:-2] > high[2:]
    bull[2:] = all_green & gap_up
    bear[2:] = all_red & gap_down
    idx_b = np.flatnonzero(bull)
    lo[idx_b] = high[idx_b - 2]
    hi[idx_b] = low[idx_b]
    idx_s = np.flatnonzero(bear)
    lo[idx_s] = high[idx_s]
    hi[idx_s] = low[idx_s - 2]
    return FvgArrays(bull, bear, lo, hi)
