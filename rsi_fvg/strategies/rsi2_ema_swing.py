"""RSI2 swing + EMA trend strategy.

Spec: docs/superpowers/specs/2026-09-08-rsi2-ema-swing-strategy-design.md §2.

The RSI(2) swing structure is the same one `rsi2_swing` uses (imported, not copied). What
changes is the trigger: there is no RSI(14) arm-and-wait state machine, so every confirmed
swing whose side agrees with the EMA trend is a signal. Whether that signal can actually open
a position (one per direction) is the engine's business, not this module's.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..bars import Bars
from ..indicators import atr_wilder, ema, rsi_wilder
from ..signals import Direction, Signal
from .rsi2_swing import cross_down, cross_up, htf_rsi, swing_structure

VARIANT = "EMASWING"


@dataclass(frozen=True)
class Rsi2EmaParams:
    rsi_fast: int = 2
    fast_hi: float = 90.0
    fast_lo: float = 10.0
    ema_fast: int = 20
    ema_slow: int = 100
    atr_len: int = 14
    atr_mult: float = 1.5
    htf_seconds: int = 0            # 0 = trend gate off; 3600 = H1
    htf_rsi_len: int = 14
    htf_level: float = 50.0


def compute_inputs(bars: Bars, params: Rsi2EmaParams):
    rsi_f = rsi_wilder(bars.close, params.rsi_fast)
    ema_f = ema(bars.close, params.ema_fast)
    ema_s = ema(bars.close, params.ema_slow)
    atr = atr_wilder(bars.high, bars.low, bars.close, params.atr_len)
    htf = htf_rsi(bars, params.htf_seconds, params.htf_rsi_len) if params.htf_seconds > 0 else None
    return rsi_f, ema_f, ema_s, atr, htf


def run_strategy(bars: Bars, params: Rsi2EmaParams,
                 directions: tuple[Direction, ...] = (Direction.BUY, Direction.SELL)) -> list[Signal]:
    rsi_f, ema_f, ema_s, atr, htf = compute_inputs(bars, params)
    f_up = cross_up(rsi_f, params.fast_hi)
    f_dn = cross_down(rsi_f, params.fast_lo)
    ev = swing_structure(bars.high, bars.low, f_up, f_dn)
    want_buy = Direction.BUY in directions
    want_sell = Direction.SELL in directions

    out: list[Signal] = []
    low_start = -1        # bar the current LOW segment started on (the last cross under fast_lo)
    high_start = -1
    for t in range(len(bars)):
        usable = not (math.isnan(ema_f[t]) or math.isnan(ema_s[t]) or math.isnan(atr[t]))
        if htf is None:
            gate_buy = gate_sell = True
        else:                                  # NaN htf fails both comparisons, which is the intent
            gate_buy = bool(htf[t] > params.htf_level)
            gate_sell = bool(htf[t] < params.htf_level)
        if usable and want_buy and ev.low_conf[t] and low_start >= 0 and gate_buy \
                and ema_f[t] > ema_s[t]:
            swing = float(ev.low_price[t])
            out.append(Signal(direction=Direction.BUY, variant=VARIANT, signal_bar=t,
                              anchor_bar=low_start, ref_price=float(bars.close[t]),
                              sl_price=swing - params.atr_mult * float(atr[t]),
                              bars_in_wait=t - low_start, swing_price=swing))
        if usable and want_sell and ev.high_conf[t] and high_start >= 0 and gate_sell \
                and ema_f[t] < ema_s[t]:
            swing = float(ev.high_price[t])
            out.append(Signal(direction=Direction.SELL, variant=VARIANT, signal_bar=t,
                              anchor_bar=high_start, ref_price=float(bars.close[t]),
                              sl_price=swing + params.atr_mult * float(atr[t]),
                              bars_in_wait=t - high_start, swing_price=swing))
        # segment starts are updated AFTER emitting: the swing confirmed at t belongs to the
        # segment that began at the previous opposite cross.
        if f_dn[t]:
            low_start = t
        if f_up[t]:
            high_start = t
    out.sort(key=lambda s: (s.signal_bar, int(s.direction)))
    return out
