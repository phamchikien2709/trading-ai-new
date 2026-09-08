"""Grid optimisation with IS/OOS split, neighbourhood robustness and auto-recommendation (spec §4).

Two of the three variants are run-level switches rather than grid axes: `min_sl_spread_mult`
(V2) is an argument here, and the HTF trend gate (V3) travels on `base.htf_seconds`. Both are
recorded on every row (`min_sl_mult`, `n_rejected_min_sl`, `htf_seconds`) so a saved grid says
which filters produced it. The fast-RSI length (V1) is one of the strategy adapter's axes, reachable as `grid.axes["rsi_fast"]`.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, replace
from typing import Callable, Iterator, Sequence

import numpy as np
import pandas as pd

from ..bars import Bars
from ..params import CostParams, SizingParams, SymbolSpec
from ..signals import Signal
from ..strategies.registry import StrategyAdapter, get_adapter
from ..strategies.rsi2_swing import Rsi2SwingParams   # still used by make_params' annotation
from .engine import BacktestResult, run_backtest
from .metrics import compute_metrics, equity_from_trades, max_drawdown

# Column names now come from the strategy adapter; this constant is the rsi2_swing view of them,
# kept because the delivered reports and CSVs use it.
KEY_COLS = get_adapter("rsi2_swing").full_key_cols()
SPLIT_KEYS = ("n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct", "net_pnl", "expectancy_usd")

# Recommendation gates (spec §4.3). A combo has to be profitable in cash, not just in R:
# 107 of 675 combos in the first full run had avg_r > 0 while losing money, and the delivered
# M5 pick lost $2,773 at a 93.7% drawdown.
MIN_TRADES = 30
MIN_OOS_TRADES = 10
OVERSIZED_MAX = 0.10
CAPPED_MAX = 0.50
MAX_DD_CAP = 0.50
MIN_PROFIT_FACTOR = 1.0
# Score weights: OOS is a pass/fail gate only (spec §4.2 forbids optimising on it), so the
# ranking runs on in-sample expectancy and its neighbourhood robustness.
W_IS_AVG_R = 0.6
W_ROBUST_R = 0.4


@dataclass(frozen=True, eq=False)  # eq=False: identity-based equality/hash, not structural (axes dict is unhashable)
class GridSpec:
    """Grid as {axis name: values} plus the TP axis (spec §3.2).

    An axis value is a scalar (one column) or a tuple (several, e.g. `rsi2 = (90, 10)`).
    Signals are computed once per axis combination; the engine runs once per `tp_r`, because
    TP is the only axis that does not change the signal.
    """

    axes: dict[str, tuple]
    tp_r: tuple[float, ...]

    @classmethod
    def for_strategy(cls, adapter: StrategyAdapter, axes: dict | None = None,
                     tp_r: Sequence | None = None) -> "GridSpec":
        known = {a.name for a in adapter.axes}
        unknown = set(axes or {}) - known
        if unknown:
            raise KeyError(f"{adapter.name}: unknown axis {sorted(unknown)}; have {sorted(known)}")
        merged = {k: tuple(v) for k, v in adapter.default_axes.items()}
        merged.update({k: tuple(v) for k, v in (axes or {}).items()})
        return cls(axes=merged, tp_r=tuple(float(x) for x in (tp_r if tp_r is not None else adapter.default_tp_r)))

    def size(self) -> int:
        n = len(self.tp_r)
        for values in self.axes.values():
            n *= len(values)
        return n

    def combos(self, adapter: StrategyAdapter) -> Iterator[dict]:
        names = [a.name for a in adapter.axes]
        for values in itertools.product(*(self.axes[n] for n in names)):
            yield dict(zip(names, values))


def split_time(bars: Bars, is_frac: float) -> pd.Timestamp:
    idx = min(max(int(len(bars) * is_frac), 0), len(bars) - 1)
    return bars.datetimes()[idx]


def make_params(base: Rsi2SwingParams, ob: float, os_: float, f_hi: float, f_lo: float,
                atr_mult: float, rsi_fast: int | None = None) -> Rsi2SwingParams:
    params = replace(base, overbought=float(ob), oversold=float(os_), fast_hi=float(f_hi),
                     fast_lo=float(f_lo), atr_mult=float(atr_mult))
    return params if rsi_fast is None else replace(params, rsi_fast=int(rsi_fast))


def run_single(strategy: StrategyAdapter, bars: Bars, spec: SymbolSpec, params, tp_r: float,
               costs: CostParams, sizing: SizingParams, concurrency: str,
               min_sl_spread_mult: float = 0.0) -> tuple[list[Signal], BacktestResult]:
    signals = strategy.run(bars, params)
    return signals, run_backtest(bars, signals, float(tp_r), spec, costs, sizing, concurrency,
                                 min_sl_spread_mult=min_sl_spread_mult)


def _col(g: pd.DataFrame, name: str, default) -> pd.Series:
    """Column `name`, or a constant series when a caller-built frame predates it."""
    return g[name] if name in g.columns else pd.Series(default, index=g.index)


def _segment_metrics(trades_seg: pd.DataFrame, equity_slice: pd.Series, init: float) -> dict:
    """Trade-based metrics for one IS/OOS segment, with drawdown from the REAL equity curve.

    Rebuilding a segment's curve from its trades alone (`equity_from_trades`) restarts it at
    the initial equity, so the OOS drawdown of an account that had already halved came out
    far too small. The peak still resets at the segment start — the question a segment answers
    is "how deep a hole would this stretch have dug on its own".
    """
    m = compute_metrics(trades_seg, equity_from_trades(trades_seg, init), init)
    dd_usd, dd_pct = max_drawdown(equity_slice)
    m["max_dd_usd"], m["max_dd_pct"] = dd_usd, dd_pct
    return m


def run_optimization(strategy: StrategyAdapter, bars_by_tf: dict[str, Bars],
                     spec_by_tf: dict[str, SymbolSpec], base, grid: GridSpec, costs: CostParams,
                     sizing: SizingParams, concurrency: str = "hedge", is_frac: float = 0.7,
                     progress: Callable[[int, int], None] | None = None,
                     min_sl_spread_mult: float = 0.0) -> pd.DataFrame:
    total = grid.size() * len(bars_by_tf)
    init = sizing.initial_equity
    rows: list[dict] = []
    for tf, bars in bars_by_tf.items():
        split = split_time(bars, is_frac)
        n_bars = len(bars)
        spec = spec_by_tf[tf]
        for axis_values in grid.combos(strategy):
            params = strategy.make_params(base, axis_values)
            signals = strategy.run(bars, params)
            key_cols = strategy.columns_for(axis_values)
            for tp in grid.tp_r:
                res = run_backtest(bars, signals, float(tp), spec, costs, sizing, concurrency,
                                   min_sl_spread_mult=min_sl_spread_mult)
                tr = res.trades
                reasons = res.skipped["reason"] if len(res.skipped) else None
                n_blocked = int((reasons == "blocked").sum()) if reasons is not None else 0
                n_min_sl = int((reasons == "rejected_min_sl").sum()) if reasons is not None else 0
                full = compute_metrics(tr, res.equity, init, n_blocked=n_blocked, n_bars=n_bars)
                is_tr = tr[tr["entry_time"] < split]
                oos_tr = tr[tr["entry_time"] >= split]
                eq = res.equity
                is_m = _segment_metrics(is_tr, eq[eq.index < split], init)
                oos_m = _segment_metrics(oos_tr, eq[eq.index >= split], init)
                row = {"tf": tf, **key_cols, "tp_r": float(tp), "n_signals": len(signals),
                       "min_sl_mult": float(min_sl_spread_mult), "n_rejected_min_sl": n_min_sl,
                       "htf_seconds": int(getattr(base, "htf_seconds", 0)),
                       "split_time": split, "ruined": bool(res.ruined), "ruin_time": res.ruin_time,
                       "oversized_share": float(tr["oversized"].astype(bool).mean()) if len(tr) else 0.0,
                       "capped_share": float(tr["capped"].astype(bool).mean()) if len(tr) else 0.0}
                row.update(full)
                row.update({f"is_{k}": is_m[k] for k in SPLIT_KEYS})
                row.update({f"oos_{k}": oos_m[k] for k in SPLIT_KEYS})
                rows.append(row)
                if progress:
                    progress(len(rows), total)
    df = pd.DataFrame(rows)
    df["ruin_time"] = pd.to_datetime(df["ruin_time"], utc=True)   # NaT where the run survived
    df = add_robustness(df, grid, strategy)
    df["flags"] = df.apply(lambda r: ";".join(compute_flags(r)), axis=1)
    return df


def add_robustness(df: pd.DataFrame, grid: GridSpec, strategy: StrategyAdapter) -> pd.DataFrame:
    """Add `robust_r` / `robust_ratio` (neighbourhood plateau) and `grid_edge`.

    Neighbours share every grid axis except `tp_r` and the strategy's robust axis (`atr_mult`),
    and sit within one grid step of this combo on those two. Ruined combos are excluded from the
    pool (their `is_avg_r` is not a sample of anything a live account could have earned) and get
    `robust_r = 0` themselves.
    """
    df = df.reset_index(drop=True).copy()
    robust_col = strategy.axis(strategy.robust_axis).columns[0]
    tp_idx = {float(v): i for i, v in enumerate(grid.tp_r)}
    am_idx = {float(v): i for i, v in enumerate(grid.axes[strategy.robust_axis])}
    ti = df["tp_r"].astype(float).map(tp_idx).to_numpy()
    ai = df[robust_col].astype(float).map(am_idx).to_numpy()
    vals = df["is_avg_r"].astype(float).to_numpy()
    ruined = _col(df, "ruined", False).astype(bool).to_numpy()
    robust = np.full(len(df), np.nan)
    keys = [k for k in strategy.robust_cols if k in df.columns]   # caller-built frames may predate a key
    for _, g in df.groupby(keys, sort=False):
        idx = g.index.to_numpy()
        alive = idx[~ruined[idx]]
        for k in idx:
            if ruined[k]:
                continue
            mask = (np.abs(ti[alive] - ti[k]) <= 1) & (np.abs(ai[alive] - ai[k]) <= 1)
            mask &= alive != k
            if mask.any():
                robust[k] = float(np.median(vals[alive[mask]]))
    df["robust_r"] = np.nan_to_num(robust, nan=0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(vals > 0, np.clip(df["robust_r"].to_numpy() / vals, 0.0, 1.5), 0.0)
    df["robust_ratio"] = ratio
    edge_tp = {float(grid.tp_r[0]), float(grid.tp_r[-1])}
    am_values = grid.axes[strategy.robust_axis]
    edge_am = {float(am_values[0]), float(am_values[-1])}
    df["grid_edge"] = (df["tp_r"].astype(float).isin(edge_tp) | df[robust_col].astype(float).isin(edge_am))
    return df


def compute_flags(row) -> list[str]:
    flags: list[str] = []
    if bool(row.get("ruined", False)):
        flags.append("ruined")
    if row["n_trades"] < MIN_TRADES:
        flags.append("n<30")
    if row["is_avg_r"] > 0 and row["oos_avg_r"] < 0:
        flags.append("oos_sign_flip")
    nb, ns = int(row["n_buy"]), int(row["n_sell"])
    if (nb + ns) > 0 and max(nb, ns) / max(1, min(nb, ns)) > 2:
        flags.append("buy_sell_imbalance")
    if row["oversized_share"] > OVERSIZED_MAX:
        flags.append("oversized")
    if row.get("capped_share", 0.0) > OVERSIZED_MAX:
        flags.append("capped")
    if bool(row.get("grid_edge", False)):
        flags.append("grid_edge")
    return flags


def _zscore(s: pd.Series) -> pd.Series:
    sd = float(s.std(ddof=0))
    return (s - s.mean()) / sd if sd > 0 else s * 0.0


FILTER_TEXT = (f"not ruined, IS n >= {MIN_TRADES}, IS avg R > 0, OOS avg R > 0, "
               f"OOS n >= {MIN_OOS_TRADES}, net P&L > 0, profit factor > {MIN_PROFIT_FACTOR:g}, "
               f"max DD <= {MAX_DD_CAP:.0%}, oversized <= {OVERSIZED_MAX:.0%}, capped <= {CAPPED_MAX:.0%}")


def _reason(r: pd.Series) -> str:
    txt = (f"net ${r['net_pnl']:,.0f} · PF {r['profit_factor']:.2f} · max DD {r['max_dd_pct']:.1%} · "
           f"IS {int(r['is_n_trades'])} trades avg {r['is_avg_r']:+.2f}R · "
           f"OOS {int(r['oos_n_trades'])} trades avg {r['oos_avg_r']:+.2f}R · "
           f"robust_r {r['robust_r']:+.2f} · win rate {r['win_rate']:.0%} · "
           f"BUY/SELL {int(r['n_buy'])}/{int(r['n_sell'])}")
    if bool(r.get("capped_share", 0.0) > 0):
        txt += f" · capped {r['capped_share']:.0%}"
    if bool(r.get("grid_edge", False)):
        txt += " (grid edge)"
    return txt


def _param_value(row: pd.Series, key: str, int_cols: tuple[str, ...]):
    """One recommended parameter, typed: `tf` stays a string, lengths int, levels float."""
    if key == "tf":
        return row[key]
    return int(row[key]) if key in int_cols else float(row[key])


def recommend(df: pd.DataFrame, strategy: StrategyAdapter, min_trades: int = MIN_TRADES,
              min_oos_trades: int = MIN_OOS_TRADES) -> dict[str, dict | None]:
    """Top-1 combo per timeframe, or None when nothing clears the gates (spec §4.3).

    OOS is a gate, never part of the score: §4.2 says the OOS stretch is not to be optimised
    on, and weighting it 50% of the ranking was exactly that. Ranking is
    `W_IS_AVG_R * z(is_avg_r) + W_ROBUST_R * z(robust_r)` over the survivors of each TF, so a
    broad plateau beats a sharp peak.
    """
    out: dict[str, dict | None] = {}
    for tf, g in df.groupby("tf", sort=False):
        f = g[~_col(g, "ruined", False).astype(bool)
              & (g["is_n_trades"] >= min_trades)
              & (g["is_avg_r"] > 0)
              & (g["oos_avg_r"] > 0)
              & (_col(g, "oos_n_trades", min_oos_trades) >= min_oos_trades)
              & (g["net_pnl"] > 0)
              & (g["profit_factor"] > MIN_PROFIT_FACTOR)
              & (g["max_dd_pct"] <= MAX_DD_CAP)
              & (g["oversized_share"] <= OVERSIZED_MAX)
              & (_col(g, "capped_share", 0.0) <= CAPPED_MAX)]
        if f.empty:
            out[tf] = None
            continue
        score = (W_IS_AVG_R * _zscore(f["is_avg_r"].astype(float))
                 + W_ROBUST_R * _zscore(f["robust_r"].astype(float)))
        best = f.loc[score.idxmax()]
        out[tf] = {"params": {k: _param_value(best, k, strategy.int_cols) for k in strategy.full_key_cols()},
                   "score": float(score.max()), "row": best.to_dict(), "reason": _reason(best)}
    return out
