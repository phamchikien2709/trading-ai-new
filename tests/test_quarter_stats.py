import numpy as np
import pandas as pd
import pytest

from conftest import epoch_for_ny, make_bars
from rsi_fvg.quarter_stats import MIN_BARS_PER_QUARTER, aggregate_cycles
from rsi_fvg.quarters import label_quarters


def _one_session_bars(n_per_quarter=(6, 6, 6, 6), start_hh=18):
    """Bar M5 cho một session 6h, số bar mỗi block 90m do caller đặt.

    Bar được đặt Ở ĐẦU mỗi block để số lượng là chính xác: block 90m chứa 18 bar
    M5, ta chỉ dùng n_per_quarter[i] bar đầu của block i.
    """
    base = epoch_for_ny(2026, 6, 1, start_hh)
    times, o, h, l, c = [], [], [], [], []
    for q, n in enumerate(n_per_quarter):
        q_start = base + q * 5400
        for i in range(n):
            times.append(q_start + i * 300)
            o.append(100.0 + q)
            h.append(110.0 + q)
            l.append(90.0 - q)
            c.append(105.0 + q)
    bars = make_bars(o, h, l, c)
    bars.time = np.array(times, dtype="int64")
    return bars


def test_aggregate_cycles_columns_use_theory_numbering():
    bars = _one_session_bars()
    w = aggregate_cycles(bars, label_quarters(bars.time, "q90"))
    assert len(w) == 1
    for q in (1, 2, 3, 4):
        for f in ("open", "high", "low", "close", "n"):
            assert f"q{q}_{f}" in w.columns
    assert "q0_open" not in w.columns


def test_aggregate_cycles_ohlc_is_first_max_min_last():
    bars = _one_session_bars(n_per_quarter=(6, 6, 6, 6))
    w = aggregate_cycles(bars, label_quarters(bars.time, "q90"))
    row = w.iloc[0]
    assert row["q1_open"] == 100.0 and row["q1_close"] == 105.0
    assert row["q1_high"] == 110.0 and row["q1_low"] == 90.0
    assert row["q4_open"] == 103.0 and row["q4_high"] == 113.0
    assert row["q1_n"] == 6


def test_aggregate_cycles_drops_cycle_when_one_quarter_too_thin():
    """Q3 chỉ có 2 bar (< MIN_BARS_PER_QUARTER = 3) => loại CẢ chu kỳ."""
    bars = _one_session_bars(n_per_quarter=(6, 6, 2, 6))
    w = aggregate_cycles(bars, label_quarters(bars.time, "q90"))
    assert len(w) == 0


def test_aggregate_cycles_drops_cycle_when_a_quarter_is_missing():
    """Không bar nào trong Q4 => loại cả chu kỳ, không để NaN lọt xuống thống kê."""
    bars = _one_session_bars(n_per_quarter=(6, 6, 6, 0))
    w = aggregate_cycles(bars, label_quarters(bars.time, "q90"))
    assert len(w) == 0


def test_aggregate_cycles_min_bars_is_a_parameter():
    bars = _one_session_bars(n_per_quarter=(6, 6, 2, 6))
    assert len(aggregate_cycles(bars, label_quarters(bars.time, "q90"), min_bars=2)) == 1
    assert MIN_BARS_PER_QUARTER == 3
