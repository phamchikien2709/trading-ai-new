import numpy as np
import pandas as pd
import pytest

from rsi_fvg.backtest.engine import TRADE_COLUMNS
from rsi_fvg.backtest.metrics import _daily_returns, compute_metrics, equity_from_trades, max_drawdown


def _trades(rows):
    """rows: list of (entry_day, exit_day, direction, r, pnl, bars_held)."""
    base = pd.Timestamp("2025-01-01", tz="UTC")
    data = []
    for e, x, d, r, pnl, bh in rows:
        data.append({c: None for c in TRADE_COLUMNS} | {
            "entry_time": base + pd.Timedelta(days=e), "exit_time": base + pd.Timedelta(days=x),
            "direction": d, "variant": "A", "tp_r": 3.0, "r_multiple": r, "pnl_usd": pnl,
            "bars_held": bh, "commission": 0.0, "risk_usd": abs(pnl / r) if r else 0.0,
        })
    return pd.DataFrame(data, columns=TRADE_COLUMNS)


def test_max_drawdown_simple():
    eq = pd.Series([100, 120, 90, 130, 100.0], index=pd.date_range("2025-01-01", periods=5, tz="UTC"))
    dd_usd, dd_pct = max_drawdown(eq)
    assert dd_usd == pytest.approx(30.0)          # 120 -> 90 and 130 -> 100 both 30
    assert dd_pct == pytest.approx(30 / 120)      # deepest in % terms is 120->90 (25%) vs 130->100 (23%)


def test_equity_from_trades_step_curve():
    tr = _trades([(0, 1, "BUY", 1.0, 100, 5), (2, 3, "SELL", -1.0, -100, 4), (4, 6, "BUY", 3.0, 300, 10)])
    eq = equity_from_trades(tr, 10_000)
    assert eq.iloc[0] == 10_000 and eq.iloc[-1] == 10_300
    assert list(eq.values) == [10_000, 10_100, 10_000, 10_300]


def test_compute_metrics_known_values():
    tr = _trades([(0, 1, "BUY", 1.0, 100, 5), (2, 3, "SELL", -1.0, -100, 4), (4, 6, "BUY", 3.0, 300, 10),
                  (7, 8, "SELL", -1.0, -100, 1)])
    eq = equity_from_trades(tr, 10_000)
    m = compute_metrics(tr, eq, 10_000, n_blocked=2)
    assert m["n_trades"] == 4 and m["n_wins"] == 2 and m["win_rate"] == pytest.approx(0.5)
    assert m["avg_r"] == pytest.approx(0.5) and m["expectancy_r"] == pytest.approx(0.5)
    assert m["profit_factor"] == pytest.approx(400 / 200)
    assert m["net_pnl"] == pytest.approx(200) and m["final_equity"] == pytest.approx(10_200)
    assert m["max_dd_usd"] == pytest.approx(100)
    assert m["avg_bars_held"] == pytest.approx(5.0)
    assert m["n_blocked"] == 2
    assert m["n_buy"] == 2 and m["n_sell"] == 2
    assert m["avg_r_buy"] == pytest.approx(2.0) and m["avg_r_sell"] == pytest.approx(-1.0)
    assert m["cagr"] > 0 and np.isfinite(m["sharpe_daily"])


def test_compute_metrics_empty():
    tr = pd.DataFrame(columns=TRADE_COLUMNS)
    eq = pd.Series([10_000.0], index=pd.date_range("2025-01-01", periods=1, tz="UTC"))
    m = compute_metrics(tr, eq, 10_000)
    assert m["n_trades"] == 0 and m["win_rate"] == 0.0 and m["profit_factor"] == 0.0
    assert m["final_equity"] == 10_000 and m["max_dd_usd"] == 0.0


def test_profit_factor_no_losses_is_inf():
    tr = _trades([(0, 1, "BUY", 2.0, 200, 3)])
    m = compute_metrics(tr, equity_from_trades(tr, 10_000), 10_000)
    assert m["profit_factor"] == np.inf


def test_sharpe_daily_known_value():
    tr = _trades([(0, 1, "BUY", 1.0, 100, 5)])
    idx = pd.to_datetime(["2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09"], utc=True)
    eq = pd.Series([10_000, 10_100, 10_000, 10_200.0], index=idx)
    returns = np.array([0.01, -0.00990099, 0.02])
    expected = returns.mean() / returns.std(ddof=1) * np.sqrt(252)
    m = compute_metrics(tr, eq, 10_000)
    assert m["sharpe_daily"] == pytest.approx(expected, rel=1e-6)


def test_sharpe_forward_fills_gaps():
    idx = pd.to_datetime(["2025-01-06", "2025-01-20"], utc=True)
    eq = pd.Series([10_000, 10_100.0], index=idx)
    r = _daily_returns(eq)
    assert len(r) == 10
    nonzero = r[r != 0]
    assert len(nonzero) == 1
    assert nonzero.iloc[0] == pytest.approx(0.01)


def test_cagr_known_value():
    idx = pd.to_datetime(["2025-01-01", "2026-01-01"], utc=True)
    eq = pd.Series([10_000, 11_000.0], index=idx)
    tr = _trades([(0, 1, "BUY", 1.0, 100, 5)])
    years = 365 / 365.25
    expected = 1.1 ** (1 / years) - 1
    m = compute_metrics(tr, eq, 10_000)
    assert m["cagr"] == pytest.approx(expected, rel=1e-9)
