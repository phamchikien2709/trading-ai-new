"""Grid optimisation with IS/OOS split, neighbourhood robustness and auto-recommendation (spec §4)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

import numpy as np
import pandas as pd

from ..bars import Bars
from ..params import CostParams, SizingParams, SymbolSpec
from ..signals import Signal
from ..strategies.rsi2_swing import Rsi2SwingParams, run_strategy
from .engine import BacktestResult, run_backtest
from .metrics import compute_metrics, equity_from_trades, max_drawdown

KEY_COLS = ["tf", "rsi_fast", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r"]
SPLIT_KEYS = ("n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct", "net_pnl", "expectancy_usd")
ROBUST_KEYS = ["tf", "rsi_fast", "ob", "os", "f_hi", "f_lo"]
INT_KEY_COLS = ("rsi_fast",)

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


@dataclass(frozen=True)
class GridSpec:
    tp_r: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 4.0)
    atr_mult: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0)
    rsi_slow_levels: tuple[tuple[float, float], ...] = ((70.0, 30.0), (75.0, 25.0), (80.0, 20.0))
    rsi_fast_levels: tuple[tuple[float, float], ...] = ((85.0, 15.0), (90.0, 10.0), (95.0, 5.0))
    # V1: the structure-RSI *length* is an axis too. On M5 the RSI(2) stop sits within a few
    # spreads of price; a longer fast RSI marks wider swings, and length 5 was the first
    # setting with positively-robust results.
    rsi_fast: tuple[int, ...] = (2,)

    def size(self) -> int:
        return (len(self.tp_r) * len(self.atr_mult) * len(self.rsi_slow_levels)
                * len(self.rsi_fast_levels) * len(self.rsi_fast))


def split_time(bars: Bars, is_frac: float) -> pd.Timestamp:
    idx = min(max(int(len(bars) * is_frac), 0), len(bars) - 1)
    return bars.datetimes()[idx]


def make_params(base: Rsi2SwingParams, ob: float, os_: float, f_hi: float, f_lo: float,
                atr_mult: float, rsi_fast: int | None = None) -> Rsi2SwingParams:
    params = replace(base, overbought=float(ob), oversold=float(os_), fast_hi=float(f_hi),
                     fast_lo=float(f_lo), atr_mult=float(atr_mult))
    return params if rsi_fast is None else replace(params, rsi_fast=int(rsi_fast))


def run_single(bars: Bars, spec: SymbolSpec, params: Rsi2SwingParams, tp_r: float, costs: CostParams,
               sizing: SizingParams, concurrency: str,
               min_sl_spread_mult: float = 0.0) -> tuple[list[Signal], BacktestResult]:
    signals = run_strategy(bars, params)
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


def run_optimization(bars_by_tf: dict[str, Bars], spec_by_tf: dict[str, SymbolSpec], base: Rsi2SwingParams,
                     grid: GridSpec, costs: CostParams, sizing: SizingParams, concurrency: str = "hedge",
                     is_frac: float = 0.7, progress: Callable[[int, int], None] | None = None,
                     min_sl_spread_mult: float = 0.0) -> pd.DataFrame:
    total = grid.size() * len(bars_by_tf)
    init = sizing.initial_equity
    rows: list[dict] = []
    for tf, bars in bars_by_tf.items():
        split = split_time(bars, is_frac)
        n_bars = len(bars)
        spec = spec_by_tf[tf]
        for rf_len in grid.rsi_fast:
            for ob, os_ in grid.rsi_slow_levels:
                for f_hi, f_lo in grid.rsi_fast_levels:
                    for am in grid.atr_mult:
                        params = make_params(base, ob, os_, f_hi, f_lo, am, rsi_fast=rf_len)
                        signals = run_strategy(bars, params)
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
                            row = {"tf": tf, "rsi_fast": int(rf_len), "ob": float(ob), "os": float(os_),
                                   "f_hi": float(f_hi), "f_lo": float(f_lo),
                                   "atr_mult": float(am), "tp_r": float(tp), "n_signals": len(signals),
                                   "min_sl_mult": float(min_sl_spread_mult), "n_rejected_min_sl": n_min_sl,
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
    df = add_robustness(df, grid)
    df["flags"] = df.apply(lambda r: ";".join(compute_flags(r)), axis=1)
    return df


def add_robustness(df: pd.DataFrame, grid: GridSpec) -> pd.DataFrame:
    """Add `robust_r` / `robust_ratio` (neighbourhood plateau) and `grid_edge`.

    Neighbours are the combos with the same fast-RSI length and the same RSI level set (all four
    levels — grouping on `ob`/`f_hi` alone silently pooled different `os`/`f_lo` sets) that sit
    within one grid step of this combo in `tp_r` and `atr_mult`. Ruined combos are excluded from the pool
    (their `is_avg_r` is not a sample of anything a live account could have earned) and get
    `robust_r = 0` themselves.
    """
    df = df.reset_index(drop=True).copy()
    tp_idx = {float(v): i for i, v in enumerate(grid.tp_r)}
    am_idx = {float(v): i for i, v in enumerate(grid.atr_mult)}
    ti = df["tp_r"].astype(float).map(tp_idx).to_numpy()
    ai = df["atr_mult"].astype(float).map(am_idx).to_numpy()
    vals = df["is_avg_r"].astype(float).to_numpy()
    ruined = _col(df, "ruined", False).astype(bool).to_numpy()
    robust = np.full(len(df), np.nan)
    keys = [k for k in ROBUST_KEYS if k in df.columns]      # caller-built frames may predate a key
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
    edge_am = {float(grid.atr_mult[0]), float(grid.atr_mult[-1])}
    df["grid_edge"] = (df["tp_r"].astype(float).isin(edge_tp) | df["atr_mult"].astype(float).isin(edge_am))
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


def _param_value(row: pd.Series, key: str):
    """One recommended parameter, typed: `tf` stays a string, lengths int, levels float."""
    if key == "tf":
        return row[key]
    return int(row[key]) if key in INT_KEY_COLS else float(row[key])


def recommend(df: pd.DataFrame, min_trades: int = MIN_TRADES,
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
        out[tf] = {"params": {k: _param_value(best, k) for k in KEY_COLS},
                   "score": float(score.max()), "row": best.to_dict(), "reason": _reason(best)}
    return out
