import numpy as np

from rsi_fvg.fvg import detect_fvg


def _fvg(o, h, l, c):
    return detect_fvg(np.array(o, float), np.array(h, float), np.array(l, float), np.array(c, float))


def test_bull_fvg_three_green_with_gap():
    # C1: 10->11 (h 11.2), C2: 11->13, C3: 13->14 (low 13.0 > 11.2)
    f = _fvg(o=[10, 11, 13], h=[11.2, 13.1, 14.2], l=[9.9, 10.9, 13.0], c=[11, 13, 14])
    assert list(f.bull) == [False, False, True]
    assert not f.bear.any()
    assert (f.lo[2], f.hi[2]) == (11.2, 13.0)
    assert np.isnan(f.lo[0]) and np.isnan(f.lo[1])


def test_three_green_without_gap_is_not_fvg():
    f = _fvg(o=[10, 11, 13], h=[11.2, 13.1, 14.2], l=[9.9, 10.9, 11.0], c=[11, 13, 14])  # low C3 11.0 < high C1 11.2
    assert not f.bull.any()


def test_doji_breaks_streak():
    f = _fvg(o=[10, 11, 13], h=[11.2, 13.1, 14.2], l=[9.9, 10.9, 13.0], c=[11, 11, 14])  # C2 doji
    assert not f.bull.any()


def test_mixed_color_with_gap_is_not_fvg():
    f = _fvg(o=[10, 11, 13], h=[11.2, 13.1, 14.2], l=[9.9, 10.9, 13.0], c=[11, 10.95, 14])  # C2 red
    assert not f.bull.any()


def test_bear_fvg_mirror():
    # C1: 14->13 (low 12.8), C2: 13->11, C3: 11->10 (high 10.9 < 12.8)
    f = _fvg(o=[14, 13, 11], h=[14.1, 13.1, 10.9], l=[12.8, 10.9, 9.8], c=[13, 11, 10])
    assert list(f.bear) == [False, False, True]
    assert not f.bull.any()
    assert (f.lo[2], f.hi[2]) == (10.9, 12.8)


def test_short_series_no_crash():
    f = _fvg(o=[1, 2], h=[2, 3], l=[0, 1], c=[2, 3])
    assert len(f.bull) == 2 and not f.bull.any()
