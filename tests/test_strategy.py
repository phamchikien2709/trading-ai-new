import numpy as np
import pytest

from rsi_fvg.fvg import FvgArrays
from rsi_fvg.indicators import pivot_high, pivot_low
from rsi_fvg.params import StrategyParams
from rsi_fvg.strategy import (Direction, Indicators, Signal, Variant, compute_indicators,
                              run_direction, run_strategy)

P = StrategyParams()  # 75/25/60/40, atr_mult 1, pivot_len 2


def mk_ind(bars, rsi, atr=1.0, fvg_bull=(), fvg_bear=()):
    n = len(bars)
    rsi = np.asarray(rsi, float)
    assert len(rsi) == n
    fvg = FvgArrays(np.zeros(n, bool), np.zeros(n, bool), np.full(n, np.nan), np.full(n, np.nan))
    for t in fvg_bull:
        fvg.bull[t] = True; fvg.lo[t] = bars.high[t - 2]; fvg.hi[t] = bars.low[t]
    for t in fvg_bear:
        fvg.bear[t] = True; fvg.lo[t] = bars.high[t]; fvg.hi[t] = bars.low[t - 2]
    return Indicators(rsi=rsi, atr=np.full(n, float(atr)), fvg=fvg,
                      piv_high=pivot_high(bars.high, P.pivot_len, P.pivot_len),
                      piv_low=pivot_low(bars.low, P.pivot_len, P.pivot_len))


def test_buy_variant_b_basic(mk_closes):
    #        t: 0   1   2   3   4   5
    bars = mk_closes([100, 101, 99, 98, 99, 100])
    rsi =        [70, 80, 55, 50, 58, 65]   # cross@1, wait@2, reclaim@5
    sigs = run_direction(Direction.BUY, bars, mk_ind(bars, rsi), P, Variant.B)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == Direction.BUY and s.variant == Variant.B
    assert s.signal_bar == 5 and s.anchor_bar == 1 and s.bars_in_wait == 3
    assert s.ref_price == 100.0
    assert s.sl_price == pytest.approx(bars.low[1:6].min() - 1.0)
    assert s.fvg_zone is None and s.pivot_price is None


def test_no_cross_no_signal(mk_closes):
    bars = mk_closes([100, 101, 102, 103, 104])
    assert run_direction(Direction.BUY, bars, mk_ind(bars, [50, 60, 70, 74, 74.9]), P, Variant.B) == []


def test_one_cross_one_signal(mk_closes):
    bars = mk_closes([100, 101, 99, 100, 99, 100])
    rsi =        [70, 80, 55, 65, 55, 65]   # reclaim @3 and again @5, no new cross
    sigs = run_direction(Direction.BUY, bars, mk_ind(bars, rsi), P, Variant.B)
    assert [s.signal_bar for s in sigs] == [3]


def test_recross_resets_anchor_and_flag(mk_closes):
    #        t: 0    1    2   3   4    5   6   7
    bars = mk_closes([100, 101, 95, 94, 102, 101, 100, 101])
    rsi =        [70,  80,  55, 50, 80,  70, 55, 65]  # cross@1, wait@2, RE-cross@4, wait@6, reclaim@7
    sigs = run_direction(Direction.BUY, bars, mk_ind(bars, rsi), P, Variant.B)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.anchor_bar == 4 and s.signal_bar == 7 and s.bars_in_wait == 1
    assert s.sl_price == pytest.approx(bars.low[4:8].min() - 1.0)  # ignores the 94 low before re-cross


def test_trigger_not_evaluated_on_wait_entry_bar(mk_closes):
    bars = mk_closes([100, 101, 102, 103, 104, 105])
    rsi =        [70, 80, 78, 55, 56, 57]  # wait@3
    ind = mk_ind(bars, rsi, fvg_bull=(3,))  # FVG on the same bar the flag turns on
    assert run_direction(Direction.BUY, bars, ind, P, Variant.A) == []
    ind2 = mk_ind(bars, rsi, fvg_bull=(4,))
    sigs = run_direction(Direction.BUY, bars, ind2, P, Variant.A)
    assert [s.signal_bar for s in sigs] == [4]
    assert sigs[0].fvg_zone == (bars.high[2], bars.low[4])


def test_max_wait_bars_expiry_has_priority_over_trigger(mk_closes):
    bars = mk_closes([100, 101, 99, 98, 97, 100])
    rsi =        [70, 80, 55, 50, 50, 65]   # wait@2; reclaim @5 -> 5-2=3 > 2 -> expired first
    p = StrategyParams(max_wait_bars=2)
    assert run_direction(Direction.BUY, bars, mk_ind(bars, rsi), p, Variant.B) == []
    p3 = StrategyParams(max_wait_bars=3)
    assert len(run_direction(Direction.BUY, bars, mk_ind(bars, rsi), p3, Variant.B)) == 1


def test_variant_c_pivot_break_and_no_pivot(mk_bars):
    o = [100, 101, 103, 104, 103, 102, 101, 102, 105]
    h = [101, 103, 105, 104.5, 103.5, 102.5, 101.5, 103, 106]   # pivot high at t=2 (105), confirmed t=4
    l = [99, 100, 102, 103, 102, 101, 100, 101, 104]
    c = [101, 103, 104, 103, 102, 101, 102, 103, 105.5]
    bars = mk_bars(o, h, l, c)
    rsi = [70, 80, 82, 78, 70, 55, 50, 58, 62]   # cross@1 (anchor 1), wait@5
    sigs = run_direction(Direction.BUY, bars, mk_ind(bars, rsi), P, Variant.C)
    assert [s.signal_bar for s in sigs] == [8]      # close 105.5 > pivot 105
    assert sigs[0].pivot_price == 105.0
    # same RSI path but pivot formed BEFORE anchor -> ignored
    rsi2 = [70, 74, 74, 74, 80, 55, 50, 58, 62]     # cross@4 -> pivot at t=2 < anchor
    assert run_direction(Direction.BUY, bars, mk_ind(bars, rsi2), P, Variant.C) == []


def test_sell_mirror_variant_b(mk_closes):
    bars = mk_closes([100, 99, 101, 102, 101, 100])
    rsi =        [30, 20, 45, 50, 42, 38]   # cross down@1, wait@2 (rsi>40), reclaim down @5
    sigs = run_direction(Direction.SELL, bars, mk_ind(bars, rsi), P, Variant.B)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == Direction.SELL and s.anchor_bar == 1 and s.signal_bar == 5
    assert s.sl_price == pytest.approx(bars.high[1:6].max() + 1.0)


def test_nan_rsi_prefix_is_skipped(mk_closes):
    bars = mk_closes([100] * 6)
    rsi = [np.nan, np.nan, 80, 55, 50, 65]
    sigs = run_direction(Direction.BUY, bars, mk_ind(bars, rsi), P, Variant.B)
    assert sigs == []  # cross needs rsi[t-1] valid: t=2 has nan prev -> no cross ever


def test_run_strategy_smoke_sorted_and_deterministic():
    rng = np.random.default_rng(42)
    n = 3000
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0, 1.5, n)
    from rsi_fvg.bars import Bars
    bars = Bars(time=np.arange(n, dtype=np.int64) * 300, open=open_, high=high, low=low, close=close)
    ind = compute_indicators(bars, P)
    assert ind.rsi.shape == (n,) and ind.atr.shape == (n,)
    for v in Variant:
        sigs = run_strategy(bars, P, v)
        keys = [(s.signal_bar, int(s.direction)) for s in sigs]
        assert keys == sorted(keys)
        assert sigs == run_strategy(bars, P, v)
        for s in sigs:
            assert s.anchor_bar <= s.signal_bar
            if s.direction == Direction.BUY:
                assert s.sl_price < bars.low[s.anchor_bar:s.signal_bar + 1].min()
            else:
                assert s.sl_price > bars.high[s.anchor_bar:s.signal_bar + 1].max()
