"""Event-driven backtest engine (spec §3.3).

Per bar t: (1) fill signals queued from t-1 at open[t]; (2) check SL/TP on bar t's range
(SL wins ties); (3) mark equity at close[t]; (4) queue signals whose signal_bar == t.
Candles are BID. Buy fills/exits at ask = bid + spread; buy SL/TP trigger on bid.
Sell fills/exits at bid; sell SL/TP trigger on ask.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..bars import Bars
from ..params import CostParams, SizingParams, SymbolSpec
from ..sizing import lots_for_risk
from ..signals import Direction, Signal

TRADE_COLUMNS = ["entry_time", "exit_time", "direction", "variant", "tp_r", "entry_price", "exit_price",
                 "sl_price", "tp_price", "lots", "sl_dist", "risk_usd", "r_multiple", "pnl_usd",
                 "commission", "exit_reason", "bars_held", "bars_in_wait", "anchor_time", "oversized"]
SKIPPED_COLUMNS = ["time", "signal_time", "direction", "variant", "reason"]
_TIME_COLS = ("entry_time", "exit_time", "anchor_time", "time", "signal_time")


@dataclass
class Position:
    direction: Direction
    signal: Signal
    entry_bar: int
    entry_price: float
    sl: float
    tp: float
    lots: float
    sl_dist: float
    risk_usd: float
    commission: float
    oversized: bool


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    skipped: pd.DataFrame
    equity: pd.Series
    tp_r: float
    variant: str
    concurrency: str
    initial_equity: float


def _to_frame(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=columns)
    for col in _TIME_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], unit="s", utc=True)
    return df


def run_backtest(bars: Bars, signals: list[Signal], tp_r: float, spec: SymbolSpec, costs: CostParams,
                 sizing: SizingParams, concurrency: str = "hedge") -> BacktestResult:
    if concurrency not in ("hedge", "single"):
        raise ValueError(f"concurrency must be 'hedge' or 'single', got {concurrency!r}")
    n = len(bars)
    o, h, l, c, tm = bars.open, bars.high, bars.low, bars.close, bars.time
    spread = costs.spread_points * spec.point
    slip = costs.slippage_points * spec.point
    cs = spec.contract_size

    by_bar: dict[int, list[Signal]] = {}
    for s in signals:
        by_bar.setdefault(s.signal_bar, []).append(s)

    equity = float(sizing.initial_equity)
    eq_curve = np.empty(n, dtype=np.float64)
    positions: dict[Direction, Position] = {}
    pending: list[Signal] = []
    trades: list[dict] = []
    skipped: list[dict] = []
    variant_name = signals[0].variant if signals else ""

    def close_position(pos: Position, bar: int, price: float, reason: str) -> None:
        nonlocal equity
        d = int(pos.direction)
        gross = d * (price - pos.entry_price) * pos.lots * cs
        equity += gross
        net = gross - pos.commission
        trades.append({
            "entry_time": tm[pos.entry_bar], "exit_time": tm[bar], "direction": pos.direction.name,
            "variant": pos.signal.variant, "tp_r": tp_r, "entry_price": pos.entry_price,
            "exit_price": price, "sl_price": pos.sl, "tp_price": pos.tp, "lots": pos.lots,
            "sl_dist": pos.sl_dist, "risk_usd": pos.risk_usd, "r_multiple": net / pos.risk_usd,
            "pnl_usd": net, "commission": pos.commission, "exit_reason": reason,
            "bars_held": bar - pos.entry_bar, "bars_in_wait": pos.signal.bars_in_wait,
            "anchor_time": tm[pos.signal.anchor_bar], "oversized": pos.oversized,
        })

    def skip(s: Signal, bar: int, reason: str) -> None:
        skipped.append({"time": tm[bar], "signal_time": tm[s.signal_bar], "direction": s.direction.name,
                        "variant": s.variant, "reason": reason})

    for t in range(n):
        # 1. fills
        for s in pending:
            blocked = (s.direction in positions) if concurrency == "hedge" else bool(positions)
            if blocked:
                skip(s, t, "blocked")
                continue
            d = int(s.direction)
            fill = o[t] + spread + slip if d == 1 else o[t] - slip
            if (d == 1 and fill <= s.sl_price) or (d == -1 and fill >= s.sl_price):
                skip(s, t, "rejected_invalid_sl")
                continue
            sl_dist = abs(fill - s.sl_price)
            lots, oversized = lots_for_risk(equity, sizing.risk_pct, sl_dist, spec)
            commission = costs.commission_per_lot_rt * lots
            equity -= commission
            positions[s.direction] = Position(
                direction=s.direction, signal=s, entry_bar=t, entry_price=float(fill), sl=s.sl_price,
                tp=float(fill + d * tp_r * sl_dist), lots=lots, sl_dist=float(sl_dist),
                risk_usd=float(sl_dist * lots * cs), commission=float(commission), oversized=oversized,
            )
        pending = []

        # 2. exits (SL before TP)
        for key in list(positions):
            pos = positions[key]
            if int(key) == 1:
                bo, bh, bl = o[t], h[t], l[t]
                if bl <= pos.sl:
                    price, reason = min(bo, pos.sl) - slip, "SL"
                elif bh >= pos.tp:
                    price, reason = max(bo, pos.tp), "TP"
                else:
                    continue
            else:
                ao, ah, al = o[t] + spread, h[t] + spread, l[t] + spread
                if ah >= pos.sl:
                    price, reason = max(ao, pos.sl) + slip, "SL"
                elif al <= pos.tp:
                    price, reason = min(ao, pos.tp), "TP"
                else:
                    continue
            close_position(pos, t, float(price), reason)
            del positions[key]

        # 3. mark-to-market
        unreal = 0.0
        for key, pos in positions.items():
            mark = c[t] if int(key) == 1 else c[t] + spread
            unreal += int(key) * (mark - pos.entry_price) * pos.lots * cs
        eq_curve[t] = equity + unreal

        # 4. queue this bar's signals for next open
        if t in by_bar:
            pending = list(by_bar[t])

    if n > 0:
        last = n - 1
        for key, pos in list(positions.items()):
            mark = c[last] if int(key) == 1 else c[last] + spread
            close_position(pos, last, float(mark), "end")
        positions.clear()
        eq_curve[last] = equity

    equity_series = pd.Series(eq_curve, index=bars.datetimes(), name="equity")
    return BacktestResult(trades=_to_frame(trades, TRADE_COLUMNS), skipped=_to_frame(skipped, SKIPPED_COLUMNS),
                          equity=equity_series, tp_r=float(tp_r), variant=variant_name,
                          concurrency=concurrency, initial_equity=float(sizing.initial_equity))
