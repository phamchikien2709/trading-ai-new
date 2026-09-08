"""Pins the rsi2_swing grid output so the generic-adapter refactor cannot change it.

The CSV was generated from the pre-refactor optimizer (see the plan, Task 1 Step 2).
If a later change makes this fail, the change is wrong — do not regenerate the file.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rsi_fvg.bars import Bars
from rsi_fvg.params import CostParams, SizingParams, SymbolSpec
from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams

GOLDEN = Path(__file__).parent / "data" / "golden_rsi2_swing_grid.csv"
GOLDEN_COLS = ["tf", "rsi_fast", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r",
               "n_signals", "n_trades", "win_rate", "avg_r", "profit_factor", "net_pnl",
               "max_dd_pct", "is_n_trades", "is_avg_r", "oos_n_trades", "oos_avg_r",
               "robust_r", "robust_ratio", "ruined", "grid_edge", "flags"]
SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0)
COSTS = CostParams(spread_points=20, commission_per_lot_rt=0.0, slippage_points=0)
SIZING = SizingParams(risk_pct=1.0, initial_equity=10_000.0)


def golden_bars(n=8000, seed=17):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    return Bars(time=1_700_000_000 + np.arange(n, dtype=np.int64) * 300,
                open=open_, high=high, low=low, close=close)


def golden_inputs():
    """(bars_by_tf, spec_by_tf, base, axis values) for the pinned run."""
    bars = golden_bars()
    return ({"M5": bars}, {"M5": SPEC}, Rsi2SwingParams(),
            dict(tp_r=(1.0, 2.0, 4.0), atr_mult=(0.5, 1.5), rsi_fast=(2, 5),
                 rsi_slow_levels=((75.0, 25.0),), rsi_fast_levels=((90.0, 10.0),)))


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    out = df[GOLDEN_COLS].copy()
    out["flags"] = out["flags"].fillna("")
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].round(9)
    return out.sort_values(GOLDEN_COLS[:8]).reset_index(drop=True)


def build_grid_df() -> pd.DataFrame:
    """Run the optimizer the way the fixture was produced."""
    from rsi_fvg.backtest.optimize import GridSpec, run_optimization
    bars_by_tf, spec_by_tf, base, ax = golden_inputs()
    grid = GridSpec(tp_r=ax["tp_r"], atr_mult=ax["atr_mult"], rsi_fast=ax["rsi_fast"],
                    rsi_slow_levels=ax["rsi_slow_levels"], rsi_fast_levels=ax["rsi_fast_levels"])
    return run_optimization(bars_by_tf, spec_by_tf, base, grid, COSTS, SIZING, "hedge")


def test_golden_fixture_exists():
    assert GOLDEN.exists(), "generate the fixture first (plan Task 1 Step 2)"


def test_rsi2_swing_grid_matches_golden():
    got = normalise(build_grid_df())
    want = normalise(pd.read_csv(GOLDEN))
    assert len(got) == 12, "3 tp x 2 atr x 2 rsi_fast x 1 x 1"
    pd.testing.assert_frame_equal(got, want, check_dtype=False, rtol=0, atol=1e-9)
