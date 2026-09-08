"""Strategy core: per-direction state machine -> Signals. Pure; knows nothing about positions.

Spec: docs/superpowers/specs/2026-09-08-rsi-fvg-pullback-strategy-design.md §2.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, IntEnum

import numpy as np

from .bars import Bars
from .fvg import FvgArrays, detect_fvg
from .indicators import atr_wilder, pivot_high, pivot_low, rsi_wilder
from .params import StrategyParams


class Direction(IntEnum):
    BUY = 1
    SELL = -1


class Variant(str, Enum):
    A = "A"  # FVG confirmation
    B = "B"  # RSI reclaim of mid level
    C = "C"  # close beyond pullback pivot


class State(IntEnum):
    IDLE = 0
    ARMED = 1
    WAIT = 2


@dataclass(frozen=True)
class Signal:
    direction: Direction
    variant: Variant
    signal_bar: int
    anchor_bar: int
    ref_price: float
    sl_price: float
    bars_in_wait: int
    fvg_zone: tuple[float, float] | None = None
    pivot_price: float | None = None


@dataclass
class Indicators:
    rsi: np.ndarray
    atr: np.ndarray
    fvg: FvgArrays
    piv_high: np.ndarray
    piv_low: np.ndarray


def compute_indicators(bars: Bars, params: StrategyParams) -> Indicators:
    return Indicators(
        rsi=rsi_wilder(bars.close, params.rsi_period),
        atr=atr_wilder(bars.high, bars.low, bars.close, params.atr_period),
        fvg=detect_fvg(bars.open, bars.high, bars.low, bars.close),
        piv_high=pivot_high(bars.high, params.pivot_len, params.pivot_len),
        piv_low=pivot_low(bars.low, params.pivot_len, params.pivot_len),
    )


def run_direction(direction: Direction, bars: Bars, ind: Indicators,
                  params: StrategyParams, variant: Variant) -> list[Signal]:
    buy = direction == Direction.BUY
    rsi, atr = ind.rsi, ind.atr
    close, high, low = bars.close, bars.high, bars.low
    ext = params.overbought if buy else params.oversold
    mid = params.mid_high if buy else params.mid_low
    fvg_hit = ind.fvg.bull if buy else ind.fvg.bear
    piv = ind.piv_high if buy else ind.piv_low
    piv_price = high if buy else low
    L = params.pivot_len
    n = len(bars)

    state = State.IDLE
    anchor = -1
    wait_start = -1
    last_pivot: float | None = None
    out: list[Signal] = []

    def reset_to(new_state: State, new_anchor: int) -> None:
        nonlocal state, anchor, wait_start, last_pivot
        state, anchor, wait_start, last_pivot = new_state, new_anchor, -1, None

    for t in range(1, n):
        r0, r1 = rsi[t], rsi[t - 1]
        if math.isnan(r0) or math.isnan(r1):
            continue
        cross = (r1 <= ext < r0) if buy else (r1 >= ext > r0)

        # Pivot bookkeeping: record new pivot formed at/after anchor. Safe to use possibly-stale
        # anchor here because reset_to() is called immediately after if cross=True, clearing last_pivot.
        # pivot confirmed at t has index t-L; only pivots formed at/after anchor count
        p = t - L
        if p >= 0 and anchor >= 0 and p >= anchor and piv[p]:
            last_pivot = float(piv_price[p])

        if state == State.IDLE:
            if cross:
                reset_to(State.ARMED, t)
            continue

        if cross:  # ARMED or WAIT: a new cross replaces the old setup
            reset_to(State.ARMED, t)
            continue

        if state == State.ARMED:
            pulled_back = (r0 < mid) if buy else (r0 > mid)
            if pulled_back:
                state, wait_start = State.WAIT, t
            continue

        # state == WAIT
        if params.max_wait_bars > 0 and (t - wait_start) > params.max_wait_bars:
            reset_to(State.IDLE, -1)
            continue
        if t <= wait_start:
            continue

        trig = False
        zone: tuple[float, float] | None = None
        pp: float | None = None
        if variant == Variant.A:
            trig = bool(fvg_hit[t])
            if trig:
                zone = (float(ind.fvg.lo[t]), float(ind.fvg.hi[t]))
        elif variant == Variant.B:
            trig = (r1 < mid <= r0) if buy else (r1 > mid >= r0)
        elif variant == Variant.C:
            if last_pivot is not None:
                trig = (close[t] > last_pivot) if buy else (close[t] < last_pivot)
                pp = last_pivot
        if not trig:
            continue

        a = atr[t]
        if math.isnan(a):
            continue
        if buy:
            sl = float(low[anchor:t + 1].min() - params.atr_mult * a)
        else:
            sl = float(high[anchor:t + 1].max() + params.atr_mult * a)
        out.append(Signal(direction=direction, variant=variant, signal_bar=t, anchor_bar=anchor,
                          ref_price=float(close[t]), sl_price=sl, bars_in_wait=t - wait_start,
                          fvg_zone=zone, pivot_price=pp))
        reset_to(State.IDLE, -1)
    return out


def run_strategy(bars: Bars, params: StrategyParams, variant: Variant | str,
                 directions: tuple[Direction, ...] = (Direction.BUY, Direction.SELL)) -> list[Signal]:
    variant = Variant(variant)
    ind = compute_indicators(bars, params)
    out: list[Signal] = []
    for d in directions:
        out.extend(run_direction(d, bars, ind, params, variant))
    out.sort(key=lambda s: (s.signal_bar, int(s.direction)))
    return out
