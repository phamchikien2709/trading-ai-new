"""Grid-optimise a registered strategy on cached MT5 data and export xlsx + html.

Usage:
  python scripts/optimize.py --strategy rsi2_ema_swing --tf M5 M15 H1 --risk 1
  python scripts/optimize.py --strategy rsi2_ema_swing --tf M5 --axis ema=20/100,50/200 --tp 4 8
  python scripts/optimize.py --strategy rsi2_swing --tf M15 --axis rsi14=80/20 --htf 3600

An axis not named on the command line keeps the strategy's default values. Pairs are written
`a/b` (`--axis ema=20/100`, `--axis rsi2=95/5`). `--list-axes` prints what a strategy accepts.
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

from rsi_fvg.backtest.export import write_csvs, write_html, write_xlsx  # noqa: E402
from rsi_fvg.backtest.optimize import GridSpec, recommend, run_optimization, run_single  # noqa: E402
from rsi_fvg.bars import Bars  # noqa: E402
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.params import load_config  # noqa: E402
from rsi_fvg.strategies.registry import STRATEGIES, get_adapter  # noqa: E402


def parse_axis(text: str) -> tuple[str, tuple]:
    """`ema=20/100,50/200` -> ("ema", ((20.0, 100.0), (50.0, 200.0)))."""
    if "=" not in text:
        raise argparse.ArgumentTypeError(f"expected name=v1,v2 — got {text!r}")
    name, values = text.split("=", 1)
    out = []
    for chunk in values.split(","):
        chunk = chunk.strip()
        if not chunk:
            raise argparse.ArgumentTypeError(f"axis {name}: empty value in {text!r}")
        try:
            out.append(tuple(float(x) for x in chunk.split("/")) if "/" in chunk else float(chunk))
        except ValueError as e:
            raise argparse.ArgumentTypeError(f"axis {name}: {chunk!r} is not a number") from e
    return name.strip(), tuple(out)


def build_base(adapter, htf_seconds: int, max_wait: int):
    """Params object with the run-level switches applied, skipping fields it does not have."""
    have = {f.name for f in fields(adapter.params_cls)}
    overrides = {k: v for k, v in (("htf_seconds", htf_seconds), ("max_wait", max_wait)) if k in have}
    return replace(adapter.params_cls(), **overrides)


def _git_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strategy", default="rsi2_ema_swing", choices=sorted(STRATEGIES))
    ap.add_argument("--list-axes", action="store_true", help="print the strategy's axes and defaults, then exit")
    ap.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    ap.add_argument("--symbol")
    ap.add_argument("--tf", nargs="*")
    ap.add_argument("--axis", action="append", default=[], metavar="NAME=V1,V2",
                    help="override one grid axis; repeatable. Pairs are a/b")
    ap.add_argument("--tp", nargs="*", type=float)
    ap.add_argument("--risk", type=float, default=1.0)
    ap.add_argument("--concurrency", choices=["hedge", "single"], default="hedge")
    ap.add_argument("--min-sl-mult", type=float, default=0.0,
                    help="skip signals whose SL is closer than this many spreads (0 = off)")
    ap.add_argument("--htf", type=int, default=0, help="higher-timeframe RSI trend gate, in seconds (0 = off)")
    ap.add_argument("--max-wait", type=int, default=0, help="rsi2_swing only: bars from flag to entry (0 = off)")
    ap.add_argument("--is-frac", type=float, default=0.7)
    ap.add_argument("--data-dir", default=str(ROOT / "data"),
                    help="parquet cache dir; a missing cache triggers a live MT5 fetch of full history")
    ap.add_argument("--out", default=None, help="default results/<strategy>")
    ap.add_argument("--offline", action="store_true", help="embed plotly.js in the html")
    a = ap.parse_args()

    adapter = get_adapter(a.strategy)
    if a.list_axes:
        print(f"{adapter.name} axes:")
        for ax in adapter.axes:
            print(f"  {ax.name:<10} -> columns {list(ax.columns)}  default {adapter.default_axes[ax.name]}")
        print(f"  tp_r       -> default {adapter.default_tp_r}")
        return 0

    try:
        axes = dict(parse_axis(t) for t in a.axis)
    except argparse.ArgumentTypeError as e:
        ap.error(str(e))
    try:
        grid = GridSpec.for_strategy(adapter, axes=axes or None, tp_r=a.tp)   # raises KeyError on a bad axis
    except KeyError as e:
        ap.error(str(e))
    cfg = load_config(a.config)
    symbol = a.symbol or cfg.symbol
    tfs = a.tf or cfg.timeframes
    sizing = replace(cfg.sizing, risk_pct=a.risk)
    base = build_base(adapter, a.htf, a.max_wait)

    bars_by_tf, spec_by_tf, ranges = {}, {}, {}
    for tf in tfs:
        df, spec = load_or_fetch(symbol, tf, Path(a.data_dir), fallback_spec=cfg.spec_fallback)
        bars = Bars.from_dataframe(df)
        bars_by_tf[tf], spec_by_tf[tf] = bars, spec
        dt = bars.datetimes()
        ranges[tf] = (f"{dt[0]:%Y-%m-%d}", f"{dt[-1]:%Y-%m-%d}")
        print(f"{tf}: {len(bars):,d} bars usable {ranges[tf][0]} -> {ranges[tf][1]}  point={spec.point}")

    t0 = time.time()
    last = {"pct": -1}

    def progress(done: int, total: int) -> None:
        pct = done * 100 // total
        if pct // 5 != last["pct"] // 5:
            last["pct"] = pct
            print(f"  {done}/{total} ({pct}%)  {time.time() - t0:.0f}s", flush=True)

    print(f"{adapter.name}: grid {grid.size()} combos x {len(tfs)} TF")
    grid_df = run_optimization(adapter, bars_by_tf, spec_by_tf, base, grid, cfg.costs, sizing,
                               a.concurrency, is_frac=a.is_frac, progress=progress,
                               min_sl_spread_mult=a.min_sl_mult)
    rec = recommend(grid_df, adapter)

    rec_results = {}
    for tf, r in rec.items():
        if r is None:
            continue
        axis_values = {ax.name: (tuple(r["params"][c] for c in ax.columns) if len(ax.columns) > 1
                                 else r["params"][ax.columns[0]]) for ax in adapter.axes}
        params = adapter.make_params(base, axis_values)
        _, res = run_single(adapter, bars_by_tf[tf], spec_by_tf[tf], params, r["params"]["tp_r"],
                            cfg.costs, sizing, a.concurrency, min_sl_spread_mult=a.min_sl_mult)
        rec_results[tf] = res

    run_info = {"strategy": adapter.name, "symbol": symbol, "timeframes": tfs, "data_range": ranges,
                "initial_equity": sizing.initial_equity, "risk_pct": sizing.risk_pct,
                "concurrency": a.concurrency, "spread_points": cfg.costs.spread_points,
                "commission_per_lot_rt": cfg.costs.commission_per_lot_rt,
                "slippage_points": cfg.costs.slippage_points, "is_frac": a.is_frac,
                "min_sl_mult": a.min_sl_mult, "htf_seconds": a.htf, "max_wait": a.max_wait,
                "grid": {**{k: list(v) for k, v in grid.axes.items()}, "tp_r": list(grid.tp_r)},
                "git_hash": _git_hash(), "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}

    out_root = Path(a.out) if a.out else ROOT / "results" / adapter.name
    out_dir = out_root / datetime.now().strftime("%Y%m%d_%H%M%S")
    write_csvs(out_dir, grid_df, rec_results, run_info)
    write_xlsx(out_dir / f"report_{symbol}.xlsx", grid_df, rec, rec_results, run_info)
    write_html(out_dir / f"report_{symbol}.html", grid_df, rec, rec_results, run_info, offline=a.offline)

    pd.set_option("display.width", 240)
    print("\n=== Recommendation ===")
    n_ruined = int(grid_df["ruined"].sum()) if "ruined" in grid_df.columns else 0
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
    cols = adapter.full_key_cols() + ["n_trades", "win_rate", "avg_r", "profit_factor", "net_pnl",
                                      "max_dd_pct", "is_avg_r", "oos_avg_r", "robust_r", "ruined", "flags"]
    for tf, g in grid_df.groupby("tf", sort=False):
        print(f"\n--- {tf}: top 5 by IS avg R (then robust_r) ---")
        print(g.sort_values(["is_avg_r", "robust_r"], ascending=False)[cols].head(5).to_string(index=False))
    print(f"\nwritten: {out_dir}  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
