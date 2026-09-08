import numpy as np
import pytest

from rsi_fvg.bars import Bars
from rsi_fvg.signals import Direction
from rsi_fvg.strategies.rsi2_swing import (Rsi2SwingParams, cross_down, cross_up, run_direction,
                                           run_strategy, swing_structure)

P = Rsi2SwingParams()  # 75/25, 90/10, atr_mult 1


def _run(direction, bars, rs, rf, params=P, atr=1.0):
    n = len(bars)
    return run_direction(direction, bars, np.asarray(rs, float), np.asarray(rf, float), np.full(n, atr), params)


def test_cross_helpers_nan_safe():
    x = np.array([np.nan, 80, 95, 5, 50, 95])
    assert list(cross_up(x, 90)) == [False, False, True, False, False, True]
    assert list(cross_down(x, 10)) == [False, False, False, True, False, False]


def test_swing_structure_alternates_and_boundary_bar_in_both_segments(mk_bars):
    h = [10, 11, 15, 14, 13, 12, 16, 17.0]
    l = [9, 10, 14, 13, 11, 10, 15, 16.0]
    bars = mk_bars(o=h, h=h, l=l, c=h)
    f_up = np.array([0, 1, 0, 0, 0, 0, 1, 0], bool)   # HIGH seg starts t=1, LOW seg ends t=6
    f_dn = np.array([0, 0, 0, 1, 0, 0, 0, 0], bool)   # HIGH seg ends / LOW seg starts t=3
    ev = swing_structure(bars.high, bars.low, f_up, f_dn)
    assert list(ev.seg) == [0, 1, 1, -1, -1, -1, 1, 1]
    assert ev.high_conf[3] and ev.high_price[3] == 15.0        # highest high over t=1..3 (boundary t=3 included)
    assert ev.low_conf[6] and ev.low_price[6] == 10.0          # lowest low over t=3..6 (t=3 low=13, t=5 low=10)
    assert ev.low_conf.sum() == 1 and ev.high_conf.sum() == 1


def test_buy_basic_flow(mk_bars):
    #      t:  0    1    2    3    4    5    6
    l =      [99, 100, 101, 98,  97,  96.5, 99]
    h =      [101, 102, 103, 100, 99, 98,  102]
    bars = mk_bars(o=l, h=h, l=l, c=h)
    rs =     [70, 80,  80,  80,  80,  80,  80]     # s_up at t=1
    rf =     [50, 95,  95,  5,   5,   5,   95]     # f_dn t=3 -> TRACKING, f_up t=6 -> signal
    sigs = _run(Direction.BUY, bars, rs, rf)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == Direction.BUY and s.variant == "SWING"
    assert s.signal_bar == 6 and s.anchor_bar == 1 and s.bars_in_wait == 5
    assert s.swing_price == 96.5                 # min(low[3..6])
    assert s.sl_price == pytest.approx(95.5)     # swing - 1*ATR
    assert s.ref_price == 102.0


def test_low_segment_started_before_flag_is_ignored(mk_bars):
    n = 9
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[99] * n, c=[100] * n)
    rs = [70, 70, 80, 80, 80, 80, 80, 80, 80]          # s_up at t=2
    rf = [95, 5, 5, 5, 95, 95, 5, 5, 95]               # LOW seg t=1..4 (started before flag), next LOW seg t=6..8
    sigs = _run(Direction.BUY, bars, rs, rf)
    assert [s.signal_bar for s in sigs] == [8]          # not 4
    assert sigs[0].anchor_bar == 2


def test_recross_while_tracking_resets(mk_bars):
    n = 9
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[99] * n, c=[100] * n)
    rs = [70, 80, 80, 80, 70, 80, 80, 80, 80]          # s_up t=1, s_up again t=5 (70->80)
    rf = [95, 95, 5, 5, 5, 5, 95, 5, 95]               # TRACKING from t=2; f_up at t=6 would trigger, but reset at t=5
    sigs = _run(Direction.BUY, bars, rs, rf)
    # after reset at t=5 state is ARMED; f_dn at t=7 -> TRACKING; f_up at t=8 -> signal anchored at 5
    assert [(s.signal_bar, s.anchor_bar) for s in sigs] == [(8, 5)]


def test_one_flag_one_signal(mk_bars):
    n = 9
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[99] * n, c=[100] * n)
    rs = [70, 80, 80, 80, 80, 80, 80, 80, 80]
    rf = [95, 95, 5, 95, 5, 95, 5, 95, 5]               # several LOW segments, only first after flag fires
    sigs = _run(Direction.BUY, bars, rs, rf)
    assert [s.signal_bar for s in sigs] == [3]


def test_max_wait_expiry(mk_bars):
    n = 8
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[99] * n, c=[100] * n)
    rs = [70, 80, 80, 80, 80, 80, 80, 80]
    rf = [95, 95, 95, 95, 95, 5, 5, 95]                # f_dn at t=5 (t-anchor=4), f_up at t=7 (t-anchor=6)
    assert _run(Direction.BUY, bars, rs, rf, Rsi2SwingParams(max_wait=5)) == []      # expires at t=7 before trigger
    assert len(_run(Direction.BUY, bars, rs, rf, Rsi2SwingParams(max_wait=6))) == 1  # 6 > 6 is False -> trigger


def test_sell_mirror(mk_bars):
    h =      [101, 100, 99, 102, 103, 103.5, 100]
    l =      [99, 98, 97, 100, 101, 101.5, 98]
    bars = mk_bars(o=l, h=h, l=l, c=l)
    rs =     [30, 20, 20, 20, 20, 20, 20]              # s_dn at t=1
    rf =     [50, 5, 5, 95, 95, 95, 5]                 # f_up t=3 -> TRACKING high, f_dn t=6 -> signal
    sigs = _run(Direction.SELL, bars, rs, rf)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == Direction.SELL and s.signal_bar == 6 and s.anchor_bar == 1
    assert s.swing_price == 103.5 and s.sl_price == pytest.approx(104.5)


def test_run_strategy_smoke_deterministic():
    rng = np.random.default_rng(3)
    n = 5000
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    bars = Bars(time=np.arange(n, dtype=np.int64) * 300, open=open_, high=high, low=low, close=close)
    sigs = run_strategy(bars, P)
    assert len(sigs) > 0
    keys = [(s.signal_bar, int(s.direction)) for s in sigs]
    assert keys == sorted(keys) and sigs == run_strategy(bars, P)
    for s in sigs:
        assert s.variant == "SWING" and s.anchor_bar < s.signal_bar
        if s.direction == Direction.BUY:
            assert s.sl_price < s.swing_price <= bars.low[s.anchor_bar:s.signal_bar + 1].max()
            assert s.swing_price >= bars.low[s.anchor_bar:s.signal_bar + 1].min()
        else:
            assert s.sl_price > s.swing_price >= bars.high[s.anchor_bar:s.signal_bar + 1].min()
