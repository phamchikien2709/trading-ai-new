"""Pull OHLC history from the running MT5 terminal; cache parquet + symbol-spec sidecar (spec §3.7)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ..params import SymbolSpec

log = logging.getLogger(__name__)

RATE_COLUMNS = ["time", "open", "high", "low", "close", "tick_volume", "spread"]
_TF_ATTR = {"M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15", "M30": "TIMEFRAME_M30",
            "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4", "D1": "TIMEFRAME_D1"}
TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}
TRIM_WINDOW = 200


def _mt5():
    import MetaTrader5 as mt5  # lazy: importing this module must not require MT5

    return mt5


def tf_constant(tf: str) -> int:
    return getattr(_mt5(), _TF_ATTR[tf.upper()])


class Mt5Session:
    def __enter__(self):
        mt5 = _mt5()
        if not mt5.initialize():
            raise RuntimeError(f"mt5.initialize() failed: {mt5.last_error()}")
        return mt5

    def __exit__(self, *exc):
        _mt5().shutdown()
        return False


def fetch_symbol_spec(symbol: str) -> SymbolSpec:
    mt5 = _mt5()
    mt5.symbol_select(symbol, True)
    si = mt5.symbol_info(symbol)
    if si is None:
        raise RuntimeError(f"symbol_info({symbol!r}) is None: {mt5.last_error()}")
    return SymbolSpec(name=symbol, point=float(si.point), digits=int(si.digits),
                      contract_size=float(si.trade_contract_size), min_lot=float(si.volume_min),
                      max_lot=float(si.volume_max), lot_step=float(si.volume_step),
                      stops_level_points=int(si.trade_stops_level))


def _usable_range(df: pd.DataFrame) -> str:
    if df.empty:
        return "empty"
    a = datetime.fromtimestamp(int(df["time"].iloc[0]), tz=timezone.utc)
    b = datetime.fromtimestamp(int(df["time"].iloc[-1]), tz=timezone.utc)
    return f"{a:%Y-%m-%d %H:%M} -> {b:%Y-%m-%d %H:%M} UTC"


def trim_to_timeframe(df: pd.DataFrame, tf: str, window: int = TRIM_WINDOW) -> tuple[pd.DataFrame, int]:
    """Drop a leading block of bars whose spacing does not match `tf`.

    MT5 serves a prefix of coarser bars (daily, then a stretch of H1) ahead of the genuine
    intraday history for XAUUSDc: ~924 daily bars for 2014-01 -> 2017-01 with
    ``tick_volume == 1``, ``spread == 0`` and 00:00 timestamps. Feeding those to an intraday
    strategy silently corrupts every indicator, so they are cut off.

    Genuine data is recognised as the first index whose spacing is exactly ``TF_SECONDS[tf]``
    and whose next `window` spacings (or all remaining, if fewer) are *mostly* that spacing:
    at least half equal it exactly and at most a quarter exceed ``3 * TF_SECONDS[tf]``.

    Note the last clause is a deliberate relaxation of "no spacing exceeds 3x the timeframe":
    XAUUSD has a ~1h daily session break and a weekend gap, so on M15 (200 bars = 50 h) and
    H1 (200 bars = 200 h) *no* window can avoid an oversized spacing and the strict form
    trims the whole file away. Anchoring on ``d[i] == tf_seconds`` is what keeps the boundary
    exact: it rejects any index still inside the daily prefix.

    Returns the trimmed frame (index reset) and the number of dropped rows.
    """
    tfs = TF_SECONDS[tf.upper()]
    if len(df) < 2:
        return df, 0
    d = np.diff(df["time"].to_numpy(dtype="int64"))
    n = len(d)
    idx = np.arange(n)
    wlen = np.minimum(window, n - idx)
    exact_cs = np.r_[0, np.cumsum(d == tfs)]
    big_cs = np.r_[0, np.cumsum(d > 3 * tfs)]
    ends = idx + wlen
    n_exact = exact_cs[ends] - exact_cs[idx]
    n_big = big_cs[ends] - big_cs[idx]
    ok = (d == tfs) & (n_exact * 2 >= wlen) & (n_big * 4 <= wlen)
    if not ok.any():
        log.warning("%s: no run of %d bars matches the %ds spacing — left untrimmed (%d rows, %s)",
                    tf, window, tfs, len(df), _usable_range(df))
        return df, 0
    start = int(np.argmax(ok))
    if start == 0:
        return df, 0
    out = df.iloc[start:].reset_index(drop=True)
    log.warning("%s: dropped %d leading bars whose spacing != %ds (MT5 served coarser bars first); "
                "usable range %s", tf, start, tfs, _usable_range(out))
    return out, start


def fetch_rates(symbol: str, tf: str, start: datetime | None = None, chunk: int = 50_000) -> pd.DataFrame:
    mt5 = _mt5()
    tfc = tf_constant(tf)
    date_to = datetime.now(timezone.utc) + timedelta(days=1)
    frames: list[pd.DataFrame] = []
    suspect_cap = False
    while True:
        rates = mt5.copy_rates_from(symbol, tfc, date_to, chunk)
        if rates is None or len(rates) == 0:
            suspect_cap = bool(frames) and len(frames[-1]) == chunk
            break
        df = pd.DataFrame(rates)[RATE_COLUMNS]
        frames.append(df)
        oldest = int(df["time"].iloc[0])
        if len(rates) < chunk:
            break
        if start is not None and oldest <= int(start.timestamp()):
            break
        date_to = datetime.fromtimestamp(oldest, tz=timezone.utc) - timedelta(seconds=1)
    if not frames:
        raise RuntimeError(f"no rates for {symbol} {tf}: {mt5.last_error()}")
    out = pd.concat(frames, ignore_index=True).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    if start is not None:
        out = out[out["time"] >= int(start.timestamp())].reset_index(drop=True)
    out["time"] = out["time"].astype("int64")
    if suspect_cap:
        log.warning("%s %s: history ended exactly on a full chunk (%d bars) — may be capped by the terminal's "
                    "'Max bars in chart' setting (Tools > Options > Charts).", symbol, tf, chunk)
    out, _ = trim_to_timeframe(out, tf)
    return out


def cache_paths(data_dir: Path, symbol: str, tf: str) -> tuple[Path, Path]:
    data_dir = Path(data_dir)
    return data_dir / f"{symbol}_{tf}.parquet", data_dir / f"{symbol}_{tf}.spec.json"


def load_or_fetch(symbol: str, tf: str, data_dir: Path, refresh: bool = False, start: datetime | None = None,
                  fallback_spec: SymbolSpec | None = None) -> tuple[pd.DataFrame, SymbolSpec]:
    pq, sj = cache_paths(data_dir, symbol, tf)
    if pq.exists() and not refresh:
        df = pd.read_parquet(pq)
        df, dropped = trim_to_timeframe(df, tf)
        if dropped:
            df.to_parquet(pq, index=False)   # persist the fix so the cache is clean from now on
            log.warning("%s: rewrote cache without the %d mismatched leading bars", pq.name, dropped)
        if sj.exists():
            spec = SymbolSpec.from_dict(json.loads(sj.read_text(encoding="utf-8")))
        else:
            spec = fallback_spec or SymbolSpec(name=symbol)
            log.warning("%s: spec sidecar missing, using fallback %s", pq.name, spec)
        return df, spec
    with Mt5Session():
        spec = fetch_symbol_spec(symbol)
        df = fetch_rates(symbol, tf, start=start)
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    df.to_parquet(pq, index=False)
    sj.write_text(json.dumps(spec.to_dict(), indent=2), encoding="utf-8")
    log.info("%s %s: %d bars cached to %s", symbol, tf, len(df), pq)
    return df, spec
