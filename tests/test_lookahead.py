"""Prefix invariance: no strategy may see a bar that has not happened yet.

For any cut point k, running a strategy over the first k bars must produce exactly the
signals the full run produced with `signal_bar < k`. Any peek at a future bar — an
un-shifted indicator, a pivot confirmed from the right, a swing extreme read off the whole
array — shows up here as a signal that changes or disappears when the tail is removed.
"""
from __future__ import annotations

import numpy as np
import pytest

from rsi_fvg.bars import Bars
from rsi_fvg.params import StrategyParams
from rsi_fvg.signals import Signal
from rsi_fvg.strategies import rsi2_swing, rsi_fvg

N_BARS = 3000
CUTS = (500, 1000, 1999, 2500)


def _random_bars(n: int = N_BARS, seed: int = 20260908) -> Bars:
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2.0, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 2.0, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 2.0, n)
    return Bars(time=1_700_000_000 + np.arange(n, dtype=np.int64) * 300,
                open=open_, high=high, low=low, close=close)


def _key(s: Signal) -> tuple:
    return (s.signal_bar, int(s.direction), s.variant, s.anchor_bar,
            round(s.ref_price, 9), round(s.sl_price, 9), s.bars_in_wait)


def _check(run, bars: Bars) -> None:
    full = run(bars)
    assert full, "the fixture must generate signals or this proves nothing"
    for k in CUTS:
        prefix = [_key(s) for s in run(bars.slice(0, k))]
        expected = [_key(s) for s in full if s.signal_bar < k]
        assert prefix == expected, f"prefix run at k={k} disagrees with the full run"


@pytest.fixture(scope="module")
def bars() -> Bars:
    return _random_bars()


def test_rsi2_swing_is_prefix_invariant(bars):
    params = rsi2_swing.Rsi2SwingParams()
    _check(lambda b: rsi2_swing.run_strategy(b, params), bars)


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_rsi_fvg_is_prefix_invariant(bars, variant):
    params = StrategyParams()
    _check(lambda b: rsi_fvg.run_strategy(b, params, variant), bars)
