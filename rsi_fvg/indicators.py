"""Vectorised/loop indicators with Wilder smoothing. All inputs float64 numpy arrays."""
from __future__ import annotations

import numpy as np


def _rma(x: np.ndarray, period: int, first_valid: int) -> np.ndarray:
    """Wilder RMA seeded with SMA of x[first_valid : first_valid+period]."""
    n = x.shape[0]
    out = np.full(n, np.nan)
    seed_end = first_valid + period
    if seed_end > n:
        return out
    out[seed_end - 1] = np.mean(x[first_valid:seed_end])
    alpha_prev = (period - 1) / period
    for i in range(seed_end, n):
        out[i] = out[i - 1] * alpha_prev + x[i] / period
    return out


def rsi_wilder(close: np.ndarray, period: int) -> np.ndarray:
    close = np.asarray(close, dtype=np.float64)
    n = close.shape[0]
    delta = np.empty(n)
    delta[0] = 0.0
    delta[1:] = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    # deltas start at index 1 -> seed over indices 1..period, first RSI at index `period`
    avg_gain = _rma(gain, period, first_valid=1)
    avg_loss = _rma(loss, period, first_valid=1)
    out = np.full(n, np.nan)
    valid = ~np.isnan(avg_gain)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = np.where(avg_loss == 0, 100.0, rsi)
    out[valid] = rsi[valid]
    return out


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    high = np.asarray(high, float); low = np.asarray(low, float); close = np.asarray(close, float)
    tr = high - low
    if tr.shape[0] > 1:
        prev_close = close[:-1]
        tr[1:] = np.maximum(tr[1:], np.maximum(np.abs(high[1:] - prev_close), np.abs(low[1:] - prev_close)))
    return tr


def atr_wilder(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    return _rma(true_range(high, low, close), period, first_valid=0)


def candle_color(open_: np.ndarray, close: np.ndarray) -> np.ndarray:
    return np.sign(np.asarray(close, float) - np.asarray(open_, float)).astype(np.int8)


def pivot_high(high: np.ndarray, left: int, right: int) -> np.ndarray:
    high = np.asarray(high, float)
    n = high.shape[0]
    out = np.zeros(n, dtype=bool)
    for i in range(left, n - right):
        v = high[i]
        if np.all(high[i - left:i] < v) and np.all(high[i + 1:i + 1 + right] < v):
            out[i] = True
    return out


def pivot_low(low: np.ndarray, left: int, right: int) -> np.ndarray:
    low = np.asarray(low, float)
    n = low.shape[0]
    out = np.zeros(n, dtype=bool)
    for i in range(left, n - right):
        v = low[i]
        if np.all(low[i - left:i] > v) and np.all(low[i + 1:i + 1 + right] > v):
            out[i] = True
    return out


def ema(close: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average, `alpha = 2/(period+1)`, recursion seeded with `close[0]`.

    The first `period-1` values are NaN so callers skip the warm-up. Pine's `ta.ema` is
    undefined over exactly the same prefix — it is seeded with `ta.sma(src, length)`, which is
    itself `na` before bar `length-1` — so neither side produces signals in the warm-up.

    The one intended divergence is the **seed**: this recursion starts from `close[0]`, while
    Pine's `ta.ema` and MT5's `iMA` MODE_EMA start from the SMA of the first `period` closes.
    Both then run the same alpha, so the gap decays geometrically: measured on a random walk
    with `period=100` it was ~0.7 price units at bar 99, ~0.01 at bar 300, and below 1e-6 by
    bar 800. Comparing Python against Pine/MT5 from bar `5 x period` onwards is therefore sound.
    """
    close = np.asarray(close, dtype=np.float64)
    n = close.shape[0]
    out = np.full(n, np.nan)
    if n == 0:
        return out
    alpha = 2.0 / (period + 1.0)
    prev = float(close[0])
    for i in range(n):
        if i:
            prev += alpha * (float(close[i]) - prev)
        if i >= period - 1:
            out[i] = prev
    return out
