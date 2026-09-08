"""Pull OHLC history from the running MT5 terminal; cache parquet + symbol-spec sidecar (spec §3.7)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from ..params import SymbolSpec

log = logging.getLogger(__name__)

RATE_COLUMNS = ["time", "open", "high", "low", "close", "tick_volume", "spread"]
_TF_ATTR = {"M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15", "M30": "TIMEFRAME_M30",
            "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4", "D1": "TIMEFRAME_D1"}


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
    return out


def cache_paths(data_dir: Path, symbol: str, tf: str) -> tuple[Path, Path]:
    data_dir = Path(data_dir)
    return data_dir / f"{symbol}_{tf}.parquet", data_dir / f"{symbol}_{tf}.spec.json"


def load_or_fetch(symbol: str, tf: str, data_dir: Path, refresh: bool = False, start: datetime | None = None,
                  fallback_spec: SymbolSpec | None = None) -> tuple[pd.DataFrame, SymbolSpec]:
    pq, sj = cache_paths(data_dir, symbol, tf)
    if pq.exists() and not refresh:
        df = pd.read_parquet(pq)
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
