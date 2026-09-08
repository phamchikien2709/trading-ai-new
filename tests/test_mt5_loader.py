import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rsi_fvg.data.mt5_loader import (RATE_COLUMNS, TF_SECONDS, Mt5Session, cache_paths, fetch_rates,
                                     fetch_symbol_spec, load_or_fetch, tf_constant, trim_to_timeframe)
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


def _frame(times) -> pd.DataFrame:
    t = np.asarray(times, dtype="int64")
    n = len(t)
    return pd.DataFrame({"time": t, "open": np.ones(n), "high": np.ones(n) * 2, "low": np.zeros(n),
                         "close": np.ones(n) * 1.5, "tick_volume": np.ones(n, dtype="int64"),
                         "spread": np.full(n, 10, dtype="int64")})


def _daily_then_intraday(n_daily: int, n_bars: int, step: int):
    daily = 1_400_000_000 + np.arange(n_daily, dtype="int64") * 86400
    intraday = daily[-1] + 86400 + np.arange(n_bars, dtype="int64") * step
    return np.r_[daily, intraday]


def test_trim_drops_daily_prefix_exactly():
    df = _frame(_daily_then_intraday(30, 500, 300))
    out, dropped = trim_to_timeframe(df, "M5")
    assert dropped == 30
    assert len(out) == 500
    assert np.diff(out["time"].to_numpy()).max() == 300
    assert list(out.index) == list(range(500))          # index reset


def test_trim_keeps_clean_frame():
    df = _frame(1_700_000_000 + np.arange(500, dtype="int64") * 900)
    out, dropped = trim_to_timeframe(df, "M15")
    assert dropped == 0 and len(out) == 500


def test_trim_tolerates_session_and_weekend_gaps():
    # 200 H1 bars with a daily break every 23 bars and one weekend gap: still recognised as H1.
    t, cur = [], 1_700_000_000
    for i in range(400):
        t.append(cur)
        cur += 3600 * (49 if i == 200 else 2 if i % 23 == 22 else 1)
    df = _frame(np.r_[1_400_000_000 + np.arange(40, dtype="int64") * 86400, np.asarray(t, dtype="int64")])
    out, dropped = trim_to_timeframe(df, "H1")
    assert dropped == 40 and len(out) == 400


def test_trim_frame_shorter_than_window():
    df = _frame(1_700_000_000 + np.arange(5, dtype="int64") * 300)
    out, dropped = trim_to_timeframe(df, "M5")
    assert dropped == 0 and len(out) == 5
    one = _frame([1_700_000_000])
    assert trim_to_timeframe(one, "M5")[1] == 0
    assert trim_to_timeframe(_frame([]), "M5")[1] == 0


def test_trim_leaves_unrecognisable_frame_untouched(caplog):
    df = _frame(1_400_000_000 + np.arange(50, dtype="int64") * 86400)
    out, dropped = trim_to_timeframe(df, "M5")
    assert dropped == 0 and len(out) == 50
    assert any("no run of" in r.getMessage() for r in caplog.records)


def test_tf_seconds_table():
    assert TF_SECONDS["M5"] == 300 and TF_SECONDS["H1"] == 3600 and TF_SECONDS["D1"] == 86400


def test_load_or_fetch_trims_and_rewrites_cache(tmp_path, caplog):
    df = _frame(_daily_then_intraday(30, 500, 300))
    pq, sj = cache_paths(tmp_path, "FAKE", "M5")
    df.to_parquet(pq, index=False)
    sj.write_text(json.dumps(SymbolSpec(name="FAKE", point=0.5).to_dict()))
    got, _ = load_or_fetch("FAKE", "M5", tmp_path)
    assert len(got) == 500
    assert len(pd.read_parquet(pq)) == 500          # cache rewritten trimmed
    msgs = [r.getMessage() for r in caplog.records]
    assert any("dropped 30 leading bars" in m for m in msgs)
    assert any("rewrote cache" in m for m in msgs)
    again, _ = load_or_fetch("FAKE", "M5", tmp_path)
    assert len(again) == 500                        # second read is a no-op


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
