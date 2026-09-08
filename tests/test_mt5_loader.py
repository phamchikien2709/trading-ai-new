import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from rsi_fvg.data.mt5_loader import (RATE_COLUMNS, Mt5Session, cache_paths, fetch_rates,
                                     fetch_symbol_spec, load_or_fetch, tf_constant)
from rsi_fvg.params import SymbolSpec, load_config

ROOT = Path(__file__).resolve().parents[1]
CFG = load_config(ROOT / "config" / "default.yaml")


def _mt5_available() -> bool:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return False
    ok = mt5.initialize()
    if ok:
        mt5.shutdown()
    return bool(ok)


needs_mt5 = pytest.mark.skipif(not _mt5_available(), reason="MT5 terminal not running/logged in")


def test_cache_paths():
    pq, sj = cache_paths(Path("data"), "XAUUSDc", "M5")
    assert pq.name == "XAUUSDc_M5.parquet" and sj.name == "XAUUSDc_M5.spec.json"


def test_load_or_fetch_reads_cache_without_mt5(tmp_path):
    df = pd.DataFrame({"time": [0, 300], "open": [1.0, 2], "high": [2.0, 3], "low": [0.0, 1],
                       "close": [1.5, 2.5], "tick_volume": [1, 1], "spread": [10, 10]})
    pq, sj = cache_paths(tmp_path, "FAKE", "M5")
    df.to_parquet(pq, index=False)
    sj.write_text(json.dumps(SymbolSpec(name="FAKE", point=0.5).to_dict()))
    got, spec = load_or_fetch("FAKE", "M5", tmp_path)
    assert len(got) == 2 and spec.point == 0.5 and spec.name == "FAKE"


def test_load_or_fetch_uses_fallback_spec_when_sidecar_missing(tmp_path):
    pq, _ = cache_paths(tmp_path, "FAKE", "M5")
    pd.DataFrame({c: [0] for c in RATE_COLUMNS}).to_parquet(pq, index=False)
    _, spec = load_or_fetch("FAKE", "M5", tmp_path, fallback_spec=SymbolSpec(name="FAKE", point=0.25))
    assert spec.point == 0.25


@needs_mt5
def test_tf_constant_and_symbol_spec():
    import MetaTrader5 as mt5
    assert tf_constant("M5") == mt5.TIMEFRAME_M5 and tf_constant("h1") == mt5.TIMEFRAME_H1
    with Mt5Session():
        spec = fetch_symbol_spec(CFG.symbol)
    assert spec.name == CFG.symbol and spec.point > 0 and spec.contract_size > 0 and spec.lot_step > 0


@needs_mt5
def test_fetch_rates_recent_window():
    start = datetime.now(timezone.utc) - timedelta(days=3)
    with Mt5Session():
        df = fetch_rates(CFG.symbol, "M5", start=start, chunk=500)
    assert list(df.columns) == RATE_COLUMNS
    assert len(df) > 100
    assert df["time"].is_monotonic_increasing and df["time"].is_unique
    assert df["time"].iloc[0] >= int(start.timestamp()) - 300
