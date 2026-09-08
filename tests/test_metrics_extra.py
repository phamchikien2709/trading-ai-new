import numpy as np
import pandas as pd
import pytest

from rsi_fvg.backtest.engine import TRADE_COLUMNS
from rsi_fvg.backtest.metrics import (compute_metrics, equity_from_trades, max_consecutive_losses,
                                      monthly_table)


def _trades(rows):
    base = pd.Timestamp("2025-01-01", tz="UTC")
    data = []
    for e, x, d, r, pnl, bh in rows:
        data.append({c: None for c in TRADE_COLUMNS} | {
            "entry_time": base + pd.Timedelta(days=e), "exit_time": base + pd.Timedelta(days=x),
            "direction": d, "variant": "SWING", "tp_r": 2.0, "r_multiple": r, "pnl_usd": pnl,
            "bars_held": bh, "commission": 0.0, "risk_usd": abs(pnl / r) if r else 0.0, "oversized": False})
    return pd.DataFrame(data, columns=TRADE_COLUMNS)


def test_max_consecutive_losses():
    assert max_consecutive_losses(pd.Series([1, -1, -1, 2, -1, -1, -1, 3.0])) == 3
    assert max_consecutive_losses(pd.Series([1, 2.0])) == 0
    assert max_consecutive_losses(pd.Series([], dtype=float)) == 0


def test_extra_keys_known_values():
    tr = _trades([(0, 1, "BUY", 1.0, 100, 5), (2, 3, "SELL", -1.0, -100, 4), (4, 6, "BUY", 3.0, 300, 10),
                  (7, 8, "SELL", -1.0, -100, 1)])
    eq = equity_from_trades(tr, 10_000)
    m = compute_metrics(tr, eq, 10_000, n_bars=100)
    assert m["avg_win_r"] == pytest.approx(2.0) and m["avg_loss_r"] == pytest.approx(-1.0)
    assert m["expectancy_usd"] == pytest.approx(50.0)
    assert m["max_consec_losses"] == 1
    assert m["time_in_market_pct"] == pytest.approx(20.0)      # 20 bars held / 100 bars
    assert m["calmar"] > 0 and np.isfinite(m["sortino_daily"])


def test_time_in_market_capped_and_zero_without_n_bars():
    tr = _trades([(0, 1, "BUY", 1.0, 100, 500)])
    m = compute_metrics(tr, equity_from_trades(tr, 10_000), 10_000, n_bars=100)
    assert m["time_in_market_pct"] == 100.0
    m2 = compute_metrics(tr, equity_from_trades(tr, 10_000), 10_000)
    assert m2["time_in_market_pct"] == 0.0


def test_empty_has_new_keys():
    m = compute_metrics(pd.DataFrame(columns=TRADE_COLUMNS), pd.Series(dtype=float), 10_000)
    for k in ("avg_win_r", "avg_loss_r", "expectancy_usd", "sortino_daily", "calmar",
              "max_consec_losses", "time_in_market_pct"):
        assert k in m and m[k] == 0


def test_monthly_table_shape_and_values():
    idx = pd.to_datetime(["2025-01-05", "2025-01-20", "2025-02-10", "2025-03-15"], utc=True)
    eq = pd.Series([10_000, 10_500, 10_500, 9_450.0], index=idx)
    tbl = monthly_table(eq)
    assert list(tbl.columns) == list(range(1, 13))
    assert list(tbl.index) == [2025]
    assert tbl.loc[2025, 1] == pytest.approx(5.0)       # 10000 -> 10500
    assert tbl.loc[2025, 2] == pytest.approx(0.0)
    assert tbl.loc[2025, 3] == pytest.approx(-10.0)
    assert np.isnan(tbl.loc[2025, 4])
    assert monthly_table(pd.Series(dtype=float)).empty
