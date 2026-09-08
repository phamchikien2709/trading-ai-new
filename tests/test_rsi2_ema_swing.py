import numpy as np
import pytest

from rsi_fvg.bars import Bars
from rsi_fvg.signals import Direction
from rsi_fvg.strategies.rsi2_ema_swing import Rsi2EmaParams, compute_inputs, run_strategy

P = Rsi2EmaParams()


def _bars(closes, wick=0.5, step=300):
    closes = np.asarray(closes, dtype=np.float64)
    opens = np.r_[closes[0], closes[:-1]]
    high = np.maximum(opens, closes) + wick
    low = np.minimum(opens, closes) - wick
    return Bars(time=1_700_000_000 + np.arange(len(closes), dtype=np.int64) * step,
                open=opens, high=high, low=low, close=closes)


def _rng_bars(n=4000, seed=9, drift=0.0):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(drift, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    return Bars(time=1_700_000_000 + np.arange(n, dtype=np.int64) * 300,
                open=open_, high=high, low=low, close=close)


def test_signals_only_where_the_ema_trend_agrees():
    """Same price path, two EMA settings: the up-trend one buys, the reversed one does not."""
    bars = _rng_bars(seed=3, drift=0.6)          # rising series -> ema_fast > ema_slow
    up = run_strategy(bars, Rsi2EmaParams(ema_fast=20, ema_slow=100))
    down = run_strategy(bars, Rsi2EmaParams(ema_fast=100, ema_slow=20))   # inverted comparison
    assert any(s.direction == Direction.BUY for s in up)
    assert all(s.direction == Direction.SELL for s in down) or not down
    assert all(s.variant == "EMASWING" for s in up + down)


def test_buy_carries_swing_low_sl_and_segment_anchor():
    bars = _rng_bars(seed=3, drift=0.6)
    params = Rsi2EmaParams(atr_mult=1.5)
    rsi_f, ema_f, ema_s, atr, _ = compute_inputs(bars, params)
    buys = [s for s in run_strategy(bars, params) if s.direction == Direction.BUY]
    assert buys
    s = buys[0]
    lo = bars.low[s.anchor_bar:s.signal_bar + 1].min()
    assert s.swing_price == pytest.approx(lo)
    assert s.sl_price == pytest.approx(s.swing_price - 1.5 * atr[s.signal_bar])
    assert s.ref_price == bars.close[s.signal_bar]
    assert s.bars_in_wait == s.signal_bar - s.anchor_bar > 0
    assert ema_f[s.signal_bar] > ema_s[s.signal_bar]


def test_sell_mirrors_on_swing_high():
    bars = _rng_bars(seed=4, drift=-0.6)
    params = Rsi2EmaParams(atr_mult=2.0)
    _, ema_f, ema_s, atr, _ = compute_inputs(bars, params)
    sells = [s for s in run_strategy(bars, params) if s.direction == Direction.SELL]
    assert sells
    s = sells[0]
    hi = bars.high[s.anchor_bar:s.signal_bar + 1].max()
    assert s.swing_price == pytest.approx(hi)
    assert s.sl_price == pytest.approx(s.swing_price + 2.0 * atr[s.signal_bar])
    assert ema_f[s.signal_bar] < ema_s[s.signal_bar]


def test_equal_emas_produce_no_signal():
    bars = _rng_bars(seed=5)
    same = run_strategy(bars, Rsi2EmaParams(ema_fast=20, ema_slow=20))
    assert same == []


def test_directions_argument_filters():
    bars = _rng_bars(seed=3, drift=0.6)
    only_buy = run_strategy(bars, P, directions=(Direction.BUY,))
    assert only_buy and all(s.direction == Direction.BUY for s in only_buy)


def test_no_signal_during_the_ema_warmup():
    bars = _rng_bars(seed=6)
    sigs = run_strategy(bars, Rsi2EmaParams(ema_slow=200))
    assert all(s.signal_bar >= 199 for s in sigs)


def test_htf_gate_blocks_and_allows():
    bars = _rng_bars(seed=3, drift=0.6)
    off = run_strategy(bars, Rsi2EmaParams())
    on = run_strategy(bars, Rsi2EmaParams(htf_seconds=3600))
    assert len(on) <= len(off)
    assert {(s.signal_bar, s.direction) for s in on} <= {(s.signal_bar, s.direction) for s in off}
    impossible = run_strategy(bars, Rsi2EmaParams(htf_seconds=3600, htf_level=1000.0))
    assert not [s for s in impossible if s.direction == Direction.BUY]


def test_sorted_and_deterministic():
    bars = _rng_bars(seed=7)
    sigs = run_strategy(bars, P)
    keys = [(s.signal_bar, int(s.direction)) for s in sigs]
    assert keys == sorted(keys)
    assert sigs == run_strategy(bars, P)


@pytest.mark.parametrize("k", [500, 1000, 2500, 3999])
def test_prefix_invariance_no_lookahead(k):
    bars = _rng_bars(seed=8)
    full = run_strategy(bars, P)
    prefix = run_strategy(bars.slice(0, k), P)
    want = [s for s in full if s.signal_bar < k]
    assert prefix == want
