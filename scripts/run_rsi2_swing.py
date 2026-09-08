"""Grid-optimise the RSI2 swing strategy on cached MT5 data and export xlsx + html.

Usage:
  python scripts/run_rsi2_swing.py                                   # full grid, M5 M15 H1, risk 5%
  python scripts/run_rsi2_swing.py --tf M15 --tp 2 3 --atr-mult 1 1.5 --rsi14 75/25 --rsi2 90/10
  python scripts/run_rsi2_swing.py --concurrency single --offline    # Pine-comparable, self-contained html
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from rsi_fvg.backtest.export import write_csvs, write_html, write_xlsx  # noqa: E402
from rsi_fvg.backtest.optimize import (KEY_COLS, GridSpec, make_params, recommend,  # noqa: E402
                                       run_optimization, run_single)
from rsi_fvg.bars import Bars  # noqa: E402
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.params import load_config  # noqa: E402
from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams  # noqa: E402


def _pairs(values: list[str]) -> tuple[tuple[float, float], ...]:
    out = []
    for v in values:
        a, b = v.split("/")
        out.append((float(a), float(b)))
    return tuple(out)


def _git_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    ap.add_argument("--symbol")
    ap.add_argument("--tf", nargs="*")
    ap.add_argument("--risk", type=float, default=5.0)
    ap.add_argument("--concurrency", choices=["hedge", "single"], default="hedge")
    ap.add_argument("--tp", nargs="*", type=float, default=[1, 1.5, 2, 3, 4])
    ap.add_argument("--atr-mult", nargs="*", type=float, default=[0, 0.5, 1, 1.5, 2])
    ap.add_argument("--rsi14", nargs="*", default=["70/30", "75/25", "80/20"])
    ap.add_argument("--rsi2", nargs="*", default=["85/15", "90/10", "95/5"])
    ap.add_argument("--max-wait", type=int, default=0)
    ap.add_argument("--is-frac", type=float, default=0.7)
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--out", default=str(ROOT / "results" / "rsi2_swing"))
    ap.add_argument("--offline", action="store_true", help="embed plotly.js in the html (bigger file, works without internet)")
    a = ap.parse_args()

    cfg = load_config(a.config)
    symbol = a.symbol or cfg.symbol
    tfs = a.tf or cfg.timeframes
    sizing = replace(cfg.sizing, risk_pct=a.risk)
    grid = GridSpec(tp_r=tuple(float(x) for x in a.tp), atr_mult=tuple(float(x) for x in a.atr_mult),
                    rsi_slow_levels=_pairs(a.rsi14), rsi_fast_levels=_pairs(a.rsi2))
    base = Rsi2SwingParams(max_wait=a.max_wait)

    bars_by_tf, spec_by_tf, ranges = {}, {}, {}
    for tf in tfs:
        df, spec = load_or_fetch(symbol, tf, Path(a.data_dir), fallback_spec=cfg.spec_fallback)
        bars = Bars.from_dataframe(df)
        bars_by_tf[tf], spec_by_tf[tf] = bars, spec
        dt = bars.datetimes()
        ranges[tf] = (f"{dt[0]:%Y-%m-%d}", f"{dt[-1]:%Y-%m-%d}")
        print(f"{tf}: {len(bars):,d} bars {ranges[tf][0]} -> {ranges[tf][1]}  point={spec.point} contract={spec.contract_size}")

    t0 = time.time()
    last = {"pct": -1}

    def progress(done: int, total: int) -> None:
        pct = done * 100 // total
        if pct // 5 != last["pct"] // 5:
            last["pct"] = pct
            print(f"  {done}/{total} ({pct}%)  {time.time() - t0:.0f}s", flush=True)

    print(f"grid: {grid.size()} combos x {len(tfs)} TF")
    grid_df = run_optimization(bars_by_tf, spec_by_tf, base, grid, cfg.costs, sizing, a.concurrency,
                               is_frac=a.is_frac, progress=progress)
    rec = recommend(grid_df)

    rec_results = {}
    for tf, r in rec.items():
        if r is None:
            continue
        p = r["params"]
        params = make_params(base, p["ob"], p["os"], p["f_hi"], p["f_lo"], p["atr_mult"])
        _, res = run_single(bars_by_tf[tf], spec_by_tf[tf], params, p["tp_r"], cfg.costs, sizing, a.concurrency)
        rec_results[tf] = res

    run_info = {"symbol": symbol, "timeframes": tfs, "data_range": ranges, "initial_equity": sizing.initial_equity,
                "risk_pct": sizing.risk_pct, "concurrency": a.concurrency, "spread_points": cfg.costs.spread_points,
                "commission_per_lot_rt": cfg.costs.commission_per_lot_rt, "slippage_points": cfg.costs.slippage_points,
                "is_frac": a.is_frac, "max_wait": a.max_wait,
                "grid": {"tp_r": list(grid.tp_r), "atr_mult": list(grid.atr_mult), "rsi14": a.rsi14, "rsi2": a.rsi2},
                "git_hash": _git_hash(), "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}

    out_dir = Path(a.out) / datetime.now().strftime("%Y%m%d_%H%M%S")
    write_csvs(out_dir, grid_df, rec_results)
    write_xlsx(out_dir / f"report_{symbol}.xlsx", grid_df, rec, rec_results, run_info)
    write_html(out_dir / f"report_{symbol}.html", grid_df, rec, rec_results, run_info, offline=a.offline)

    pd.set_option("display.width", 220)
    print("\n=== Recommendation ===")
    for tf, r in rec.items():
        if r is None:
            print(f"{tf}: no reliable parameter set")
        else:
            p = r["params"]
            print(f"{tf}: TP {p['tp_r']:g}R  ATRx{p['atr_mult']:g}  RSI14 {p['ob']:g}/{p['os']:g}  RSI2 {p['f_hi']:g}/{p['f_lo']:g}")
            print(f"     {r['reason']}")
    cols = KEY_COLS + ["n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct", "is_avg_r", "oos_avg_r", "robust_r", "flags"]
    for tf, g in grid_df.groupby("tf", sort=False):
        print(f"\n--- {tf}: top 5 by OOS avg R ---")
        print(g.sort_values(["oos_avg_r", "is_avg_r"], ascending=False)[cols].head(5).to_string(index=False))
    print(f"\nwritten: {out_dir}  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
