"""RSI2 Swing Pullback strategy — line-by-line port of pine/rsi2_swing_strategy.pine.

Spec: docs/superpowers/specs/2026-09-08-rsi2-swing-backtest-optimizer-design.md §2.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum

import numpy as np

from ..bars import Bars
from ..indicators import atr_wilder, rsi_wilder
from ..signals import Direction, Signal

VARIANT = "SWING"


@dataclass(frozen=True)
class Rsi2SwingParams:
    rsi_slow: int = 14
    overbought: float = 75.0
    oversold: float = 25.0
    rsi_fast: int = 2
    fast_hi: float = 90.0
    fast_lo: float = 10.0
    atr_len: int = 14
    atr_mult: float = 1.0
    max_wait: int = 0  # bars from flag to entry; 0 = never expires


class State(IntEnum):
    IDLE = 0
    ARMED = 1
    TRACKING = 2


def cross_up(x: np.ndarray, level: float) -> np.ndarray:
    x = np.asarray(x, float)
    out = np.zeros(x.shape[0], dtype=bool)
    if x.shape[0] > 1:
        prev, cur = x[:-1], x[1:]
        out[1:] = (prev <= level) & (cur > level) & ~np.isnan(prev) & ~np.isnan(cur)
    return out


def cross_down(x: np.ndarray, level: float) -> np.ndarray:
    x = np.asarray(x, float)
    out = np.zeros(x.shape[0], dtype=bool)
    if x.shape[0] > 1:
        prev, cur = x[:-1], x[1:]
        out[1:] = (prev >= level) & (cur < level) & ~np.isnan(prev) & ~np.isnan(cur)
    return out


@dataclass
class SwingEvents:
    seg: np.ndarray         # int8: 0 undefined, 1 HIGH segment, -1 LOW segment (state after bar t)
    low_conf: np.ndarray    # bool: swing low confirmed at bar t
    low_price: np.ndarray   # float: the confirmed swing low (NaN elsewhere)
    high_conf: np.ndarray
    high_price: np.ndarray


def swing_structure(high: np.ndarray, low: np.ndarray, f_up: np.ndarray, f_dn: np.ndarray) -> SwingEvents:
    n = high.shape[0]
    seg = np.zeros(n, dtype=np.int8)
    low_conf = np.zeros(n, dtype=bool)
    high_conf = np.zeros(n, dtype=bool)
    low_price = np.full(n, np.nan)
    high_price = np.full(n, np.nan)
    cur = 0
    seg_high = math.nan
    seg_low = math.nan
    for t in range(n):
        # 1. extend the running extreme (boundary bar belongs to both segments)
        if cur == 1:
            seg_high = max(seg_high, high[t])
        elif cur == -1:
            seg_low = min(seg_low, low[t])
        # 2. transitions
        if f_up[t]:
            if cur == -1:
                low_conf[t] = True
                low_price[t] = seg_low
            cur = 1
            seg_high = high[t]
        if f_dn[t]:
            if cur == 1:
                high_conf[t] = True
                high_price[t] = seg_high
            cur = -1
            seg_low = low[t]
        seg[t] = cur
    return SwingEvents(seg, low_conf, low_price, high_conf, high_price)


def compute_inputs(bars: Bars, params: Rsi2SwingParams) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (rsi_wilder(bars.close, params.rsi_slow),
            rsi_wilder(bars.close, params.rsi_fast),
            atr_wilder(bars.high, bars.low, bars.close, params.atr_len))


def run_direction(direction: Direction, bars: Bars, rsi_slow: np.ndarray, rsi_fast: np.ndarray,
                  atr: np.ndarray, params: Rsi2SwingParams) -> list[Signal]:
    buy = direction == Direction.BUY
    n = len(bars)
    close, high, low = bars.close, bars.high, bars.low
    arm = cross_up(rsi_slow, params.overbought) if buy else cross_down(rsi_slow, params.oversold)
    f_up = cross_up(rsi_fast, params.fast_hi)
    f_dn = cross_down(rsi_fast, params.fast_lo)
    seg_start = f_dn if buy else f_up      # the segment we track starts here
    seg_end = f_up if buy else f_dn        # ... and its extreme is confirmed here

    state = State.IDLE
    anchor = -1
    run_ext = math.nan
    out: list[Signal] = []
    for t in range(1, n):
        if (math.isnan(rsi_slow[t]) or math.isnan(rsi_slow[t - 1]) or math.isnan(rsi_fast[t])
                or math.isnan(rsi_fast[t - 1]) or math.isnan(atr[t])):
            continue
        if state == State.IDLE:
            if arm[t]:
                state, anchor, run_ext = State.ARMED, t, math.nan
            continue
        if arm[t]:                                   # re-cross: replace the setup
            state, anchor, run_ext = State.ARMED, t, math.nan
            continue
        if params.max_wait > 0 and (t - anchor) > params.max_wait:
            state, anchor, run_ext = State.IDLE, -1, math.nan
            continue
        if state == State.ARMED:
            if seg_start[t]:
                state = State.TRACKING
                run_ext = low[t] if buy else high[t]
            continue
        # TRACKING
        run_ext = min(run_ext, low[t]) if buy else max(run_ext, high[t])
        if seg_end[t]:
            sl = run_ext - params.atr_mult * atr[t] if buy else run_ext + params.atr_mult * atr[t]
            out.append(Signal(direction=direction, variant=VARIANT, signal_bar=t, anchor_bar=anchor,
                              ref_price=float(close[t]), sl_price=float(sl), bars_in_wait=t - anchor,
                              swing_price=float(run_ext)))
            state, anchor, run_ext = State.IDLE, -1, math.nan
    return out


def run_strategy(bars: Bars, params: Rsi2SwingParams,
                 directions: tuple[Direction, ...] = (Direction.BUY, Direction.SELL)) -> list[Signal]:
    rs, rf, atr = compute_inputs(bars, params)
    out: list[Signal] = []
    for d in directions:
        out.extend(run_direction(d, bars, rs, rf, atr, params))
    out.sort(key=lambda s: (s.signal_bar, int(s.direction)))
    return out
