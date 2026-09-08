"""Performance statistics for a trade log + equity curve (spec §3.5)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> tuple[float, float]:
    if equity.empty:
        return 0.0, 0.0
    peak = equity.cummax()
    dd = peak - equity
    dd_pct = (dd / peak.replace(0, np.nan)).fillna(0.0)
    return float(dd.max()), float(dd_pct.max())


def equity_from_trades(trades: pd.DataFrame, initial_equity: float) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=float, name="equity")
    t = trades.sort_values("exit_time")
    idx = [t["entry_time"].min()] + list(t["exit_time"])
    vals = [initial_equity] + list(initial_equity + t["pnl_usd"].cumsum())
    return pd.Series(vals, index=pd.DatetimeIndex(idx), name="equity")


def _daily_returns(equity: pd.Series) -> pd.Series:
    """Daily simple returns of the equity curve: calendar-day resample, forward-filled
    across days without a mark, weekends dropped (XAUUSD trades Mon-Fri), then pct_change."""
    if len(equity) < 2:
        return pd.Series(dtype=float)
    daily = equity.resample("1D").last().ffill()
    daily = daily[daily.index.dayofweek < 5]
    return daily.pct_change().dropna()


def _sharpe_daily(equity: pd.Series) -> float:
    if len(equity) < 3:
        return 0.0
    r = _daily_returns(equity)
    return 0.0 if len(r) < 2 or r.std() == 0 else float(r.mean() / r.std() * np.sqrt(252))


def _cagr(equity: pd.Series, initial_equity: float) -> float:
    if equity.empty or initial_equity <= 0:
        return 0.0
    years = (equity.index[-1] - equity.index[0]).total_seconds() / (365.25 * 86400)
    if years <= 0 or equity.iloc[-1] <= 0:
        return 0.0
    return float((equity.iloc[-1] / initial_equity) ** (1 / years) - 1)


def max_consecutive_losses(pnl: pd.Series) -> int:
    best = cur = 0
    for v in pnl.astype(float):
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return int(best)


def _sortino_daily(equity: pd.Series) -> float:
    r = _daily_returns(equity)
    downside = r[r < 0]
    if len(r) < 2 or len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(r.mean() / downside.std() * np.sqrt(252))


def monthly_table(equity: pd.Series) -> pd.DataFrame:
    if equity.empty:
        return pd.DataFrame()
    monthly = equity.resample("1ME").last().dropna()
    prev = monthly.shift(1)
    prev.iloc[0] = equity.iloc[0]
    ret = (monthly / prev - 1.0) * 100.0
    df = pd.DataFrame({"year": ret.index.year, "month": ret.index.month, "ret": ret.values})
    return df.pivot(index="year", columns="month", values="ret").reindex(columns=range(1, 13))


def compute_metrics(trades: pd.DataFrame, equity: pd.Series, initial_equity: float,
                     n_blocked: int = 0, n_bars: int | None = None) -> dict:
    n = int(len(trades))
    if n == 0:
        return {"n_trades": 0, "n_wins": 0, "win_rate": 0.0, "avg_r": 0.0, "expectancy_r": 0.0,
                "profit_factor": 0.0, "max_dd_usd": 0.0, "max_dd_pct": 0.0, "sharpe_daily": 0.0, "cagr": 0.0,
                "avg_bars_held": 0.0, "net_pnl": 0.0, "final_equity": float(initial_equity),
                "n_blocked": int(n_blocked), "n_buy": 0, "n_sell": 0, "avg_r_buy": 0.0, "avg_r_sell": 0.0,
                "avg_win_r": 0.0, "avg_loss_r": 0.0, "expectancy_usd": 0.0, "sortino_daily": 0.0,
                "calmar": 0.0, "max_consec_losses": 0, "time_in_market_pct": 0.0}
    pnl = trades["pnl_usd"].astype(float)
    r = trades["r_multiple"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_loss = float(-losses.sum())
    pf = float(wins.sum() / gross_loss) if gross_loss > 0 else (np.inf if wins.sum() > 0 else 0.0)
    dd_usd, dd_pct = max_drawdown(equity)
    buy = trades[trades["direction"] == "BUY"]
    sell = trades[trades["direction"] == "SELL"]
    cagr = _cagr(equity, initial_equity)
    bars_held = trades["bars_held"].astype(float)
    tim = min(1.0, float(bars_held.sum()) / n_bars) * 100.0 if n_bars else 0.0
    return {
        "n_trades": n,
        "n_wins": int((pnl > 0).sum()),
        "win_rate": float((pnl > 0).mean()),
        "avg_r": float(r.mean()),
        "expectancy_r": float(r.mean()),
        "profit_factor": pf,
        "max_dd_usd": dd_usd,
        "max_dd_pct": dd_pct,
        "sharpe_daily": _sharpe_daily(equity),
        "cagr": cagr,
        "avg_bars_held": float(bars_held.mean()),
        "net_pnl": float(pnl.sum()),
        "final_equity": float(initial_equity + pnl.sum()),
        "n_blocked": int(n_blocked),
        "n_buy": int(len(buy)),
        "n_sell": int(len(sell)),
        "avg_r_buy": float(buy["r_multiple"].astype(float).mean()) if len(buy) else 0.0,
        "avg_r_sell": float(sell["r_multiple"].astype(float).mean()) if len(sell) else 0.0,
        "avg_win_r": float(r[pnl > 0].mean()) if len(wins) else 0.0,
        "avg_loss_r": float(r[pnl < 0].mean()) if len(losses) else 0.0,
        "expectancy_usd": float(pnl.mean()),
        "sortino_daily": _sortino_daily(equity),
        "calmar": float(cagr / dd_pct) if dd_pct > 0 else 0.0,
        "max_consec_losses": max_consecutive_losses(pnl),
        "time_in_market_pct": tim,
    }
