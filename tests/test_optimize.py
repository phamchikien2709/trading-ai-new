import numpy as np
import pandas as pd
import pytest

from rsi_fvg.backtest.optimize import (SPLIT_KEYS, GridSpec, _segment_metrics, add_robustness,
                                       compute_flags, make_params, recommend, run_optimization, run_single,
                                       split_time)
from rsi_fvg.bars import Bars
from rsi_fvg.params import CostParams, SizingParams, SymbolSpec
from rsi_fvg.strategies.registry import get_adapter
from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams

ADAPTER = get_adapter("rsi2_swing")
KEY_COLS = ADAPTER.full_key_cols()
SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0)
COSTS = CostParams(spread_points=20, commission_per_lot_rt=0.0, slippage_points=0)
SIZING = SizingParams(risk_pct=5.0, initial_equity=10_000.0)
SMALL = GridSpec.for_strategy(ADAPTER, axes={"rsi_fast": (2,), "rsi14": ((75.0, 25.0),),
                                             "rsi2": ((90.0, 10.0),), "atr_mult": (0.5, 1.0)},
                              tp_r=(1.0, 2.0))


def _bars(n=6000, seed=11):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    return Bars(time=1_700_000_000 + np.arange(n, dtype=np.int64) * 300, open=open_, high=high, low=low, close=close)


def test_grid_size_default_and_small():
    assert GridSpec.for_strategy(ADAPTER).size() == 225 and SMALL.size() == 4
    assert GridSpec.for_strategy(ADAPTER, axes={"rsi_fast": (2, 5)}).size() == 450  # the fast-RSI length is a full grid axis


def test_make_params_sets_rsi_fast_only_when_given():
    base = Rsi2SwingParams()
    assert make_params(base, 70, 30, 90, 10, 1.0).rsi_fast == base.rsi_fast
    assert make_params(base, 70, 30, 90, 10, 1.0, rsi_fast=5).rsi_fast == 5


def test_split_time_70_30():
    b = _bars(1000)
    assert split_time(b, 0.7) == b.datetimes()[700]


def test_run_optimization_rows_and_columns():
    b = _bars()
    calls = []
    df = run_optimization(ADAPTER, {"M5": b}, {"M5": SPEC}, Rsi2SwingParams(), SMALL, COSTS, SIZING,
                          progress=lambda d, t: calls.append((d, t)))
    assert len(df) == 4 and calls[-1] == (4, 4)
    assert (df["rsi_fast"] == 2).all()
    for c in KEY_COLS + ["n_signals", "split_time", "oversized_share", "capped_share", "ruined", "ruin_time",
                         "grid_edge", "robust_r", "robust_ratio", "flags",
                         "n_trades", "avg_r", "max_dd_pct", "sortino_daily", "time_in_market_pct"]:
        assert c in df.columns
    assert df["ruined"].dtype == bool
    for k in SPLIT_KEYS:
        assert f"is_{k}" in df.columns and f"oos_{k}" in df.columns
    assert (df["is_n_trades"] + df["oos_n_trades"] == df["n_trades"]).all()
    assert df.groupby("atr_mult")["n_signals"].nunique().eq(1).all()      # signals depend on atr_mult, not tp
    assert df["flags"].map(lambda s: isinstance(s, str)).all()


def test_rsi_fast_axis_multiplies_rows_and_changes_signals():
    b = _bars()
    grid = GridSpec.for_strategy(ADAPTER, axes={"rsi_fast": (2, 5), "rsi14": ((75.0, 25.0),),
                                                "rsi2": ((90.0, 10.0),), "atr_mult": (1.0,)},
                                 tp_r=(1.0,))
    df = run_optimization(ADAPTER, {"M5": b}, {"M5": SPEC}, Rsi2SwingParams(), grid, COSTS, SIZING)
    assert len(df) == 2 and sorted(df["rsi_fast"]) == [2, 5]
    assert df["n_signals"].nunique() == 2            # a different fast length is a different strategy


def test_run_single_matches_grid_row():
    b = _bars()
    grid = GridSpec.for_strategy(ADAPTER, axes={"rsi_fast": (2, 5), "rsi14": ((75.0, 25.0),),
                                                "rsi2": ((90.0, 10.0),), "atr_mult": (1.0,)},
                                 tp_r=(1.0, 2.0))
    df = run_optimization(ADAPTER, {"M5": b}, {"M5": SPEC}, Rsi2SwingParams(), grid, COSTS, SIZING)
    assert len(df) == 4
    for row in df.itertuples():
        params = make_params(Rsi2SwingParams(), row.ob, row.os, row.f_hi, row.f_lo, row.atr_mult,
                             rsi_fast=int(row.rsi_fast))
        sigs, res = run_single(ADAPTER, b, SPEC, params, row.tp_r, COSTS, SIZING, "hedge")
        assert len(sigs) == row.n_signals and len(res.trades) == row.n_trades


def test_min_sl_filter_is_recorded_and_counted():
    b = _bars()
    off = run_optimization(ADAPTER, {"M5": b}, {"M5": SPEC}, Rsi2SwingParams(), SMALL, COSTS, SIZING)
    assert (off["min_sl_mult"] == 0.0).all() and (off["n_rejected_min_sl"] == 0).all()
    assert (off["n_trades"] > 0).any()
    # An absurd multiple (0.20 spread x 1e6) rejects every fill: no trades, all skips counted.
    on = run_optimization(ADAPTER, {"M5": b}, {"M5": SPEC}, Rsi2SwingParams(), SMALL, COSTS, SIZING,
                          min_sl_spread_mult=1e6)
    assert (on["min_sl_mult"] == 1e6).all()
    assert (on["n_trades"] == 0).all()
    gap = on["n_signals"] - on["n_rejected_min_sl"]                    # a last-bar signal never fills
    assert ((gap >= 0) & (gap <= 1)).all() and (on["n_rejected_min_sl"] > 0).all()


def test_htf_gate_is_a_run_level_switch_recorded_on_every_row():
    b = _bars()
    off = run_optimization(ADAPTER, {"M5": b}, {"M5": SPEC}, Rsi2SwingParams(), SMALL, COSTS, SIZING)
    on = run_optimization(ADAPTER, {"M5": b}, {"M5": SPEC}, Rsi2SwingParams(htf_seconds=3600), SMALL, COSTS, SIZING)
    assert (off["htf_seconds"] == 0).all() and (on["htf_seconds"] == 3600).all()
    assert (on["n_signals"].to_numpy() < off["n_signals"].to_numpy()).all()


def test_run_single_honours_the_min_sl_filter():
    b = _bars()
    params = Rsi2SwingParams()
    sigs, res = run_single(ADAPTER, b, SPEC, params, 2.0, COSTS, SIZING, "hedge", min_sl_spread_mult=1e6)
    assert len(sigs) > 0 and len(res.trades) == 0
    assert (res.skipped["reason"] == "rejected_min_sl").all()


def _robust_df(**over):
    base = {"tf": "M5", "rsi_fast": 2, "ob": 75.0, "os": 25.0, "f_hi": 90.0, "f_lo": 10.0,
            "tp_r": [1.0, 1.0, 2.0, 2.0], "atr_mult": [0.5, 1.0, 0.5, 1.0],
            "is_avg_r": [1.0, 2.0, 3.0, 4.0], "ruined": False}
    return pd.DataFrame(base | over)


def test_add_robustness_median_of_neighbours():
    grid = GridSpec.for_strategy(ADAPTER, axes={"atr_mult": (0.5, 1.0), "rsi14": ((75, 25),),
                                                "rsi2": ((90, 10),)}, tp_r=(1.0, 2.0))
    out = add_robustness(_robust_df(), grid, ADAPTER)
    assert out.loc[0, "robust_r"] == pytest.approx(3.0)      # neighbours 2,3,4 -> median 3
    assert out.loc[3, "robust_r"] == pytest.approx(2.0)      # neighbours 1,2,3 -> median 2
    assert out.loc[0, "robust_ratio"] == pytest.approx(1.5)  # 3/1 clipped to 1.5
    assert out.loc[3, "robust_ratio"] == pytest.approx(0.5)


def test_add_robustness_excludes_ruined_neighbours():
    grid = GridSpec.for_strategy(ADAPTER, axes={"atr_mult": (0.5, 1.0), "rsi14": ((75, 25),),
                                                "rsi2": ((90, 10),)}, tp_r=(1.0, 2.0))
    out = add_robustness(_robust_df(ruined=[False, True, False, False]), grid, ADAPTER)
    assert out.loc[0, "robust_r"] == pytest.approx(3.5)      # row 1 (2.0) dropped -> median(3,4)
    assert out.loc[1, "robust_r"] == pytest.approx(0.0)      # ruined rows score 0
    assert out.loc[3, "robust_r"] == pytest.approx(2.0)      # median(1,3) with row 1 gone


def test_add_robustness_groups_by_all_four_rsi_levels():
    # Two RSI sets that share ob/f_hi but differ in os/f_lo must not pool their neighbours.
    grid = GridSpec.for_strategy(ADAPTER, axes={"atr_mult": (0.5, 1.0),
                                                "rsi14": ((75, 25), (75, 20)),
                                                "rsi2": ((90, 10), (90, 5))}, tp_r=(1.0, 2.0))
    df = pd.concat([_robust_df(), _robust_df(os=20.0, f_lo=5.0, is_avg_r=[10.0, 20.0, 30.0, 40.0])],
                   ignore_index=True)
    out = add_robustness(df, grid, ADAPTER)
    assert out.loc[0, "robust_r"] == pytest.approx(3.0)      # unaffected by the 10..40 block
    assert out.loc[4, "robust_r"] == pytest.approx(30.0)


def test_add_robustness_groups_by_rsi_fast_length():
    # RSI(2) and RSI(5) at the same levels are different strategies: never pool their neighbours.
    grid = GridSpec.for_strategy(ADAPTER, axes={"rsi_fast": (2, 5), "atr_mult": (0.5, 1.0),
                                                "rsi14": ((75, 25),), "rsi2": ((90, 10),)},
                                 tp_r=(1.0, 2.0))
    df = pd.concat([_robust_df(), _robust_df(rsi_fast=5, is_avg_r=[10.0, 20.0, 30.0, 40.0])],
                   ignore_index=True)
    out = add_robustness(df, grid, ADAPTER)
    assert out.loc[0, "robust_r"] == pytest.approx(3.0)
    assert out.loc[4, "robust_r"] == pytest.approx(30.0)


def test_grid_edge_flag():
    grid = GridSpec.for_strategy(ADAPTER, axes={"atr_mult": (0.0, 0.5, 1.0), "rsi14": ((75, 25),),
                                                "rsi2": ((90, 10),)}, tp_r=(1.0, 2.0, 3.0))
    df = pd.DataFrame({"tf": "M5", "rsi_fast": 2, "ob": 75.0, "os": 25.0, "f_hi": 90.0, "f_lo": 10.0,
                       "tp_r": [2.0, 1.0, 2.0, 3.0], "atr_mult": [0.5, 0.5, 0.0, 0.5],
                       "is_avg_r": 1.0, "ruined": False})
    edge = add_robustness(df, grid, ADAPTER)["grid_edge"].tolist()
    assert edge == [False, True, True, True]                 # interior, first tp, first atr, last tp


def test_compute_flags():
    r = pd.Series({"n_trades": 10, "is_avg_r": 0.5, "oos_avg_r": -0.2, "n_buy": 9, "n_sell": 1,
                   "oversized_share": 0.2, "capped_share": 0.3, "ruined": True, "grid_edge": True})
    assert compute_flags(r) == ["ruined", "n<30", "oos_sign_flip", "buy_sell_imbalance", "oversized",
                                "capped", "grid_edge"]
    ok = pd.Series({"n_trades": 50, "is_avg_r": 0.5, "oos_avg_r": 0.3, "n_buy": 20, "n_sell": 30,
                    "oversized_share": 0.0, "capped_share": 0.0, "ruined": False, "grid_edge": False})
    assert compute_flags(ok) == []


def test_segment_metrics_uses_the_real_equity_slice():
    # The account halves during IS, then digs a 40% hole inside OOS: 5000 -> 3000.
    idx = pd.date_range("2024-01-01", periods=6, freq="D", tz="UTC")
    eq = pd.Series([10_000.0, 8_000.0, 5_000.0, 5_000.0, 3_000.0, 4_000.0], index=idx)
    split = idx[3]
    trades = pd.DataFrame({"pnl_usd": [-1_000.0], "r_multiple": [-1.0], "bars_held": [1],
                           "direction": ["BUY"], "entry_time": [idx[4]], "exit_time": [idx[5]]})
    m = _segment_metrics(trades, eq[eq.index >= split], 10_000.0)
    assert m["max_dd_pct"] == pytest.approx(0.40)            # peak resets at the segment start
    assert m["max_dd_usd"] == pytest.approx(2_000.0)
    assert m["n_trades"] == 1 and m["net_pnl"] == pytest.approx(-1_000.0)
    is_m = _segment_metrics(trades.iloc[:0], eq[eq.index < split], 10_000.0)
    assert is_m["max_dd_pct"] == pytest.approx(0.50)


def _grid_df(rows):
    cols = {"tf": "M5", "rsi_fast": 2, "ob": 75.0, "os": 25.0, "f_hi": 90.0, "f_lo": 10.0,
            "atr_mult": 1.0, "tp_r": 2.0,
            "is_n_trades": 40, "oos_n_trades": 15, "is_avg_r": 0.3, "oos_avg_r": 0.2, "robust_r": 0.25,
            "oversized_share": 0.0, "capped_share": 0.0, "ruined": False, "grid_edge": False,
            "net_pnl": 1_500.0, "profit_factor": 1.4, "max_dd_pct": 0.1, "win_rate": 0.4,
            "n_buy": 20, "n_sell": 20, "n_trades": 55}
    return pd.DataFrame([cols | r for r in rows])


def test_recommend_none_when_nothing_qualifies():
    df = _grid_df([{"is_n_trades": 10}, {"oos_avg_r": -0.1}, {"oversized_share": 0.5},
                   {"oos_n_trades": 5}, {"capped_share": 0.8}])
    assert recommend(df, ADAPTER) == {"M5": None}


@pytest.mark.parametrize("bad", [{"net_pnl": -2_773.0}, {"profit_factor": 0.9}, {"max_dd_pct": 0.937},
                                 {"ruined": True}])
def test_recommend_rejects_money_losing_and_ruined_combos(bad):
    # C3: the delivered M5 pick had avg_r > 0 with net_pnl -$2,773 and a 93.7% drawdown.
    assert recommend(_grid_df([bad]), ADAPTER) == {"M5": None}
    assert recommend(_grid_df([{}]), ADAPTER)["M5"] is not None       # the same row without the defect passes


def test_recommend_picks_best_score_and_explains():
    # I1: OOS is a gate only. The OOS-best row (tp_r 1.0) is the worst on IS+robust and must
    # lose to the row that wins on those two.
    df = _grid_df([{"tp_r": 1.0, "oos_avg_r": 0.90, "robust_r": 0.10, "is_avg_r": 0.10},
                   {"tp_r": 2.0, "oos_avg_r": 0.20, "robust_r": 0.35, "is_avg_r": 0.40},
                   {"tp_r": 3.0, "oos_avg_r": 0.05, "robust_r": 0.05, "is_avg_r": 0.20}])
    rec = recommend(df, ADAPTER)["M5"]
    assert rec is not None and rec["params"]["tp_r"] == 2.0
    assert set(rec["params"]) == set(KEY_COLS)
    assert rec["params"]["rsi_fast"] == 2 and isinstance(rec["params"]["rsi_fast"], int)
    for token in ("net $", "PF ", "max DD", "OOS", "robust"):
        assert token in rec["reason"]


def test_reason_marks_a_grid_edge_pick():
    rec = recommend(_grid_df([{"grid_edge": True}]), ADAPTER)["M5"]
    assert rec["reason"].endswith("(grid edge)")


def test_gridspec_for_strategy_fills_defaults_and_rejects_unknown_axis():
    g = GridSpec.for_strategy(ADAPTER, axes={"atr_mult": (1.0,)})
    assert g.axes["rsi14"] == ADAPTER.default_axes["rsi14"]      # untouched axis keeps its default
    assert g.axes["atr_mult"] == (1.0,)
    assert g.tp_r == ADAPTER.default_tp_r
    with pytest.raises(KeyError):
        GridSpec.for_strategy(ADAPTER, axes={"ema": ((20, 100),)})


def test_combos_follow_adapter_axis_order():
    g = GridSpec.for_strategy(ADAPTER, axes={"rsi_fast": (2, 5), "rsi14": ((75.0, 25.0),),
                                             "rsi2": ((90.0, 10.0),), "atr_mult": (0.5, 1.0)},
                              tp_r=(1.0,))
    combos = list(g.combos(ADAPTER))
    assert len(combos) == 4
    assert list(combos[0]) == ["rsi_fast", "rsi14", "rsi2", "atr_mult"]
    assert [c["rsi_fast"] for c in combos] == [2, 2, 5, 5]       # first axis varies slowest


def test_grid_columns_come_from_the_adapter():
    df = run_optimization(ADAPTER, {"M5": _bars()}, {"M5": SPEC}, Rsi2SwingParams(), SMALL, COSTS, SIZING)
    for c in KEY_COLS:
        assert c in df.columns
    assert df["rsi_fast"].dtype.kind == "i"
    assert list(df.columns[:len(KEY_COLS) - 1]) == KEY_COLS[:-1] or set(KEY_COLS) <= set(df.columns)


def test_gridspec_is_immutable_and_hashable_by_identity():
    from dataclasses import FrozenInstanceError
    g = GridSpec.for_strategy(ADAPTER)
    with pytest.raises(FrozenInstanceError):
        g.tp_r = (1.0,)
    assert hash(g) == hash(g)               # identity hash, not a TypeError
    assert g != GridSpec.for_strategy(ADAPTER)   # eq=False -> identity comparison
