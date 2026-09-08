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
from .metrics import compute_metrics, equity_from_trades

KEY_COLS = ["tf", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r"]
SPLIT_KEYS = ("n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct", "net_pnl", "expectancy_usd")
MIN_TRADES = 30
OVERSIZED_MAX = 0.10


@dataclass(frozen=True)
class GridSpec:
    tp_r: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 4.0)
    atr_mult: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0)
    rsi_slow_levels: tuple[tuple[float, float], ...] = ((70.0, 30.0), (75.0, 25.0), (80.0, 20.0))
    rsi_fast_levels: tuple[tuple[float, float], ...] = ((85.0, 15.0), (90.0, 10.0), (95.0, 5.0))

    def size(self) -> int:
        return len(self.tp_r) * len(self.atr_mult) * len(self.rsi_slow_levels) * len(self.rsi_fast_levels)


def split_time(bars: Bars, is_frac: float) -> pd.Timestamp:
    idx = min(max(int(len(bars) * is_frac), 0), len(bars) - 1)
    return bars.datetimes()[idx]


def make_params(base: Rsi2SwingParams, ob: float, os_: float, f_hi: float, f_lo: float,
                atr_mult: float) -> Rsi2SwingParams:
    return replace(base, overbought=float(ob), oversold=float(os_), fast_hi=float(f_hi),
                   fast_lo=float(f_lo), atr_mult=float(atr_mult))


def run_single(bars: Bars, spec: SymbolSpec, params: Rsi2SwingParams, tp_r: float, costs: CostParams,
               sizing: SizingParams, concurrency: str) -> tuple[list[Signal], BacktestResult]:
    signals = run_strategy(bars, params)
    return signals, run_backtest(bars, signals, float(tp_r), spec, costs, sizing, concurrency)


def run_optimization(bars_by_tf: dict[str, Bars], spec_by_tf: dict[str, SymbolSpec], base: Rsi2SwingParams,
                     grid: GridSpec, costs: CostParams, sizing: SizingParams, concurrency: str = "hedge",
                     is_frac: float = 0.7, progress: Callable[[int, int], None] | None = None) -> pd.DataFrame:
    total = grid.size() * len(bars_by_tf)
    init = sizing.initial_equity
    rows: list[dict] = []
    for tf, bars in bars_by_tf.items():
        split = split_time(bars, is_frac)
        n_bars = len(bars)
        spec = spec_by_tf[tf]
        for ob, os_ in grid.rsi_slow_levels:
            for f_hi, f_lo in grid.rsi_fast_levels:
                for am in grid.atr_mult:
                    params = make_params(base, ob, os_, f_hi, f_lo, am)
                    signals = run_strategy(bars, params)
                    for tp in grid.tp_r:
                        res = run_backtest(bars, signals, float(tp), spec, costs, sizing, concurrency)
                        tr = res.trades
                        n_blocked = int((res.skipped["reason"] == "blocked").sum()) if len(res.skipped) else 0
                        full = compute_metrics(tr, res.equity, init, n_blocked=n_blocked, n_bars=n_bars)
                        is_tr = tr[tr["entry_time"] < split]
                        oos_tr = tr[tr["entry_time"] >= split]
                        is_m = compute_metrics(is_tr, equity_from_trades(is_tr, init), init)
                        oos_m = compute_metrics(oos_tr, equity_from_trades(oos_tr, init), init)
                        row = {"tf": tf, "ob": float(ob), "os": float(os_), "f_hi": float(f_hi), "f_lo": float(f_lo),
                               "atr_mult": float(am), "tp_r": float(tp), "n_signals": len(signals),
                               "split_time": split,
                               "oversized_share": float(tr["oversized"].astype(bool).mean()) if len(tr) else 0.0}
                        row.update(full)
                        row.update({f"is_{k}": is_m[k] for k in SPLIT_KEYS})
                        row.update({f"oos_{k}": oos_m[k] for k in SPLIT_KEYS})
                        rows.append(row)
                        if progress:
                            progress(len(rows), total)
    df = pd.DataFrame(rows)
    df = add_robustness(df, grid)
    df["flags"] = df.apply(lambda r: ";".join(compute_flags(r)), axis=1)
    return df


def add_robustness(df: pd.DataFrame, grid: GridSpec) -> pd.DataFrame:
    df = df.reset_index(drop=True).copy()
    tp_idx = {float(v): i for i, v in enumerate(grid.tp_r)}
    am_idx = {float(v): i for i, v in enumerate(grid.atr_mult)}
    ti = df["tp_r"].astype(float).map(tp_idx).to_numpy()
    ai = df["atr_mult"].astype(float).map(am_idx).to_numpy()
    vals = df["is_avg_r"].astype(float).to_numpy()
    robust = np.full(len(df), np.nan)
    for _, g in df.groupby(["tf", "ob", "f_hi"], sort=False):
        idx = g.index.to_numpy()
        for k in idx:
            mask = (np.abs(ti[idx] - ti[k]) <= 1) & (np.abs(ai[idx] - ai[k]) <= 1)
            mask &= idx != k
            if mask.any():
                robust[k] = float(np.median(vals[idx[mask]]))
    df["robust_r"] = np.nan_to_num(robust, nan=0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(vals > 0, np.clip(df["robust_r"].to_numpy() / vals, 0.0, 1.5), 0.0)
    df["robust_ratio"] = ratio
    return df


def compute_flags(row) -> list[str]:
    flags: list[str] = []
    if row["n_trades"] < MIN_TRADES:
        flags.append("n<30")
    if row["is_avg_r"] > 0 and row["oos_avg_r"] < 0:
        flags.append("oos_sign_flip")
    nb, ns = int(row["n_buy"]), int(row["n_sell"])
    if (nb + ns) > 0 and max(nb, ns) / max(1, min(nb, ns)) > 2:
        flags.append("buy_sell_imbalance")
    if row["oversized_share"] > OVERSIZED_MAX:
        flags.append("oversized")
    return flags


def _zscore(s: pd.Series) -> pd.Series:
    sd = float(s.std(ddof=0))
    return (s - s.mean()) / sd if sd > 0 else s * 0.0


def _reason(r: pd.Series) -> str:
    return (f"IS {int(r['is_n_trades'])} trades avg {r['is_avg_r']:+.2f}R · "
            f"OOS {int(r['oos_n_trades'])} trades avg {r['oos_avg_r']:+.2f}R · "
            f"robust_r {r['robust_r']:+.2f} · max DD {r['max_dd_pct']:.1%} · "
            f"win rate {r['win_rate']:.0%} · BUY/SELL {int(r['n_buy'])}/{int(r['n_sell'])}")


def recommend(df: pd.DataFrame, min_trades: int = MIN_TRADES) -> dict[str, dict | None]:
    out: dict[str, dict | None] = {}
    for tf, g in df.groupby("tf", sort=False):
        f = g[(g["is_n_trades"] >= min_trades) & (g["is_avg_r"] > 0) & (g["oos_avg_r"] > 0)
              & (g["oversized_share"] <= OVERSIZED_MAX)]
        if f.empty:
            out[tf] = None
            continue
        score = 0.5 * _zscore(f["oos_avg_r"].astype(float)) + 0.3 * _zscore(f["robust_r"].astype(float)) \
            + 0.2 * _zscore(f["is_avg_r"].astype(float))
        best = f.loc[score.idxmax()]
        out[tf] = {"params": {k: (best[k] if k == "tf" else float(best[k])) for k in KEY_COLS},
                   "score": float(score.max()), "row": best.to_dict(), "reason": _reason(best)}
    return out
