"""Rebuild the xlsx/html reports of a finished run from its `grid.csv`, in place.

A grid run costs 12-25 minutes, so an export bug must not force a re-run. This reads the
`grid.csv` a run already wrote, redoes `recommend()`, re-runs only the recommended combo per
timeframe (one `run_single` each, seconds not minutes) and overwrites the reports in the same
folder. It also reprints the `=== Recommendation ===` block and the per-timeframe top-5 table,
so a crashed run's console output can be recovered too.

Usage:
  python scripts/rerender.py results/rsi2_ema_swing/20260908_220458
  python scripts/rerender.py results/rsi2_ema_swing/20260908_220458 --offline
  python scripts/rerender.py <run-dir> --strategy rsi2_swing --risk 5

The strategy comes from `--strategy` or, failing that, from the run folder's parent directory
name (`results/<strategy>/<timestamp>`), validated against the registry.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import fields, replace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from rsi_fvg.backtest.export import write_html, write_xlsx  # noqa: E402
from rsi_fvg.backtest.optimize import recommend, run_single  # noqa: E402
from rsi_fvg.bars import Bars  # noqa: E402
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.params import load_config  # noqa: E402
from rsi_fvg.strategies.registry import STRATEGIES, get_adapter  # noqa: E402


def infer_strategy(run_dir: Path) -> str:
    """`results/<strategy>/<timestamp>` -> "<strategy>", validated against the registry."""
    name = run_dir.resolve().parent.name
    if name not in STRATEGIES:
        raise SystemExit(f"cannot tell the strategy from {run_dir}: its parent directory is "
                         f"{name!r}, which is not a registered strategy ({sorted(STRATEGIES)}). "
                         f"Pass --strategy explicitly.")
    return name


def build_base(adapter, htf_seconds: int, max_wait: int):
    """Params object with the run-level switches applied, skipping fields it does not have.

    Same rule as scripts/optimize.py's build_base — kept in step deliberately, so a rerender
    reconstructs the params the original run used.
    """
    have = {f.name for f in fields(adapter.params_cls)}
    overrides = {k: v for k, v in (("htf_seconds", htf_seconds), ("max_wait", max_wait)) if k in have}
    return replace(adapter.params_cls(), **overrides)


def axis_values_for(adapter, params: dict) -> dict:
    """Rebuild {axis name: value} from a recommendation's params, as optimize.py does."""
    return {ax.name: (tuple(params[c] for c in ax.columns) if len(ax.columns) > 1
                      else params[ax.columns[0]]) for ax in adapter.axes}


def _git_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _first_row_value(grid_df: pd.DataFrame, column: str, fallback):
    if column not in grid_df.columns or grid_df.empty:
        return fallback
    v = grid_df[column].iloc[0]
    return fallback if pd.isna(v) else v


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", help="a finished run folder containing grid.csv; the reports are overwritten there")
    ap.add_argument("--strategy", choices=sorted(STRATEGIES),
                    help="default: inferred from the run folder's parent directory name")
    ap.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    ap.add_argument("--symbol", help="default: the config's symbol")
    ap.add_argument("--risk", type=float, default=1.0, help="risk %% per trade (optimize.py default)")
    ap.add_argument("--concurrency", choices=["hedge", "single"], default="hedge")
    ap.add_argument("--min-sl-mult", type=float, default=None,
                    help="skip signals whose SL is closer than this many spreads. Default: the "
                         "min_sl_mult recorded on grid.csv's first row (every row of a run shares it)")
    ap.add_argument("--htf", type=int, default=None,
                    help="higher-timeframe RSI trend gate, in seconds. Default: the htf_seconds "
                         "recorded on grid.csv's first row (every row of a run shares it)")
    ap.add_argument("--max-wait", type=int, default=0, help="rsi2_swing only: bars from flag to entry (0 = off)")
    ap.add_argument("--data-dir", default=str(ROOT / "data"),
                    help="parquet cache dir; a missing cache triggers a live MT5 fetch of full history")
    ap.add_argument("--offline", action="store_true", help="embed plotly.js in the html")
    a = ap.parse_args(argv)

    run_dir = Path(a.run_dir)
    grid_csv = run_dir / "grid.csv"
    if not grid_csv.exists():
        ap.error(f"no grid.csv in {run_dir}")
    adapter = get_adapter(a.strategy) if a.strategy else get_adapter(infer_strategy(run_dir))

    t0 = time.time()
    grid_df = pd.read_csv(grid_csv)
    if grid_df.empty:
        ap.error(f"{grid_csv} has no rows")
    for col in ("split_time", "ruin_time"):
        if col in grid_df.columns:
            grid_df[col] = pd.to_datetime(grid_df[col], utc=True, errors="coerce")
    grid_df["flags"] = grid_df["flags"].fillna("").astype(str) if "flags" in grid_df.columns else ""
    for col in ("ruined", "grid_edge"):     # read_csv gives bool for clean columns, object with a NaN
        if col in grid_df.columns and grid_df[col].dtype != bool:
            grid_df[col] = grid_df[col].map({"True": True, "False": False, True: True, False: False}).fillna(False).astype(bool)

    # min_sl_mult / htf_seconds are run-level switches recorded identically on every row.
    min_sl_mult = float(a.min_sl_mult if a.min_sl_mult is not None
                        else _first_row_value(grid_df, "min_sl_mult", 0.0))
    htf_seconds = int(a.htf if a.htf is not None else _first_row_value(grid_df, "htf_seconds", 0))

    cfg = load_config(a.config)
    symbol = a.symbol or cfg.symbol
    sizing = replace(cfg.sizing, risk_pct=a.risk)
    base = build_base(adapter, htf_seconds, a.max_wait)
    print(f"{adapter.name}: {len(grid_df)} grid rows from {grid_csv} "
          f"(min_sl_mult={min_sl_mult:g}, htf_seconds={htf_seconds})")

    rec = recommend(grid_df, adapter)

    tfs = list(dict.fromkeys(grid_df["tf"].astype(str)))
    # Bars are loaded only for the timeframes that produced a recommendation — the whole point
    # is to avoid the original run's cost — so `data_range` covers those, not every tf in tfs.
    ranges: dict[str, tuple[str, str]] = {}
    rec_results = {}
    for tf, r in rec.items():
        if r is None:
            continue
        df, spec = load_or_fetch(symbol, tf, Path(a.data_dir), fallback_spec=cfg.spec_fallback)
        bars = Bars.from_dataframe(df)
        dt = bars.datetimes()
        ranges[tf] = (f"{dt[0]:%Y-%m-%d}", f"{dt[-1]:%Y-%m-%d}")
        print(f"{tf}: {len(bars):,d} bars usable {ranges[tf][0]} -> {ranges[tf][1]}  point={spec.point}")
        params = adapter.make_params(base, axis_values_for(adapter, r["params"]))
        _, res = run_single(adapter, bars, spec, params, r["params"]["tp_r"], cfg.costs, sizing,
                            a.concurrency, min_sl_spread_mult=min_sl_mult)
        rec_results[tf] = res

    grid_axes = {c: sorted(grid_df[c].dropna().unique().tolist())
                 for c in adapter.key_cols if c in grid_df.columns}
    run_info = {"strategy": adapter.name, "symbol": symbol, "timeframes": tfs, "data_range": ranges,
                "initial_equity": sizing.initial_equity, "risk_pct": sizing.risk_pct,
                "concurrency": a.concurrency, "spread_points": cfg.costs.spread_points,
                "commission_per_lot_rt": cfg.costs.commission_per_lot_rt,
                "slippage_points": cfg.costs.slippage_points,
                "min_sl_mult": min_sl_mult, "htf_seconds": htf_seconds,
                **({"max_wait": a.max_wait} if "max_wait" in {f.name for f in fields(adapter.params_cls)} else {}),
                "grid": {**grid_axes, "tp_r": sorted(grid_df["tp_r"].unique().tolist())},
                "rerendered_from": str(grid_csv), "git_hash": _git_hash(),
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}

    write_xlsx(run_dir / f"report_{symbol}.xlsx", grid_df, rec, rec_results, run_info)
    write_html(run_dir / f"report_{symbol}.html", grid_df, rec, rec_results, run_info, offline=a.offline)

    pd.set_option("display.width", 240)
    print("\n=== Recommendation ===")
    n_ruined = int(grid_df["ruined"].astype(bool).sum()) if "ruined" in grid_df.columns else 0
    if n_ruined:
        print(f"note: {n_ruined} of {len(grid_df)} combos blew the account (equity <= 10% of start) and were excluded")
    for tf, r in rec.items():
        if r is None:
            print(f"{tf}: no reliable parameter set")
        else:
            shown = " ".join(f"{k} {v:g}" if isinstance(v, float) else f"{k} {v}"
                             for k, v in r["params"].items() if k != "tf")
            print(f"{tf}: {shown}")
            print(f"     {r['reason']}")
    cols = [c for c in adapter.full_key_cols() + ["n_trades", "win_rate", "avg_r", "profit_factor",
                                                  "net_pnl", "max_dd_pct", "is_avg_r", "oos_avg_r",
                                                  "robust_r", "ruined", "flags"] if c in grid_df.columns]
    for tf, g in grid_df.groupby("tf", sort=False):
        print(f"\n--- {tf}: top 5 by IS avg R (then robust_r) ---")
        print(g.sort_values(["is_avg_r", "robust_r"], ascending=False)[cols].head(5).to_string(index=False))
    print(f"\nrewritten: {run_dir}  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
