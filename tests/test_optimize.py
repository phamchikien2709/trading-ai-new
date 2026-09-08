from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rsi_fvg.backtest.optimize import (KEY_COLS, SPLIT_KEYS, GridSpec, add_robustness, compute_flags,
                                       recommend, run_optimization, run_single, split_time)
from rsi_fvg.bars import Bars
from rsi_fvg.params import CostParams, SizingParams, SymbolSpec
from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams

SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0)
COSTS = CostParams(spread_points=20, commission_per_lot_rt=0.0, slippage_points=0)
SIZING = SizingParams(risk_pct=5.0, initial_equity=10_000.0)
SMALL = GridSpec(tp_r=(1.0, 2.0), atr_mult=(0.5, 1.0), rsi_slow_levels=((75.0, 25.0),), rsi_fast_levels=((90.0, 10.0),))


def _bars(n=6000, seed=11):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    return Bars(time=1_700_000_000 + np.arange(n, dtype=np.int64) * 300, open=open_, high=high, low=low, close=close)


def test_grid_size_default_and_small():
    assert GridSpec().size() == 225 and SMALL.size() == 4


def test_split_time_70_30():
    b = _bars(1000)
    assert split_time(b, 0.7) == b.datetimes()[700]


def test_run_optimization_rows_and_columns():
    b = _bars()
    calls = []
    df = run_optimization({"M5": b}, {"M5": SPEC}, Rsi2SwingParams(), SMALL, COSTS, SIZING,
                          progress=lambda d, t: calls.append((d, t)))
    assert len(df) == 4 and calls[-1] == (4, 4)
    for c in KEY_COLS + ["n_signals", "split_time", "oversized_share", "robust_r", "robust_ratio", "flags",
                         "n_trades", "avg_r", "max_dd_pct", "sortino_daily", "time_in_market_pct"]:
        assert c in df.columns
    for k in SPLIT_KEYS:
        assert f"is_{k}" in df.columns and f"oos_{k}" in df.columns
    assert (df["is_n_trades"] + df["oos_n_trades"] == df["n_trades"]).all()
    assert df.groupby("atr_mult")["n_signals"].nunique().eq(1).all()      # signals depend on atr_mult, not tp
    assert df["flags"].map(lambda s: isinstance(s, str)).all()


def test_run_single_matches_grid_row():
    b = _bars()
    df = run_optimization({"M5": b}, {"M5": SPEC}, Rsi2SwingParams(), SMALL, COSTS, SIZING)
    row = df.iloc[0]
    params = Rsi2SwingParams(atr_mult=row.atr_mult)
    sigs, res = run_single(b, SPEC, params, row.tp_r, COSTS, SIZING, "hedge")
    assert len(sigs) == row.n_signals and len(res.trades) == row.n_trades


def test_add_robustness_median_of_neighbours():
    grid = GridSpec(tp_r=(1.0, 2.0), atr_mult=(0.5, 1.0), rsi_slow_levels=((75, 25),), rsi_fast_levels=((90, 10),))
    df = pd.DataFrame({"tf": "M5", "ob": 75.0, "os": 25.0, "f_hi": 90.0, "f_lo": 10.0,
                       "tp_r": [1.0, 1.0, 2.0, 2.0], "atr_mult": [0.5, 1.0, 0.5, 1.0],
                       "is_avg_r": [1.0, 2.0, 3.0, 4.0]})
    out = add_robustness(df, grid)
    assert out.loc[0, "robust_r"] == pytest.approx(3.0)      # neighbours 2,3,4 -> median 3
    assert out.loc[3, "robust_r"] == pytest.approx(2.0)      # neighbours 1,2,3 -> median 2
    assert out.loc[0, "robust_ratio"] == pytest.approx(1.5)  # 3/1 clipped to 1.5
    assert out.loc[3, "robust_ratio"] == pytest.approx(0.5)


def test_compute_flags():
    r = pd.Series({"n_trades": 10, "is_avg_r": 0.5, "oos_avg_r": -0.2, "n_buy": 9, "n_sell": 1, "oversized_share": 0.2})
    assert compute_flags(r) == ["n<30", "oos_sign_flip", "buy_sell_imbalance", "oversized"]
    ok = pd.Series({"n_trades": 50, "is_avg_r": 0.5, "oos_avg_r": 0.3, "n_buy": 20, "n_sell": 30, "oversized_share": 0.0})
    assert compute_flags(ok) == []


def _grid_df(rows):
    cols = {"tf": "M5", "ob": 75.0, "os": 25.0, "f_hi": 90.0, "f_lo": 10.0, "atr_mult": 1.0, "tp_r": 2.0,
            "is_n_trades": 40, "oos_n_trades": 15, "is_avg_r": 0.3, "oos_avg_r": 0.2, "robust_r": 0.25,
            "oversized_share": 0.0, "max_dd_pct": 0.1, "win_rate": 0.4, "n_buy": 20, "n_sell": 20, "n_trades": 55}
    return pd.DataFrame([cols | r for r in rows])


def test_recommend_none_when_nothing_qualifies():
    df = _grid_df([{"is_n_trades": 10}, {"oos_avg_r": -0.1}, {"oversized_share": 0.5}])
    assert recommend(df) == {"M5": None}


def test_recommend_picks_best_score_and_explains():
    df = _grid_df([{"tp_r": 1.0, "oos_avg_r": 0.10, "robust_r": 0.10, "is_avg_r": 0.10},
                   {"tp_r": 2.0, "oos_avg_r": 0.40, "robust_r": 0.35, "is_avg_r": 0.30},
                   {"tp_r": 3.0, "oos_avg_r": 0.20, "robust_r": 0.20, "is_avg_r": 0.50}])
    rec = recommend(df)["M5"]
    assert rec is not None and rec["params"]["tp_r"] == 2.0
    assert set(rec["params"]) == set(KEY_COLS)
    assert "OOS" in rec["reason"] and "robust" in rec["reason"]
