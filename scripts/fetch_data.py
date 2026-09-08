"""Fetch/cache OHLC history from MT5 for the configured symbol/timeframes.

Usage: python scripts/fetch_data.py [--tf M5 M15 H1] [--refresh] [--start 2023-01-01]
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.params import load_config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    ap.add_argument("--symbol")
    ap.add_argument("--tf", nargs="*")
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--start", help="YYYY-MM-DD (UTC); default = as far back as the broker allows")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = load_config(a.config)
    symbol = a.symbol or cfg.symbol
    tfs = a.tf or cfg.timeframes
    start = datetime.strptime(a.start, "%Y-%m-%d").replace(tzinfo=timezone.utc) if a.start else None
    for tf in tfs:
        df, spec = load_or_fetch(symbol, tf, Path(a.data_dir), refresh=a.refresh, start=start,
                                 fallback_spec=cfg.spec_fallback)
        t0 = datetime.fromtimestamp(int(df["time"].iloc[0]), tz=timezone.utc)
        t1 = datetime.fromtimestamp(int(df["time"].iloc[-1]), tz=timezone.utc)
        print(f"{symbol} {tf:>3}: {len(df):>8,d} bars  {t0:%Y-%m-%d} -> {t1:%Y-%m-%d %H:%M}  "
              f"point={spec.point} contract={spec.contract_size} lot_step={spec.lot_step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
