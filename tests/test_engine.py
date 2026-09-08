import numpy as np
import pandas as pd
import pytest

from rsi_fvg.backtest.engine import SKIPPED_COLUMNS, TRADE_COLUMNS, run_backtest
from rsi_fvg.params import CostParams, SizingParams, SymbolSpec
from rsi_fvg.signals import Direction, Signal

SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0, min_lot=0.01, max_lot=200.0, lot_step=0.01)
COSTS = CostParams(spread_points=20, commission_per_lot_rt=0.0, slippage_points=0)   # spread 0.20
SIZING = SizingParams(risk_pct=1.0, initial_equity=10_000.0)


def sig(direction, bar, sl, variant="A", anchor=0):
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


def test_gap_through_tp_wins_even_when_bar_also_touches_sl(mk_bars):
    # I4: buy filled 100.2, sl 90, tp 110.4. The bar opens above TP and its low reaches SL —
    # the open is tested first, so this books TP at the open, not SL.
    bars = mk_bars(o=[100, 100, 121, 121], h=[101, 101, 122, 122], l=[99, 99, 89, 120], c=[100, 100, 121, 121])
    res = run_backtest(bars, [sig(Direction.BUY, 0, sl=90.0)], tp_r=1.0, spec=SPEC, costs=COSTS, sizing=SIZING)
    tr = res.trades.iloc[0]
    assert tr.tp_price == pytest.approx(110.4)
    assert tr.exit_reason == "TP" and tr.exit_price == pytest.approx(121.0)


def test_gap_through_sl_wins_when_open_is_below_sl(mk_bars):
    # Mirror of the above: the open is already through SL, so SL books at the open.
    bars = mk_bars(o=[100, 100, 85, 85], h=[101, 101, 122, 122], l=[99, 99, 84, 84], c=[100, 100, 85, 85])
    res = run_backtest(bars, [sig(Direction.BUY, 0, sl=90.0)], tp_r=1.0, spec=SPEC, costs=COSTS, sizing=SIZING)
    tr = res.trades.iloc[0]
    assert tr.exit_reason == "SL" and tr.exit_price == pytest.approx(85.0)


def test_sell_gap_through_tp_wins_on_ask_open(mk_bars):
    # Sell fills at bid 100, sl 110, tp = 100 - 10 = 90. Ask open 80.2 is past TP while the
    # ask high 122.2 is past SL -> TP at the ask open.
    bars = mk_bars(o=[100, 100, 80, 80], h=[101, 101, 122, 81], l=[99, 99, 79, 79], c=[100, 100, 80, 80])
    res = run_backtest(bars, [sig(Direction.SELL, 0, sl=110.0)], tp_r=1.0, spec=SPEC, costs=COSTS, sizing=SIZING)
    tr = res.trades.iloc[0]
    assert tr.tp_price == pytest.approx(90.0)
    assert tr.exit_reason == "TP" and tr.exit_price == pytest.approx(80.2)


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


BIG = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0, min_lot=0.01, max_lot=1e6, lot_step=0.01)
NOCOST = CostParams(spread_points=0, commission_per_lot_rt=0.0, slippage_points=0)


def test_capped_flag_reaches_the_trade_log(mk_bars):
    # risk 5% of 10k over a 10-point stop wants 50 lots; max_lot 5 clamps it.
    spec = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0, min_lot=0.01, max_lot=5.0, lot_step=0.01)
    bars = mk_bars(o=[100, 100, 100], h=[101, 101, 101], l=[99, 99, 99], c=[100, 100, 100])
    res = run_backtest(bars, [sig(Direction.BUY, 0, sl=90.0)], 3.0, spec, NOCOST, SizingParams(5.0, 10_000.0))
    tr = res.trades.iloc[0]
    assert tr.lots == 5.0 and bool(tr.capped) is True and bool(tr.oversized) is False
    assert list(res.trades.columns) == TRADE_COLUMNS


def test_ruin_stops_trading_and_flatlines_the_curve(mk_bars):
    # 50% risk, every trade stops out: 10k -> 5k -> 2.5k -> 1.25k -> 625, which is under the
    # 10% floor, so the run ends at that bar.
    n = 8
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[85] * n, c=[100] * n)
    sigs = [sig(Direction.BUY, b, sl=90.0) for b in range(n - 1)]
    res = run_backtest(bars, sigs, 1.0, BIG, NOCOST, SizingParams(50.0, 10_000.0))
    assert res.ruined is True
    assert res.ruin_time == pd.Timestamp(bars.time[4], unit="s", tz="UTC")
    assert len(res.trades) == 4                                   # nothing fills after ruin
    assert (res.trades["exit_time"] <= res.ruin_time).all()
    assert res.equity.iloc[4] == pytest.approx(625.0)
    assert res.equity.iloc[4:].nunique() == 1                     # flat to the end
    assert res.equity.min() > 0


def test_ruin_force_closes_an_open_position(mk_bars):
    # 80% risk. Bar 1 stops out (10k -> 2k). Bar 2 opens 160 lots and marks -1280 at the
    # close without touching its stop, so marked equity 720 breaches the 1000 floor.
    bars = mk_bars(o=[100, 100, 100, 100, 100], h=[101, 101, 101, 101, 101],
                   l=[99, 85, 91, 99, 99], c=[100, 100, 92, 100, 100])
    sigs = [sig(Direction.BUY, 0, sl=90.0), sig(Direction.BUY, 1, sl=90.0)]
    res = run_backtest(bars, sigs, 1.0, BIG, NOCOST, SizingParams(80.0, 10_000.0))
    assert res.ruined is True and res.ruin_time == pd.Timestamp(bars.time[2], unit="s", tz="UTC")
    assert len(res.trades) == 2
    last = res.trades.iloc[1]
    assert last.exit_reason == "ruin"
    assert last.lots == pytest.approx(160.0) and last.exit_price == pytest.approx(92.0)
    assert res.equity.iloc[2] == pytest.approx(720.0)
    assert res.equity.iloc[-1] == pytest.approx(720.0)


def test_normal_run_is_not_ruined(mk_bars):
    bars = mk_bars(o=[100, 100, 104, 104], h=[101, 101, 111, 105], l=[99, 99, 99.5, 103], c=[100, 100, 104, 104])
    res = run_backtest(bars, [sig(Direction.BUY, 0, sl=90.0)], tp_r=1.0, spec=SPEC, costs=COSTS, sizing=SIZING)
    assert res.ruined is False and res.ruin_time is None


def test_ruin_floor_is_configurable(mk_bars):
    n = 8
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[85] * n, c=[100] * n)
    sigs = [sig(Direction.BUY, b, sl=90.0) for b in range(n - 1)]
    # A 60% floor stops the same sequence one loss earlier (10k -> 5k, 5k > 6k is false).
    high = run_backtest(bars, sigs, 1.0, BIG, NOCOST, SizingParams(50.0, 10_000.0), ruin_floor_pct=0.60)
    assert high.ruined is True and len(high.trades) == 1
    # A zero floor only trips on a wiped-out account, so this run keeps trading.
    zero = run_backtest(bars, sigs, 1.0, BIG, NOCOST, SizingParams(50.0, 10_000.0), ruin_floor_pct=0.0)
    assert zero.ruined is False and len(zero.trades) == 7


def test_min_sl_spread_mult_rejects_a_stop_inside_the_spread(mk_bars):
    # V2: fill 100.20 (open + 0.20 spread), SL 99.70 -> sl_dist 0.50, i.e. 2.5 spreads.
    bars = mk_bars(o=[100, 100, 100, 100], h=[100.1] * 4, l=[99.8] * 4, c=[100] * 4)
    sigs = [sig(Direction.BUY, 0, sl=99.7)]
    tight = run_backtest(bars, sigs, 1.0, SPEC, COSTS, SIZING, min_sl_spread_mult=5.0)   # needs 1.00
    assert len(tight.trades) == 0
    assert list(tight.skipped["reason"]) == ["rejected_min_sl"]
    assert list(tight.skipped.columns) == SKIPPED_COLUMNS
    off = run_backtest(bars, sigs, 1.0, SPEC, COSTS, SIZING)                             # filter off
    assert len(off.trades) == 1 and off.skipped.empty
    passes = run_backtest(bars, sigs, 1.0, SPEC, COSTS, SIZING, min_sl_spread_mult=2.0)  # needs 0.40
    assert len(passes.trades) == 1 and passes.skipped.empty


def test_signal_on_last_bar_never_fills(mk_bars):
    bars = mk_bars(o=[100, 100], h=[101, 101], l=[99, 99], c=[100, 100])
    res = run_backtest(bars, [sig(Direction.BUY, 1, sl=90.0)], 3.0, SPEC, COSTS, SIZING)
    assert len(res.trades) == 0 and len(res.skipped) == 0
    assert len(res.equity) == 2 and res.equity.iloc[-1] == 10_000.0
