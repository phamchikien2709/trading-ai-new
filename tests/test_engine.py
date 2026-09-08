import numpy as np
import pandas as pd
import pytest

from rsi_fvg.backtest.engine import SKIPPED_COLUMNS, TRADE_COLUMNS, run_backtest
from rsi_fvg.params import CostParams, SizingParams, SymbolSpec
from rsi_fvg.strategy import Direction, Signal, Variant

SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0, min_lot=0.01, max_lot=200.0, lot_step=0.01)
COSTS = CostParams(spread_points=20, commission_per_lot_rt=0.0, slippage_points=0)   # spread 0.20
SIZING = SizingParams(risk_pct=1.0, initial_equity=10_000.0)


def sig(direction, bar, sl, variant=Variant.A, anchor=0):
    return Signal(direction=direction, variant=variant, signal_bar=bar, anchor_bar=anchor,
                  ref_price=0.0, sl_price=sl, bars_in_wait=1)


def test_buy_fill_next_open_plus_spread_then_tp(mk_bars):
    #          t: 0    1     2      3
    bars = mk_bars(o=[100, 100, 104, 104], h=[101, 101, 111, 105], l=[99, 99, 99.5, 103], c=[100, 100, 104, 104])
    res = run_backtest(bars, [sig(Direction.BUY, 0, sl=90.0)], tp_r=1.0, spec=SPEC, costs=COSTS, sizing=SIZING)
    assert list(res.trades.columns) == TRADE_COLUMNS
    assert len(res.trades) == 1
    tr = res.trades.iloc[0]
    assert tr.entry_price == pytest.approx(100.2)           # open[1] + spread
    assert tr.sl_dist == pytest.approx(10.2)
    assert tr.tp_price == pytest.approx(110.4)              # 1R from real fill
    assert tr.lots == pytest.approx(9.80)                   # 100 / 10.2 floored
    assert tr.exit_reason == "TP" and tr.exit_price == pytest.approx(110.4)
    assert tr.r_multiple == pytest.approx(1.0)
    assert tr.pnl_usd == pytest.approx(10.2 * 9.8)
    assert tr.bars_held == 1 and tr.direction == "BUY" and tr.variant == "A" and tr.tp_r == 1.0
    assert tr.entry_time == pd.Timestamp(bars.time[1], unit="s", tz="UTC")
    assert res.equity.iloc[-1] == pytest.approx(10_000 + 10.2 * 9.8)
    assert res.equity.index.tz is not None


def test_same_bar_sl_and_tp_hits_sl_first(mk_bars):
    bars = mk_bars(o=[100, 100, 104, 104], h=[101, 101, 111, 105], l=[99, 99, 89, 103], c=[100, 100, 104, 104])
    res = run_backtest(bars, [sig(Direction.BUY, 0, sl=90.0)], tp_r=1.0, spec=SPEC, costs=COSTS, sizing=SIZING)
    tr = res.trades.iloc[0]
    assert tr.exit_reason == "SL" and tr.exit_price == pytest.approx(90.0)
    assert tr.r_multiple == pytest.approx(-1.0)


def test_gap_through_sl_fills_at_open_minus_slippage(mk_bars):
    bars = mk_bars(o=[100, 100, 85, 85], h=[101, 101, 86, 86], l=[99, 99, 84, 84], c=[100, 100, 85, 85])
    costs = CostParams(spread_points=20, commission_per_lot_rt=0.0, slippage_points=5)   # slip 0.05
    res = run_backtest(bars, [sig(Direction.BUY, 0, sl=90.0)], tp_r=1.0, spec=SPEC, costs=costs, sizing=SIZING)
    tr = res.trades.iloc[0]
    assert tr.entry_price == pytest.approx(100.25)          # open + spread + slip
    assert tr.exit_reason == "SL" and tr.exit_price == pytest.approx(85 - 0.05)
    assert tr.r_multiple < -1.0


def test_tp_gap_fills_at_open(mk_bars):
    bars = mk_bars(o=[100, 100, 120, 120], h=[101, 101, 121, 121], l=[99, 99, 119, 119], c=[100, 100, 120, 120])
    res = run_backtest(bars, [sig(Direction.BUY, 0, sl=90.0)], tp_r=1.0, spec=SPEC, costs=COSTS, sizing=SIZING)
    tr = res.trades.iloc[0]
    assert tr.exit_reason == "TP" and tr.exit_price == pytest.approx(120.0)
    assert tr.r_multiple > 1.0


def test_sell_uses_ask_for_sl(mk_bars):
    # bid high 109.9 < SL 110 but ask high = 110.1 >= 110 -> SL
    bars = mk_bars(o=[100, 100, 100, 100], h=[101, 101, 109.9, 101], l=[99, 99, 99, 99], c=[100, 100, 100, 100])
    res = run_backtest(bars, [sig(Direction.SELL, 0, sl=110.0)], tp_r=1.0, spec=SPEC, costs=COSTS, sizing=SIZING)
    tr = res.trades.iloc[0]
    assert tr.entry_price == pytest.approx(100.0)           # sell fills at bid
    assert tr.exit_reason == "SL" and tr.exit_price == pytest.approx(110.0)
    assert tr.r_multiple == pytest.approx(-1.0)


def test_blocked_same_direction(mk_bars):
    n = 6
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[99] * n, c=[100] * n)
    sigs = [sig(Direction.BUY, 0, sl=90.0), sig(Direction.BUY, 2, sl=90.0)]
    res = run_backtest(bars, sigs, tp_r=3.0, spec=SPEC, costs=COSTS, sizing=SIZING)
    assert len(res.trades) == 1 and res.trades.iloc[0].exit_reason == "end"
    assert list(res.skipped.columns) == SKIPPED_COLUMNS
    assert len(res.skipped) == 1 and res.skipped.iloc[0].reason == "blocked"
    assert res.skipped.iloc[0].time == pd.Timestamp(bars.time[3], unit="s", tz="UTC")


def test_hedge_allows_both_directions_single_blocks(mk_bars):
    n = 5
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[99] * n, c=[100] * n)
    sigs = [sig(Direction.SELL, 0, sl=110.0), sig(Direction.BUY, 0, sl=90.0)]
    hedge = run_backtest(bars, sigs, 3.0, SPEC, COSTS, SIZING, concurrency="hedge")
    assert len(hedge.trades) == 2 and len(hedge.skipped) == 0
    single = run_backtest(bars, sigs, 3.0, SPEC, COSTS, SIZING, concurrency="single")
    assert len(single.trades) == 1 and len(single.skipped) == 1 and single.skipped.iloc[0].reason == "blocked"
    with pytest.raises(ValueError):
        run_backtest(bars, sigs, 3.0, SPEC, COSTS, SIZING, concurrency="nope")


def test_rejected_invalid_sl_when_open_gaps_below_sl(mk_bars):
    bars = mk_bars(o=[100, 80, 80], h=[101, 81, 81], l=[99, 79, 79], c=[100, 80, 80])
    res = run_backtest(bars, [sig(Direction.BUY, 0, sl=90.0)], 1.0, SPEC, COSTS, SIZING)
    assert len(res.trades) == 0
    assert res.skipped.iloc[0].reason == "rejected_invalid_sl"


def test_commission_and_oversized(mk_bars):
    bars = mk_bars(o=[100, 100, 100], h=[101, 101, 101], l=[99, 99, 99], c=[100, 100, 100])
    costs = CostParams(spread_points=0, commission_per_lot_rt=7.0, slippage_points=0)
    sizing = SizingParams(risk_pct=1.0, initial_equity=5.0)      # 0.05 USD risk / 10 dist = 0.005 -> floors to 0 -> min_lot, oversized
    res = run_backtest(bars, [sig(Direction.BUY, 0, sl=90.0)], 3.0, SPEC, costs, sizing)
    tr = res.trades.iloc[0]
    assert tr.lots == 0.01 and bool(tr.oversized) is True
    assert tr.commission == pytest.approx(0.07)
    assert tr.pnl_usd == pytest.approx(-0.07)                # flat price, closed at end, only commission
    assert tr.exit_reason == "end"
    assert res.equity.iloc[-1] == pytest.approx(5.0 - 0.07)


def test_signal_on_last_bar_never_fills(mk_bars):
    bars = mk_mk = mk_bars(o=[100, 100], h=[101, 101], l=[99, 99], c=[100, 100])
    res = run_backtest(bars, [sig(Direction.BUY, 1, sl=90.0)], 3.0, SPEC, COSTS, SIZING)
    assert len(res.trades) == 0 and len(res.skipped) == 0
    assert len(res.equity) == 2 and res.equity.iloc[-1] == 10_000.0
