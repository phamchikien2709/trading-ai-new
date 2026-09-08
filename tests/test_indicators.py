import numpy as np
import pytest

from rsi_fvg.indicators import (atr_wilder, candle_color, pivot_high, pivot_low,
                                rsi_wilder, true_range)


def _ref_rsi(close, period):
    """Straightforward reference: SMA seed then Wilder smoothing."""
    close = np.asarray(close, float)
    n = len(close)
    out = np.full(n, np.nan)
    d = np.diff(close)
    gains = np.where(d > 0, d, 0.0)
    losses = np.where(d < 0, -d, 0.0)
    ag = gains[:period].mean()
    al = losses[:period].mean()
    out[period] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(period + 1, n):
        ag = (ag * (period - 1) + gains[i - 1]) / period
        al = (al * (period - 1) + losses[i - 1]) / period
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def test_rsi_matches_reference_and_nan_prefix():
    rng = np.random.default_rng(0)
    close = 2000 + np.cumsum(rng.normal(0, 1, 200))
    got = rsi_wilder(close, 14)
    ref = _ref_rsi(close, 14)
    assert np.all(np.isnan(got[:14]))
    np.testing.assert_allclose(got[14:], ref[14:], atol=1e-9)
    assert np.nanmin(got) >= 0 and np.nanmax(got) <= 100


def test_rsi_all_up_is_100_all_down_is_0():
    up = np.arange(1, 40, dtype=float)
    assert rsi_wilder(up, 14)[-1] == pytest.approx(100.0)
    down = np.arange(40, 1, -1, dtype=float)
    assert rsi_wilder(down, 14)[-1] == pytest.approx(0.0)


def test_true_range_first_bar_and_gap():
    h = np.array([10, 12, 20.0]); l = np.array([9, 11, 19.0]); c = np.array([9.5, 11.5, 19.5])
    tr = true_range(h, l, c)
    assert tr[0] == 1.0
    assert tr[1] == pytest.approx(max(12 - 11, abs(12 - 9.5), abs(11 - 9.5)))  # 2.5
    assert tr[2] == pytest.approx(max(1.0, abs(20 - 11.5), abs(19 - 11.5)))   # 8.5


def test_atr_wilder_seed_and_smoothing():
    n = 30
    h = np.full(n, 11.0); l = np.full(n, 10.0); c = np.full(n, 10.5)
    h[20] = 15.0  # one spike -> TR jumps
    atr = atr_wilder(h, l, c, 14)
    assert np.all(np.isnan(atr[:13])) and not np.isnan(atr[13])
    assert atr[13] == pytest.approx(1.0)
    tr20 = max(15 - 10, abs(15 - 10.5), abs(10 - 10.5))  # 5.0 (prev close 10.5)
    expected20 = (atr[19] * 13 + tr20) / 14
    assert atr[20] == pytest.approx(expected20)
    assert atr[21] == pytest.approx((atr[20] * 13 + 1.0) / 14)


def test_candle_color():
    o = np.array([1.0, 2.0, 3.0]); c = np.array([2.0, 1.0, 3.0])
    np.testing.assert_array_equal(candle_color(o, c), np.array([1, -1, 0], dtype=np.int8))


def test_pivot_high_strict_and_edges():
    high = np.array([1, 2, 5, 2, 1, 5, 5, 1, 9.0])
    ph = pivot_high(high, 2, 2)
    assert ph[2]  # 5 > [1,2] and > [2,1]
    assert not ph[5] and not ph[6]  # equal highs are not strict pivots
    assert not ph[8]  # not enough bars on the right
    assert ph.dtype == bool and len(ph) == len(high)


def test_pivot_low_mirror():
    low = np.array([5, 4, 1, 4, 5, 1, 1, 5.0])
    pl = pivot_low(low, 2, 2)
    assert pl[2] and not pl[5] and not pl[6]


def test_ema_hand_computed_with_nan_warmup():
    from rsi_fvg.indicators import ema
    close = np.array([10.0, 20.0, 30.0, 40.0])
    got = ema(close, 3)                      # alpha = 0.5, seed = close[0]
    assert np.isnan(got[0]) and np.isnan(got[1])
    assert got[2] == pytest.approx(22.5)     # 10 -> 15 -> 22.5
    assert got[3] == pytest.approx(31.25)


def test_ema_pine_divergence_is_the_seed_only_and_decays():
    """Pins the real Python<->Pine EMA relationship (docstring / README / spec §2.1).

    Pine's `ta.ema` is seeded with `ta.sma(src, length)`, which is itself `na` before bar
    `length-1`, so BOTH sides are undefined for the first `period-1` bars — the divergence is
    the seed (Python starts from close[0]) and it decays away. That is why the documented
    parity window starts at bar 5*ema_slow.
    """
    from rsi_fvg.indicators import ema
    rng = np.random.default_rng(3)
    n, period = 1200, 100
    close = 2000 + np.cumsum(rng.normal(0, 2.0, n))

    def pine_ema(src, length):
        out = np.full(len(src), np.nan)
        alpha = 2.0 / (length + 1.0)
        out[length - 1] = src[:length].mean()          # ta.sma seed; na before this bar
        for i in range(length, len(src)):
            out[i] = out[i - 1] + alpha * (src[i] - out[i - 1])
        return out

    py, pine = ema(close, period), pine_ema(close, period)
    assert np.all(np.isnan(py[:period - 1])) and np.all(np.isnan(pine[:period - 1]))
    assert not np.isnan(py[period - 1]) and not np.isnan(pine[period - 1])   # same first live bar
    gap = np.abs(py - pine)
    assert gap[period - 1] > 0.1                    # the seed difference is real at the warm-up edge
    assert gap[300] < gap[period - 1]               # and monotonically decaying
    assert gap[5 * period] < 1e-3                   # sub-tick by the documented parity window
    assert gap[800] < 1e-6                          # gone entirely a few hundred bars later


def test_ema_period_one_is_the_close_and_short_input_is_safe():
    from rsi_fvg.indicators import ema
    close = np.array([5.0, 7.0, 9.0])
    np.testing.assert_allclose(ema(close, 1), close)
    assert np.all(np.isnan(ema(close, 10)))
    assert ema(np.array([]), 5).shape == (0,)
