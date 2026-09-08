# RSI2 Swing — Python Backtest, Optimizer & Export Implementation Plan (Phase 1b)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backtest the RSI2 Swing Pullback strategy on XAUUSDc M5/M15/H1 data from MT5 (10,000 USD, 5% risk), sweep a 225-combo parameter grid per timeframe with IS/OOS + neighbourhood robustness, auto-recommend parameters, and export an Excel workbook + self-contained HTML report.

**Architecture:** Reuses the Phase 1 core (`indicators`, `bars`, `params`, `sizing`, `backtest/engine`, `backtest/metrics`, `data/mt5_loader`). Strategies become plugins under `rsi_fvg/strategies/` sharing `rsi_fvg/signals.py`. `backtest/optimize.py` runs the grid (signals computed once per RSI/ATR combo, engine once per TP), scores robustness and recommends. `backtest/export.py` writes xlsx (openpyxl) and html (plotly).

**Tech Stack:** Python 3.13, numpy, pandas, pyarrow, MetaTrader5, openpyxl 3.1, plotly 6.3, pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-rsi2-swing-backtest-optimizer-design.md` (this plan) which inherits `docs/superpowers/specs/2026-09-08-rsi-fvg-pullback-strategy-design.md` §2.6–2.8, §3.

**Prerequisites:** Phase 1 plan `docs/superpowers/plans/2026-09-08-rsi-fvg-phase1-python-backtest.md` **Tasks 1–8 must be complete first** (they build the core this plan plugs into). Phase 1 **Task 9 (RSI-FVG runner/report/CLI) is deferred** — its job is superseded here by `optimize.py` + `export.py`; the RSI-FVG grid can be run through them later.

## Global Constraints

- Everything in the Phase 1 plan's Global Constraints still applies (Wilder RSI/ATR, fills at `open[t+1]`, bid candles + spread, SL wins ties, state machine ignores positions, priority re-cross → expiry → trigger, `XAUUSDc` spec from broker sidecar, real account → **never send orders**).
- Default run for this strategy: `risk_pct = 5.0`, `tp_r = 2.0`, `concurrency = hedge`, initial equity 10,000.
- Grid (spec §4.1): `tp_r ∈ {1, 1.5, 2, 3, 4}`, `atr_mult ∈ {0, 0.5, 1, 1.5, 2}`, `(ob, os) ∈ {(70,30), (75,25), (80,20)}`, `(f_hi, f_lo) ∈ {(85,15), (90,10), (95,5)}` → 225 combos per TF.
- IS/OOS split: IS = first 70% of bars by time, OOS = last 30%. Metrics split by trade `entry_time`. Never re-optimise on OOS.
- Recommendation filter: `is_n_trades ≥ 30`, `is_avg_r > 0`, `oos_avg_r > 0`, `oversized_share ≤ 0.10`. Score = `0.5·z(oos_avg_r) + 0.3·z(robust_r) + 0.2·z(is_avg_r)` with z-scores computed within each TF over the filtered rows. No survivor → recommendation is `None` for that TF and the report says so.
- Robustness neighbours: same `tf, ob, f_hi`; grid-index distance ≤ 1 in both `tp_r` and `atr_mult`; self excluded. `robust_r = median(is_avg_r of neighbours)`; `robust_ratio = clip(robust_r / is_avg_r, 0, 1.5)` when `is_avg_r > 0` else `0`.
- Signal `variant` field is a plain `str` (`"A"/"B"/"C"` for RSI-FVG, `"SWING"` for RSI2).
- Commit after each task: `git -c user.name="MeoMeo" -c user.email="kienpham@cungbai.vn" commit ...`. Tests: `python -m pytest -q`.

---

## File Structure (new / changed in this plan)

| Path | Responsibility |
|---|---|
| `rsi_fvg/signals.py` | `Direction`, `Signal` (shared by all strategies) |
| `rsi_fvg/strategies/__init__.py` | empty |
| `rsi_fvg/strategies/rsi_fvg.py` | moved from `rsi_fvg/strategy.py` (Variant, State, Indicators, run_direction, run_strategy) |
| `rsi_fvg/strategy.py` | thin re-export shim so Phase 1 imports keep working |
| `rsi_fvg/strategies/rsi2_swing.py` | `Rsi2SwingParams`, `cross_up/cross_down`, `SwingEvents`, `swing_structure`, `run_direction`, `run_strategy` |
| `rsi_fvg/backtest/engine.py` | import from `signals`; `variant` is str |
| `rsi_fvg/backtest/metrics.py` | + `avg_win_r, avg_loss_r, expectancy_usd, sortino_daily, calmar, max_consec_losses, time_in_market_pct`, `monthly_table` |
| `rsi_fvg/backtest/optimize.py` | `GridSpec`, `run_optimization`, `add_robustness`, `compute_flags`, `recommend`, `run_single` |
| `rsi_fvg/backtest/export.py` | `write_csvs`, `write_xlsx`, `write_html` |
| `scripts/run_rsi2_swing.py` | CLI |
| `tests/test_signals.py`, `tests/test_rsi2_swing.py`, `tests/test_metrics_extra.py`, `tests/test_optimize.py`, `tests/test_export.py` | tests |
| `requirements.txt`, `README.md` | + openpyxl, plotly; usage |

---

### Task 10: Shared `signals.py` and strategy plugin layout

**Files:**
- Create: `rsi_fvg/signals.py`, `rsi_fvg/strategies/__init__.py`, `tests/test_signals.py`
- Move: `rsi_fvg/strategy.py` → `rsi_fvg/strategies/rsi_fvg.py` (git mv), then recreate `rsi_fvg/strategy.py` as a shim
- Modify: `rsi_fvg/backtest/engine.py` (imports + variant handling), `tests/test_strategy.py` (import path only if needed — the shim should make it pass unchanged)

**Interfaces:**
- Produces:
  - `rsi_fvg.signals.Direction(IntEnum): BUY = 1, SELL = -1`
  - `rsi_fvg.signals.Signal(direction: Direction, variant: str, signal_bar: int, anchor_bar: int, ref_price: float, sl_price: float, bars_in_wait: int, fvg_zone: tuple[float, float] | None = None, pivot_price: float | None = None, swing_price: float | None = None)` frozen dataclass
  - `rsi_fvg.strategies.rsi_fvg` exports `Variant, State, Indicators, compute_indicators, run_direction, run_strategy` (unchanged behaviour; `Signal.variant` now receives `variant.value`)
  - `rsi_fvg.strategy` re-exports everything above plus `Direction, Signal`.

- [ ] **Step 1: Write failing test**

`tests/test_signals.py`:
```python
from rsi_fvg.signals import Direction, Signal


def test_signal_defaults_and_variant_is_str():
    s = Signal(direction=Direction.BUY, variant="SWING", signal_bar=5, anchor_bar=1,
               ref_price=100.0, sl_price=95.0, bars_in_wait=4)
    assert s.swing_price is None and s.fvg_zone is None and s.pivot_price is None
    assert isinstance(s.variant, str)
    assert int(Direction.SELL) == -1


def test_shim_and_plugin_paths_agree():
    import rsi_fvg.strategy as shim
    from rsi_fvg.strategies import rsi_fvg as plugin
    assert shim.run_strategy is plugin.run_strategy
    assert shim.Signal is Signal and shim.Direction is Direction
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_signals.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.signals'`.

- [ ] **Step 3: Create signals.py and move the strategy**

`rsi_fvg/signals.py`:
```python
"""Signal types shared by every strategy plugin."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Direction(IntEnum):
    BUY = 1
    SELL = -1


@dataclass(frozen=True)
class Signal:
    direction: Direction
    variant: str                 # "A" | "B" | "C" (RSI-FVG) or "SWING" (RSI2 swing)
    signal_bar: int
    anchor_bar: int
    ref_price: float
    sl_price: float
    bars_in_wait: int
    fvg_zone: tuple[float, float] | None = None
    pivot_price: float | None = None
    swing_price: float | None = None
```

Then:
```bash
mkdir -p rsi_fvg/strategies && touch rsi_fvg/strategies/__init__.py
git mv rsi_fvg/strategy.py rsi_fvg/strategies/rsi_fvg.py
```

Edit `rsi_fvg/strategies/rsi_fvg.py`:
- Delete the `Direction` class and the `Signal` dataclass definitions.
- Change relative imports to two-dot form: `from ..bars import Bars`, `from ..fvg import FvgArrays, detect_fvg`, `from ..indicators import ...`, `from ..params import StrategyParams`, and add `from ..signals import Direction, Signal`.
- In `run_direction`, build the signal with `variant=variant.value` (a plain str) instead of `variant=variant`.
- Remove `IntEnum` from the enum import if no longer used (`State` still uses it — keep).

Recreate `rsi_fvg/strategy.py` as the shim:
```python
"""Backward-compatible shim: the RSI-FVG strategy now lives in rsi_fvg.strategies.rsi_fvg."""
from .signals import Direction, Signal  # noqa: F401
from .strategies.rsi_fvg import (Indicators, State, Variant, compute_indicators,  # noqa: F401
                                 run_direction, run_strategy)

__all__ = ["Direction", "Signal", "Indicators", "State", "Variant", "compute_indicators",
           "run_direction", "run_strategy"]
```

- [ ] **Step 4: Update the engine**

In `rsi_fvg/backtest/engine.py`:
- Replace `from ..strategy import Direction, Signal` with `from ..signals import Direction, Signal`.
- Replace `variant_name = signals[0].variant.value if signals else ""` with `variant_name = signals[0].variant if signals else ""`.
- In `close_position`, replace `"variant": pos.signal.variant.value` with `"variant": pos.signal.variant`.
- In `skip`, replace `"variant": s.variant.value` with `"variant": s.variant`.

In `tests/test_engine.py`, the `sig()` helper passes `variant=Variant.A`; change it to `variant="A"` and drop the `Variant` import (keep `Direction, Signal` imported from `rsi_fvg.signals`).

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -q`
Expected: all passed. `tests/test_strategy.py` still imports from `rsi_fvg.strategy` and asserts `s.variant == Variant.B` — that holds because `Variant` is a `str` enum and `"B" == Variant.B` is `True`.

- [ ] **Step 6: Commit**

```bash
git add rsi_fvg/signals.py rsi_fvg/strategies rsi_fvg/strategy.py rsi_fvg/backtest/engine.py tests/test_signals.py tests/test_engine.py
git commit -m "refactor: shared signals module, strategies as plugins"
```

---

### Task 11: RSI2 Swing strategy plugin

**Files:**
- Create: `rsi_fvg/strategies/rsi2_swing.py`, `tests/test_rsi2_swing.py`

**Interfaces:**
- Consumes: `Bars`, `rsi_wilder`, `atr_wilder`, `Direction`, `Signal`.
- Produces:
  - `Rsi2SwingParams(rsi_slow=14, overbought=75.0, oversold=25.0, rsi_fast=2, fast_hi=90.0, fast_lo=10.0, atr_len=14, atr_mult=1.0, max_wait=0)` frozen dataclass
  - `cross_up(x: np.ndarray, level: float) -> np.ndarray[bool]` — `x[t-1] <= level < x[t]`, False where NaN, False at index 0
  - `cross_down(x, level)` — `x[t-1] >= level > x[t]`
  - `SwingEvents(seg: np.ndarray[int8], low_conf: np.ndarray[bool], low_price: np.ndarray[float], high_conf: np.ndarray[bool], high_price: np.ndarray[float])`
  - `swing_structure(high, low, f_up, f_dn) -> SwingEvents` — spec §2.2
  - `run_direction(direction, bars, rsi_slow, rsi_fast, atr, params) -> list[Signal]` — spec §2.3, `variant="SWING"`, `swing_price` set, `bars_in_wait = t - anchor`
  - `run_strategy(bars, params, directions=(BUY, SELL)) -> list[Signal]` sorted by `(signal_bar, direction)`
  - `compute_inputs(bars, params) -> tuple[rsi_slow, rsi_fast, atr]`

- [ ] **Step 1: Write failing tests**

`tests/test_rsi2_swing.py`:
```python
import numpy as np
import pytest

from rsi_fvg.bars import Bars
from rsi_fvg.signals import Direction
from rsi_fvg.strategies.rsi2_swing import (Rsi2SwingParams, cross_down, cross_up, run_direction,
                                           run_strategy, swing_structure)

P = Rsi2SwingParams()  # 75/25, 90/10, atr_mult 1


def _run(direction, bars, rs, rf, params=P, atr=1.0):
    n = len(bars)
    return run_direction(direction, bars, np.asarray(rs, float), np.asarray(rf, float), np.full(n, atr), params)


def test_cross_helpers_nan_safe():
    x = np.array([np.nan, 80, 95, 5, 50, 95])
    assert list(cross_up(x, 90)) == [False, False, True, False, False, True]
    assert list(cross_down(x, 10)) == [False, False, False, True, False, False]


def test_swing_structure_alternates_and_boundary_bar_in_both_segments(mk_bars):
    h = [10, 11, 15, 14, 13, 12, 16, 17.0]
    l = [9, 10, 14, 13, 11, 10, 15, 16.0]
    bars = mk_bars(o=h, h=h, l=l, c=h)
    f_up = np.array([0, 1, 0, 0, 0, 0, 1, 0], bool)   # HIGH seg starts t=1, LOW seg ends t=6
    f_dn = np.array([0, 0, 0, 1, 0, 0, 0, 0], bool)   # HIGH seg ends / LOW seg starts t=3
    ev = swing_structure(bars.high, bars.low, f_up, f_dn)
    assert list(ev.seg) == [0, 1, 1, -1, -1, -1, 1, 1]
    assert ev.high_conf[3] and ev.high_price[3] == 15.0        # highest high over t=1..3 (boundary t=3 included)
    assert ev.low_conf[6] and ev.low_price[6] == 10.0          # lowest low over t=3..6 (t=3 low=13, t=5 low=10)
    assert ev.low_conf.sum() == 1 and ev.high_conf.sum() == 1


def test_buy_basic_flow(mk_bars):
    #      t:  0    1    2    3    4    5    6
    l =      [99, 100, 101, 98,  97,  96.5, 99]
    h =      [101, 102, 103, 100, 99, 98,  102]
    bars = mk_bars(o=l, h=h, l=l, c=h)
    rs =     [70, 80,  80,  80,  80,  80,  80]     # s_up at t=1
    rf =     [50, 95,  95,  5,   5,   5,   95]     # f_dn t=3 -> TRACKING, f_up t=6 -> signal
    sigs = _run(Direction.BUY, bars, rs, rf)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == Direction.BUY and s.variant == "SWING"
    assert s.signal_bar == 6 and s.anchor_bar == 1 and s.bars_in_wait == 5
    assert s.swing_price == 96.5                 # min(low[3..6])
    assert s.sl_price == pytest.approx(95.5)     # swing - 1*ATR
    assert s.ref_price == 102.0


def test_low_segment_started_before_flag_is_ignored(mk_bars):
    n = 9
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[99] * n, c=[100] * n)
    rs = [70, 70, 80, 80, 80, 80, 80, 80, 80]          # s_up at t=2
    rf = [95, 5, 5, 5, 95, 95, 5, 5, 95]               # LOW seg t=1..4 (started before flag), next LOW seg t=6..8
    sigs = _run(Direction.BUY, bars, rs, rf)
    assert [s.signal_bar for s in sigs] == [8]          # not 4
    assert sigs[0].anchor_bar == 2


def test_recross_while_tracking_resets(mk_bars):
    n = 9
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[99] * n, c=[100] * n)
    rs = [70, 80, 80, 80, 70, 80, 80, 80, 80]          # s_up t=1, s_up again t=5 (70->80)
    rf = [95, 95, 5, 5, 5, 5, 95, 5, 95]               # TRACKING from t=2; f_up at t=6 would trigger, but reset at t=5
    sigs = _run(Direction.BUY, bars, rs, rf)
    # after reset at t=5 state is ARMED; f_dn at t=7 -> TRACKING; f_up at t=8 -> signal anchored at 5
    assert [(s.signal_bar, s.anchor_bar) for s in sigs] == [(8, 5)]


def test_one_flag_one_signal(mk_bars):
    n = 9
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[99] * n, c=[100] * n)
    rs = [70, 80, 80, 80, 80, 80, 80, 80, 80]
    rf = [95, 95, 5, 95, 5, 95, 5, 95, 5]               # several LOW segments, only first after flag fires
    sigs = _run(Direction.BUY, bars, rs, rf)
    assert [s.signal_bar for s in sigs] == [3]


def test_max_wait_expiry(mk_bars):
    n = 8
    bars = mk_bars(o=[100] * n, h=[101] * n, l=[99] * n, c=[100] * n)
    rs = [70, 80, 80, 80, 80, 80, 80, 80]
    rf = [95, 95, 95, 95, 95, 5, 5, 95]                # f_dn at t=5 (t-anchor=4), f_up at t=7 (t-anchor=6)
    assert _run(Direction.BUY, bars, rs, rf, Rsi2SwingParams(max_wait=5)) == []      # expires at t=7 before trigger
    assert len(_run(Direction.BUY, bars, rs, rf, Rsi2SwingParams(max_wait=6))) == 1  # 6 > 6 is False -> trigger


def test_sell_mirror(mk_bars):
    h =      [101, 100, 99, 102, 103, 103.5, 100]
    l =      [99, 98, 97, 100, 101, 101.5, 98]
    bars = mk_bars(o=l, h=h, l=l, c=l)
    rs =     [30, 20, 20, 20, 20, 20, 20]              # s_dn at t=1
    rf =     [50, 5, 5, 95, 95, 95, 5]                 # f_up t=3 -> TRACKING high, f_dn t=6 -> signal
    sigs = _run(Direction.SELL, bars, rs, rf)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == Direction.SELL and s.signal_bar == 6 and s.anchor_bar == 1
    assert s.swing_price == 103.5 and s.sl_price == pytest.approx(104.5)


def test_run_strategy_smoke_deterministic():
    rng = np.random.default_rng(3)
    n = 5000
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    bars = Bars(time=np.arange(n, dtype=np.int64) * 300, open=open_, high=high, low=low, close=close)
    sigs = run_strategy(bars, P)
    assert len(sigs) > 0
    keys = [(s.signal_bar, int(s.direction)) for s in sigs]
    assert keys == sorted(keys) and sigs == run_strategy(bars, P)
    for s in sigs:
        assert s.variant == "SWING" and s.anchor_bar < s.signal_bar
        if s.direction == Direction.BUY:
            assert s.sl_price < s.swing_price <= bars.low[s.anchor_bar:s.signal_bar + 1].max()
            assert s.swing_price >= bars.low[s.anchor_bar:s.signal_bar + 1].min()
        else:
            assert s.sl_price > s.swing_price >= bars.high[s.anchor_bar:s.signal_bar + 1].min()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rsi2_swing.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.strategies.rsi2_swing'`.

- [ ] **Step 3: Write rsi_fvg/strategies/rsi2_swing.py**

```python
"""RSI2 Swing Pullback strategy — line-by-line port of pine/rsi2_swing_strategy.pine.

Spec: docs/superpowers/specs/2026-09-08-rsi2-swing-backtest-optimizer-design.md §2.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum

import numpy as np

from ..bars import Bars
from ..indicators import atr_wilder, rsi_wilder
from ..signals import Direction, Signal

VARIANT = "SWING"


@dataclass(frozen=True)
class Rsi2SwingParams:
    rsi_slow: int = 14
    overbought: float = 75.0
    oversold: float = 25.0
    rsi_fast: int = 2
    fast_hi: float = 90.0
    fast_lo: float = 10.0
    atr_len: int = 14
    atr_mult: float = 1.0
    max_wait: int = 0  # bars from flag to entry; 0 = never expires


class State(IntEnum):
    IDLE = 0
    ARMED = 1
    TRACKING = 2


def cross_up(x: np.ndarray, level: float) -> np.ndarray:
    x = np.asarray(x, float)
    out = np.zeros(x.shape[0], dtype=bool)
    if x.shape[0] > 1:
        prev, cur = x[:-1], x[1:]
        out[1:] = (prev <= level) & (cur > level) & ~np.isnan(prev) & ~np.isnan(cur)
    return out


def cross_down(x: np.ndarray, level: float) -> np.ndarray:
    x = np.asarray(x, float)
    out = np.zeros(x.shape[0], dtype=bool)
    if x.shape[0] > 1:
        prev, cur = x[:-1], x[1:]
        out[1:] = (prev >= level) & (cur < level) & ~np.isnan(prev) & ~np.isnan(cur)
    return out


@dataclass
class SwingEvents:
    seg: np.ndarray         # int8: 0 undefined, 1 HIGH segment, -1 LOW segment (state after bar t)
    low_conf: np.ndarray    # bool: swing low confirmed at bar t
    low_price: np.ndarray   # float: the confirmed swing low (NaN elsewhere)
    high_conf: np.ndarray
    high_price: np.ndarray


def swing_structure(high: np.ndarray, low: np.ndarray, f_up: np.ndarray, f_dn: np.ndarray) -> SwingEvents:
    n = high.shape[0]
    seg = np.zeros(n, dtype=np.int8)
    low_conf = np.zeros(n, dtype=bool)
    high_conf = np.zeros(n, dtype=bool)
    low_price = np.full(n, np.nan)
    high_price = np.full(n, np.nan)
    cur = 0
    seg_high = math.nan
    seg_low = math.nan
    for t in range(n):
        # 1. extend the running extreme (boundary bar belongs to both segments)
        if cur == 1:
            seg_high = max(seg_high, high[t])
        elif cur == -1:
            seg_low = min(seg_low, low[t])
        # 2. transitions
        if f_up[t]:
            if cur == -1:
                low_conf[t] = True
                low_price[t] = seg_low
            cur = 1
            seg_high = high[t]
        if f_dn[t]:
            if cur == 1:
                high_conf[t] = True
                high_price[t] = seg_high
            cur = -1
            seg_low = low[t]
        seg[t] = cur
    return SwingEvents(seg, low_conf, low_price, high_conf, high_price)


def compute_inputs(bars: Bars, params: Rsi2SwingParams) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (rsi_wilder(bars.close, params.rsi_slow),
            rsi_wilder(bars.close, params.rsi_fast),
            atr_wilder(bars.high, bars.low, bars.close, params.atr_len))


def run_direction(direction: Direction, bars: Bars, rsi_slow: np.ndarray, rsi_fast: np.ndarray,
                  atr: np.ndarray, params: Rsi2SwingParams) -> list[Signal]:
    buy = direction == Direction.BUY
    n = len(bars)
    close, high, low = bars.close, bars.high, bars.low
    arm = cross_up(rsi_slow, params.overbought) if buy else cross_down(rsi_slow, params.oversold)
    f_up = cross_up(rsi_fast, params.fast_hi)
    f_dn = cross_down(rsi_fast, params.fast_lo)
    seg_start = f_dn if buy else f_up      # the segment we track starts here
    seg_end = f_up if buy else f_dn        # ... and its extreme is confirmed here

    state = State.IDLE
    anchor = -1
    run_ext = math.nan
    out: list[Signal] = []
    for t in range(1, n):
        if (math.isnan(rsi_slow[t]) or math.isnan(rsi_slow[t - 1]) or math.isnan(rsi_fast[t])
                or math.isnan(rsi_fast[t - 1]) or math.isnan(atr[t])):
            continue
        if state == State.IDLE:
            if arm[t]:
                state, anchor, run_ext = State.ARMED, t, math.nan
            continue
        if arm[t]:                                   # re-cross: replace the setup
            state, anchor, run_ext = State.ARMED, t, math.nan
            continue
        if params.max_wait > 0 and (t - anchor) > params.max_wait:
            state, anchor, run_ext = State.IDLE, -1, math.nan
            continue
        if state == State.ARMED:
            if seg_start[t]:
                state = State.TRACKING
                run_ext = low[t] if buy else high[t]
            continue
        # TRACKING
        run_ext = min(run_ext, low[t]) if buy else max(run_ext, high[t])
        if seg_end[t]:
            sl = run_ext - params.atr_mult * atr[t] if buy else run_ext + params.atr_mult * atr[t]
            out.append(Signal(direction=direction, variant=VARIANT, signal_bar=t, anchor_bar=anchor,
                              ref_price=float(close[t]), sl_price=float(sl), bars_in_wait=t - anchor,
                              swing_price=float(run_ext)))
            state, anchor, run_ext = State.IDLE, -1, math.nan
    return out


def run_strategy(bars: Bars, params: Rsi2SwingParams,
                 directions: tuple[Direction, ...] = (Direction.BUY, Direction.SELL)) -> list[Signal]:
    rs, rf, atr = compute_inputs(bars, params)
    out: list[Signal] = []
    for d in directions:
        out.extend(run_direction(d, bars, rs, rf, atr, params))
    out.sort(key=lambda s: (s.signal_bar, int(s.direction)))
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rsi2_swing.py -q`
Expected: `9 passed`. If `test_recross_while_tracking_resets` fails, trace `rs`/`rf` bar by bar against spec §2.3 — the expected `(8, 5)` follows from: t=1 arm, t=2 f_dn→TRACKING, t=5 arm→reset ARMED (f_dn at t=5 is not processed that bar), t=6 f_up in ARMED does nothing, t=7 f_dn→TRACKING, t=8 f_up→signal.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/strategies/rsi2_swing.py tests/test_rsi2_swing.py
git commit -m "feat: RSI2 swing pullback strategy plugin"
```

---

### Task 12: Extra metrics (spec §3)

**Files:**
- Modify: `rsi_fvg/backtest/metrics.py`
- Create: `tests/test_metrics_extra.py`

**Interfaces:**
- `compute_metrics(trades, equity, initial_equity, n_blocked=0, n_bars=None)` — new optional `n_bars`; dict gains keys `avg_win_r, avg_loss_r, expectancy_usd, sortino_daily, calmar, max_consec_losses, time_in_market_pct` (all `0.0`/`0` in the empty case).
- `monthly_table(equity: pd.Series) -> pd.DataFrame` — index = year, columns = 1..12, values = month-over-month equity change in percent (NaN where no data). Empty Series → empty DataFrame.
- `max_consecutive_losses(pnl: pd.Series) -> int`

- [ ] **Step 1: Write failing tests**

`tests/test_metrics_extra.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_metrics_extra.py -q`
Expected: `ImportError: cannot import name 'max_consecutive_losses'`.

- [ ] **Step 3: Extend rsi_fvg/backtest/metrics.py**

Add these functions (after `_cagr`) and update `compute_metrics`:

```python
def max_consecutive_losses(pnl: pd.Series) -> int:
    best = cur = 0
    for v in pnl.astype(float):
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return int(best)


def _sortino_daily(equity: pd.Series) -> float:
    if len(equity) < 3:
        return 0.0
    daily = equity.resample("1D").last().dropna().pct_change().dropna()
    downside = daily[daily < 0]
    if len(daily) < 2 or len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(daily.mean() / downside.std() * np.sqrt(252))


def monthly_table(equity: pd.Series) -> pd.DataFrame:
    if equity.empty:
        return pd.DataFrame()
    monthly = equity.resample("1ME").last().dropna()
    prev = monthly.shift(1)
    prev.iloc[0] = equity.iloc[0]
    ret = (monthly / prev - 1.0) * 100.0
    df = pd.DataFrame({"year": ret.index.year, "month": ret.index.month, "ret": ret.values})
    return df.pivot(index="year", columns="month", values="ret").reindex(columns=range(1, 13))
```

Replace the body of `compute_metrics` with (signature adds `n_bars: int | None = None`):

```python
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_metrics_extra.py tests/test_metrics.py -q`
Expected: all passed (the Phase 1 metrics tests must still pass — `test_compute_metrics_empty` asserts on keys that still exist).

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/backtest/metrics.py tests/test_metrics_extra.py
git commit -m "feat: sortino, calmar, consecutive losses, time in market, monthly table"
```

---

### Task 13: Optimizer — grid, IS/OOS, robustness, recommendation

**Files:**
- Create: `rsi_fvg/backtest/optimize.py`, `tests/test_optimize.py`

**Interfaces:**
- Consumes: `Bars`, `SymbolSpec`, `CostParams`, `SizingParams`, `Rsi2SwingParams`, `run_strategy` (rsi2_swing), `run_backtest`, `BacktestResult`, `compute_metrics`, `equity_from_trades`.
- Produces:
  - `GridSpec(tp_r=(1,1.5,2,3,4), atr_mult=(0,0.5,1,1.5,2), rsi_slow_levels=((70,30),(75,25),(80,20)), rsi_fast_levels=((85,15),(90,10),(95,5)))` with `.size() -> int`
  - `KEY_COLS = ["tf", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r"]`
  - `SPLIT_KEYS = ("n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct", "net_pnl", "expectancy_usd")`
  - `split_time(bars, is_frac) -> pd.Timestamp`
  - `make_params(base, ob, os_, f_hi, f_lo, atr_mult) -> Rsi2SwingParams`
  - `run_single(bars, spec, params, tp_r, costs, sizing, concurrency) -> tuple[list[Signal], BacktestResult]`
  - `run_optimization(bars_by_tf, spec_by_tf, base, grid, costs, sizing, concurrency="hedge", is_frac=0.7, progress=None) -> pd.DataFrame` — one row per combo, columns: `KEY_COLS + ["n_signals", "split_time", "oversized_share"] + compute_metrics keys + is_<k>/oos_<k> for SPLIT_KEYS + ["robust_r", "robust_ratio", "flags"]`. `progress(done: int, total: int)` is called after every engine run when given.
  - `add_robustness(df, grid) -> pd.DataFrame`
  - `compute_flags(row) -> list[str]` — subset of `["n<30", "oos_sign_flip", "buy_sell_imbalance", "oversized"]`
  - `recommend(df, min_trades=30) -> dict[str, dict | None]` — per TF: `{"params": {KEY_COLS...}, "score": float, "row": dict, "reason": str}` or `None`.

- [ ] **Step 1: Write failing tests**

`tests/test_optimize.py`:
```python
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rsi_fvg.backtest.optimize import (KEY_COLS, SPLIT_KEYS, GridSpec, add_robustness, compute_flags,
                                       recommend, run_optimization, run_single, split_time)
from rsi_fvg.bars import Bars
from rsi_fvg.params import CostParams, SizingParams, SymbolSpec
from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams

SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0)
COSTS = CostParams(spread_points=20, commission_per_lot_rt=0.0, slippage_points=0)
SIZING = SizingParams(risk_pct=5.0, initial_equity=10_000.0)
SMALL = GridSpec(tp_r=(1.0, 2.0), atr_mult=(0.5, 1.0), rsi_slow_levels=((75.0, 25.0),), rsi_fast_levels=((90.0, 10.0),))


def _bars(n=6000, seed=11):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    return Bars(time=1_700_000_000 + np.arange(n, dtype=np.int64) * 300, open=open_, high=high, low=low, close=close)


def test_grid_size_default_and_small():
    assert GridSpec().size() == 225 and SMALL.size() == 4


def test_split_time_70_30():
    b = _bars(1000)
    assert split_time(b, 0.7) == b.datetimes()[700]


def test_run_optimization_rows_and_columns():
    b = _bars()
    calls = []
    df = run_optimization({"M5": b}, {"M5": SPEC}, Rsi2SwingParams(), SMALL, COSTS, SIZING,
                          progress=lambda d, t: calls.append((d, t)))
    assert len(df) == 4 and calls[-1] == (4, 4)
    for c in KEY_COLS + ["n_signals", "split_time", "oversized_share", "robust_r", "robust_ratio", "flags",
                         "n_trades", "avg_r", "max_dd_pct", "sortino_daily", "time_in_market_pct"]:
        assert c in df.columns
    for k in SPLIT_KEYS:
        assert f"is_{k}" in df.columns and f"oos_{k}" in df.columns
    assert (df["is_n_trades"] + df["oos_n_trades"] == df["n_trades"]).all()
    assert df.groupby("atr_mult")["n_signals"].nunique().eq(1).all()      # signals depend on atr_mult, not tp
    assert df["flags"].map(lambda s: isinstance(s, str)).all()


def test_run_single_matches_grid_row():
    b = _bars()
    df = run_optimization({"M5": b}, {"M5": SPEC}, Rsi2SwingParams(), SMALL, COSTS, SIZING)
    row = df.iloc[0]
    params = Rsi2SwingParams(atr_mult=row.atr_mult)
    sigs, res = run_single(b, SPEC, params, row.tp_r, COSTS, SIZING, "hedge")
    assert len(sigs) == row.n_signals and len(res.trades) == row.n_trades


def test_add_robustness_median_of_neighbours():
    grid = GridSpec(tp_r=(1.0, 2.0), atr_mult=(0.5, 1.0), rsi_slow_levels=((75, 25),), rsi_fast_levels=((90, 10),))
    df = pd.DataFrame({"tf": "M5", "ob": 75.0, "os": 25.0, "f_hi": 90.0, "f_lo": 10.0,
                       "tp_r": [1.0, 1.0, 2.0, 2.0], "atr_mult": [0.5, 1.0, 0.5, 1.0],
                       "is_avg_r": [1.0, 2.0, 3.0, 4.0]})
    out = add_robustness(df, grid)
    assert out.loc[0, "robust_r"] == pytest.approx(3.0)      # neighbours 2,3,4 -> median 3
    assert out.loc[3, "robust_r"] == pytest.approx(2.0)      # neighbours 1,2,3 -> median 2
    assert out.loc[0, "robust_ratio"] == pytest.approx(1.5)  # 3/1 clipped to 1.5
    assert out.loc[3, "robust_ratio"] == pytest.approx(0.5)


def test_compute_flags():
    r = pd.Series({"n_trades": 10, "is_avg_r": 0.5, "oos_avg_r": -0.2, "n_buy": 9, "n_sell": 1, "oversized_share": 0.2})
    assert compute_flags(r) == ["n<30", "oos_sign_flip", "buy_sell_imbalance", "oversized"]
    ok = pd.Series({"n_trades": 50, "is_avg_r": 0.5, "oos_avg_r": 0.3, "n_buy": 20, "n_sell": 30, "oversized_share": 0.0})
    assert compute_flags(ok) == []


def _grid_df(rows):
    cols = {"tf": "M5", "ob": 75.0, "os": 25.0, "f_hi": 90.0, "f_lo": 10.0, "atr_mult": 1.0, "tp_r": 2.0,
            "is_n_trades": 40, "oos_n_trades": 15, "is_avg_r": 0.3, "oos_avg_r": 0.2, "robust_r": 0.25,
            "oversized_share": 0.0, "max_dd_pct": 0.1, "win_rate": 0.4, "n_buy": 20, "n_sell": 20, "n_trades": 55}
    return pd.DataFrame([cols | r for r in rows])


def test_recommend_none_when_nothing_qualifies():
    df = _grid_df([{"is_n_trades": 10}, {"oos_avg_r": -0.1}, {"oversized_share": 0.5}])
    assert recommend(df) == {"M5": None}


def test_recommend_picks_best_score_and_explains():
    df = _grid_df([{"tp_r": 1.0, "oos_avg_r": 0.10, "robust_r": 0.10, "is_avg_r": 0.10},
                   {"tp_r": 2.0, "oos_avg_r": 0.40, "robust_r": 0.35, "is_avg_r": 0.30},
                   {"tp_r": 3.0, "oos_avg_r": 0.20, "robust_r": 0.20, "is_avg_r": 0.50}])
    rec = recommend(df)["M5"]
    assert rec is not None and rec["params"]["tp_r"] == 2.0
    assert set(rec["params"]) == set(KEY_COLS)
    assert "OOS" in rec["reason"] and "robust" in rec["reason"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_optimize.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.backtest.optimize'`.

- [ ] **Step 3: Write rsi_fvg/backtest/optimize.py**

```python
"""Grid optimisation with IS/OOS split, neighbourhood robustness and auto-recommendation (spec §4)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

import numpy as np
import pandas as pd

from ..bars import Bars
from ..params import CostParams, SizingParams, SymbolSpec
from ..signals import Signal
from ..strategies.rsi2_swing import Rsi2SwingParams, run_strategy
from .engine import BacktestResult, run_backtest
from .metrics import compute_metrics, equity_from_trades

KEY_COLS = ["tf", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r"]
SPLIT_KEYS = ("n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct", "net_pnl", "expectancy_usd")
MIN_TRADES = 30
OVERSIZED_MAX = 0.10


@dataclass(frozen=True)
class GridSpec:
    tp_r: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 4.0)
    atr_mult: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0)
    rsi_slow_levels: tuple[tuple[float, float], ...] = ((70.0, 30.0), (75.0, 25.0), (80.0, 20.0))
    rsi_fast_levels: tuple[tuple[float, float], ...] = ((85.0, 15.0), (90.0, 10.0), (95.0, 5.0))

    def size(self) -> int:
        return len(self.tp_r) * len(self.atr_mult) * len(self.rsi_slow_levels) * len(self.rsi_fast_levels)


def split_time(bars: Bars, is_frac: float) -> pd.Timestamp:
    idx = min(max(int(len(bars) * is_frac), 0), len(bars) - 1)
    return bars.datetimes()[idx]


def make_params(base: Rsi2SwingParams, ob: float, os_: float, f_hi: float, f_lo: float,
                atr_mult: float) -> Rsi2SwingParams:
    return replace(base, overbought=float(ob), oversold=float(os_), fast_hi=float(f_hi),
                   fast_lo=float(f_lo), atr_mult=float(atr_mult))


def run_single(bars: Bars, spec: SymbolSpec, params: Rsi2SwingParams, tp_r: float, costs: CostParams,
               sizing: SizingParams, concurrency: str) -> tuple[list[Signal], BacktestResult]:
    signals = run_strategy(bars, params)
    return signals, run_backtest(bars, signals, float(tp_r), spec, costs, sizing, concurrency)


def run_optimization(bars_by_tf: dict[str, Bars], spec_by_tf: dict[str, SymbolSpec], base: Rsi2SwingParams,
                     grid: GridSpec, costs: CostParams, sizing: SizingParams, concurrency: str = "hedge",
                     is_frac: float = 0.7, progress: Callable[[int, int], None] | None = None) -> pd.DataFrame:
    total = grid.size() * len(bars_by_tf)
    init = sizing.initial_equity
    rows: list[dict] = []
    for tf, bars in bars_by_tf.items():
        split = split_time(bars, is_frac)
        n_bars = len(bars)
        spec = spec_by_tf[tf]
        for ob, os_ in grid.rsi_slow_levels:
            for f_hi, f_lo in grid.rsi_fast_levels:
                for am in grid.atr_mult:
                    params = make_params(base, ob, os_, f_hi, f_lo, am)
                    signals = run_strategy(bars, params)
                    for tp in grid.tp_r:
                        res = run_backtest(bars, signals, float(tp), spec, costs, sizing, concurrency)
                        tr = res.trades
                        n_blocked = int((res.skipped["reason"] == "blocked").sum()) if len(res.skipped) else 0
                        full = compute_metrics(tr, res.equity, init, n_blocked=n_blocked, n_bars=n_bars)
                        is_tr = tr[tr["entry_time"] < split]
                        oos_tr = tr[tr["entry_time"] >= split]
                        is_m = compute_metrics(is_tr, equity_from_trades(is_tr, init), init)
                        oos_m = compute_metrics(oos_tr, equity_from_trades(oos_tr, init), init)
                        row = {"tf": tf, "ob": float(ob), "os": float(os_), "f_hi": float(f_hi), "f_lo": float(f_lo),
                               "atr_mult": float(am), "tp_r": float(tp), "n_signals": len(signals),
                               "split_time": split,
                               "oversized_share": float(tr["oversized"].astype(bool).mean()) if len(tr) else 0.0}
                        row.update(full)
                        row.update({f"is_{k}": is_m[k] for k in SPLIT_KEYS})
                        row.update({f"oos_{k}": oos_m[k] for k in SPLIT_KEYS})
                        rows.append(row)
                        if progress:
                            progress(len(rows), total)
    df = pd.DataFrame(rows)
    df = add_robustness(df, grid)
    df["flags"] = df.apply(lambda r: ";".join(compute_flags(r)), axis=1)
    return df


def add_robustness(df: pd.DataFrame, grid: GridSpec) -> pd.DataFrame:
    df = df.reset_index(drop=True).copy()
    tp_idx = {float(v): i for i, v in enumerate(grid.tp_r)}
    am_idx = {float(v): i for i, v in enumerate(grid.atr_mult)}
    ti = df["tp_r"].astype(float).map(tp_idx).to_numpy()
    ai = df["atr_mult"].astype(float).map(am_idx).to_numpy()
    vals = df["is_avg_r"].astype(float).to_numpy()
    robust = np.full(len(df), np.nan)
    for _, g in df.groupby(["tf", "ob", "f_hi"], sort=False):
        idx = g.index.to_numpy()
        for k in idx:
            mask = (np.abs(ti[idx] - ti[k]) <= 1) & (np.abs(ai[idx] - ai[k]) <= 1)
            mask &= idx != k
            if mask.any():
                robust[k] = float(np.median(vals[idx[mask]]))
    df["robust_r"] = np.nan_to_num(robust, nan=0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(vals > 0, np.clip(df["robust_r"].to_numpy() / vals, 0.0, 1.5), 0.0)
    df["robust_ratio"] = ratio
    return df


def compute_flags(row) -> list[str]:
    flags: list[str] = []
    if row["n_trades"] < MIN_TRADES:
        flags.append("n<30")
    if row["is_avg_r"] > 0 and row["oos_avg_r"] < 0:
        flags.append("oos_sign_flip")
    nb, ns = int(row["n_buy"]), int(row["n_sell"])
    if (nb + ns) > 0 and max(nb, ns) / max(1, min(nb, ns)) > 2:
        flags.append("buy_sell_imbalance")
    if row["oversized_share"] > OVERSIZED_MAX:
        flags.append("oversized")
    return flags


def _zscore(s: pd.Series) -> pd.Series:
    sd = float(s.std(ddof=0))
    return (s - s.mean()) / sd if sd > 0 else s * 0.0


def _reason(r: pd.Series) -> str:
    return (f"IS {int(r['is_n_trades'])} trades avg {r['is_avg_r']:+.2f}R · "
            f"OOS {int(r['oos_n_trades'])} trades avg {r['oos_avg_r']:+.2f}R · "
            f"robust_r {r['robust_r']:+.2f} · max DD {r['max_dd_pct']:.1%} · "
            f"win rate {r['win_rate']:.0%} · BUY/SELL {int(r['n_buy'])}/{int(r['n_sell'])}")


def recommend(df: pd.DataFrame, min_trades: int = MIN_TRADES) -> dict[str, dict | None]:
    out: dict[str, dict | None] = {}
    for tf, g in df.groupby("tf", sort=False):
        f = g[(g["is_n_trades"] >= min_trades) & (g["is_avg_r"] > 0) & (g["oos_avg_r"] > 0)
              & (g["oversized_share"] <= OVERSIZED_MAX)]
        if f.empty:
            out[tf] = None
            continue
        score = 0.5 * _zscore(f["oos_avg_r"].astype(float)) + 0.3 * _zscore(f["robust_r"].astype(float)) \
            + 0.2 * _zscore(f["is_avg_r"].astype(float))
        best = f.loc[score.idxmax()]
        out[tf] = {"params": {k: (best[k] if k == "tf" else float(best[k])) for k in KEY_COLS},
                   "score": float(score.max()), "row": best.to_dict(), "reason": _reason(best)}
    return out
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_optimize.py -q`
Expected: `8 passed`. `test_run_optimization_rows_and_columns` runs 2 strategy passes + 4 engine runs on 6000 bars — under 5 s.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/backtest/optimize.py tests/test_optimize.py
git commit -m "feat: grid optimizer with IS/OOS, neighbourhood robustness and recommendation"
```

---

### Task 14: Export — Excel workbook + HTML report

**Files:**
- Create: `rsi_fvg/backtest/export.py`, `tests/test_export.py`
- Modify: `requirements.txt` (add `openpyxl>=3.1`, `plotly>=5.20`)

**Interfaces:**
- Consumes: grid DataFrame from `run_optimization`, `recommend` dict, `BacktestResult`, `monthly_table`, `KEY_COLS`.
- Produces:
  - `write_csvs(out_dir: Path, grid_df, rec_results: dict[str, BacktestResult]) -> None` → `grid.csv`, `trades_<TF>.csv`
  - `write_xlsx(path: Path, grid_df, rec: dict, rec_results: dict[str, BacktestResult], run_info: dict) -> None` — sheets `Summary`, `Grid`, `Trades_<TF>`, `Monthly_<TF>`, `Equity_<TF>` (one set per TF present in `rec_results`), `Params`
  - `write_html(path: Path, grid_df, rec, rec_results, run_info, offline: bool = False) -> None`
  - `run_info` keys used: `symbol, timeframes (list), data_range (dict tf → (start, end)), initial_equity, risk_pct, concurrency, spread_points, commission_per_lot_rt, slippage_points, is_frac, grid (dict of lists), git_hash, generated_at`.

Before writing the plotting code, load the `dataviz` skill (Skill tool) and apply its guidance to colours, axis labels and layout — keep the function names, section order and file outputs exactly as below.

- [ ] **Step 1: Write failing tests**

`tests/test_export.py`:
```python
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

from rsi_fvg.backtest.export import write_csvs, write_html, write_xlsx
from rsi_fvg.backtest.optimize import GridSpec, recommend, run_optimization, run_single
from rsi_fvg.bars import Bars
from rsi_fvg.params import CostParams, SizingParams, SymbolSpec
from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams

SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0)
COSTS = CostParams(spread_points=20, commission_per_lot_rt=0.0, slippage_points=0)
SIZING = SizingParams(risk_pct=5.0, initial_equity=10_000.0)
SMALL = GridSpec(tp_r=(1.0, 2.0), atr_mult=(0.5, 1.0), rsi_slow_levels=((75.0, 25.0),), rsi_fast_levels=((90.0, 10.0),))


def _bars(n=6000, seed=5):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    return Bars(time=1_700_000_000 + np.arange(n, dtype=np.int64) * 300, open=open_, high=high, low=low, close=close)


def _fixture():
    b = _bars()
    df = run_optimization({"M5": b}, {"M5": SPEC}, Rsi2SwingParams(), SMALL, COSTS, SIZING)
    rec = recommend(df)
    row = df.iloc[0]
    _, res = run_single(b, SPEC, Rsi2SwingParams(atr_mult=row.atr_mult), row.tp_r, COSTS, SIZING, "hedge")
    info = {"symbol": "T", "timeframes": ["M5"], "data_range": {"M5": ("2023-11-14", "2023-12-05")},
            "initial_equity": 10_000, "risk_pct": 5.0, "concurrency": "hedge", "spread_points": 20,
            "commission_per_lot_rt": 0.0, "slippage_points": 0, "is_frac": 0.7,
            "grid": {"tp_r": [1, 2], "atr_mult": [0.5, 1], "rsi14": ["75/25"], "rsi2": ["90/10"]},
            "git_hash": "test", "generated_at": "2026-09-08 00:00"}
    return df, rec, {"M5": res}, info


def test_write_csvs(tmp_path):
    df, rec, res, info = _fixture()
    write_csvs(tmp_path, df, res)
    assert (tmp_path / "grid.csv").exists() and (tmp_path / "trades_M5.csv").exists()
    assert len(pd.read_csv(tmp_path / "grid.csv")) == 4


def test_write_xlsx_sheets_and_rows(tmp_path):
    df, rec, res, info = _fixture()
    p = tmp_path / "r.xlsx"
    write_xlsx(p, df, rec, res, info)
    wb = openpyxl.load_workbook(p, read_only=True)
    assert {"Summary", "Grid", "Trades_M5", "Monthly_M5", "Equity_M5", "Params"} <= set(wb.sheetnames)
    assert wb["Grid"].max_row == 5            # header + 4 combos
    head = [c.value for c in next(wb["Grid"].iter_rows(min_row=1, max_row=1))]
    assert head[:7] == ["tf", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r"]
    assert wb["Equity_M5"].max_row <= 20_001   # downsampled


def test_write_xlsx_handles_no_recommendation(tmp_path):
    df, _, res, info = _fixture()
    write_xlsx(tmp_path / "r.xlsx", df, {"M5": None}, res, info)
    wb = openpyxl.load_workbook(tmp_path / "r.xlsx", read_only=True)
    cells = [c.value for row in wb["Summary"].iter_rows() for c in row if isinstance(c.value, str)]
    assert any("no reliable" in v for v in cells)


def test_write_html_contents(tmp_path):
    df, rec, res, info = _fixture()
    p = tmp_path / "r.html"
    write_html(p, df, rec, res, info)
    html = p.read_text(encoding="utf-8")
    assert "Recommendation" in html and "plotly" in html.lower()
    assert "Heatmap" in html or "heatmap" in html
    assert "cdn.plot.ly" in html                   # cdn mode by default
    write_html(tmp_path / "off.html", df, rec, res, info, offline=True)
    assert (tmp_path / "off.html").stat().st_size > 1_000_000   # plotly.js embedded
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_export.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.backtest.export'`.

- [ ] **Step 3: Add dependencies**

Append to `requirements.txt`:
```
openpyxl>=3.1
plotly>=5.20
```
(Both are already installed in this environment: openpyxl 3.1.5, plotly 6.3.1.)

- [ ] **Step 4: Write rsi_fvg/backtest/export.py**

```python
"""Excel workbook + self-contained HTML report for the optimisation run (spec §5)."""
from __future__ import annotations

import html as _html
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from plotly.subplots import make_subplots

from .engine import BacktestResult
from .metrics import monthly_table
from .optimize import KEY_COLS

GRID_FIRST_COLS = KEY_COLS + ["n_signals", "n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct",
                              "net_pnl", "final_equity", "is_n_trades", "is_avg_r", "oos_n_trades", "oos_avg_r",
                              "robust_r", "robust_ratio", "flags"]
REC_COLS = ["n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct", "net_pnl",
            "is_n_trades", "is_avg_r", "oos_n_trades", "oos_avg_r", "robust_r", "robust_ratio"]
EQUITY_MAX_ROWS = 20_000
_RED, _WHITE, _GREEN = "F8696B", "FFFFFF", "63BE7B"


def _order_grid(df: pd.DataFrame) -> pd.DataFrame:
    first = [c for c in GRID_FIRST_COLS if c in df.columns]
    rest = [c for c in df.columns if c not in first]
    return df[first + rest]


def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if isinstance(out[c].dtype, pd.DatetimeTZDtype):
            out[c] = out[c].dt.tz_localize(None)
    return out


def _downsample(eq: pd.Series, max_rows: int = EQUITY_MAX_ROWS) -> pd.Series:
    step = max(1, int(np.ceil(len(eq) / max_rows)))
    return eq.iloc[::step]


def _equity_frame(res: BacktestResult) -> pd.DataFrame:
    eq = _downsample(res.equity)
    peak = eq.cummax()
    idx = eq.index.tz_localize(None) if eq.index.tz is not None else eq.index
    return pd.DataFrame({"time": idx, "equity": eq.values, "drawdown_usd": (peak - eq).values,
                         "drawdown_pct": ((peak - eq) / peak * 100).values})


def _rec_table(rec: dict) -> pd.DataFrame:
    rows = []
    for tf, r in rec.items():
        if r is None:
            rows.append({"tf": tf, "status": "no reliable parameter set (filters: IS n>=30, IS & OOS avg R > 0, oversized <= 10%)"})
        else:
            row = {"tf": tf, "status": "recommended"}
            row.update({k: r["params"][k] for k in KEY_COLS if k != "tf"})
            row.update({k: r["row"].get(k) for k in REC_COLS})
            row["reason"] = r["reason"]
            rows.append(row)
    return pd.DataFrame(rows)


def _info_table(run_info: dict) -> pd.DataFrame:
    flat = []
    for k, v in run_info.items():
        if k == "grid":
            for gk, gv in v.items():
                flat.append((f"grid.{gk}", ", ".join(str(x) for x in gv)))
        elif k == "data_range":
            for tf, (a, b) in v.items():
                flat.append((f"data.{tf}", f"{a} -> {b}"))
        elif isinstance(v, (list, tuple)):
            flat.append((k, ", ".join(str(x) for x in v)))
        else:
            flat.append((k, v))
    return pd.DataFrame(flat, columns=["key", "value"])


def write_csvs(out_dir: Path, grid_df: pd.DataFrame, rec_results: dict[str, BacktestResult]) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _order_grid(grid_df).to_csv(out_dir / "grid.csv", index=False)
    for tf, res in rec_results.items():
        res.trades.to_csv(out_dir / f"trades_{tf}.csv", index=False)


def _color_scale(ws, col_letter: str, first_row: int, last_row: int) -> None:
    if last_row < first_row:
        return
    ws.conditional_formatting.add(
        f"{col_letter}{first_row}:{col_letter}{last_row}",
        ColorScaleRule(start_type="min", start_color=_RED, mid_type="num", mid_value=0, mid_color=_WHITE,
                       end_type="max", end_color=_GREEN))


def _bold_header(ws, row: int = 1) -> None:
    for cell in ws[row]:
        cell.font = Font(bold=True)


def write_xlsx(path: Path, grid_df: pd.DataFrame, rec: dict, rec_results: dict[str, BacktestResult],
               run_info: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    grid = _order_grid(grid_df.copy())
    if "split_time" in grid.columns:
        grid["split_time"] = pd.to_datetime(grid["split_time"]).dt.tz_localize(None)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        info = _info_table(run_info)
        info.to_excel(xw, sheet_name="Summary", index=False, startrow=0)
        rec_tbl = _rec_table(rec)
        rec_tbl.to_excel(xw, sheet_name="Summary", index=False, startrow=len(info) + 3)
        ws = xw.sheets["Summary"]
        ws.cell(row=len(info) + 3, column=1, value="Recommendation per timeframe").font = Font(bold=True)
        _bold_header(ws, 1)
        _bold_header(ws, len(info) + 4)
        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 60

        grid.to_excel(xw, sheet_name="Grid", index=False)
        wg = xw.sheets["Grid"]
        wg.freeze_panes = "A2"
        wg.auto_filter.ref = wg.dimensions
        _bold_header(wg)
        for col in ("oos_avg_r", "is_avg_r", "avg_r", "robust_r"):
            if col in grid.columns:
                _color_scale(wg, get_column_letter(grid.columns.get_loc(col) + 1), 2, len(grid) + 1)

        for tf, res in rec_results.items():
            _strip_tz(res.trades).to_excel(xw, sheet_name=f"Trades_{tf}", index=False)
            _bold_header(xw.sheets[f"Trades_{tf}"])
            xw.sheets[f"Trades_{tf}"].freeze_panes = "A2"
            mt = monthly_table(res.equity)
            mt.to_excel(xw, sheet_name=f"Monthly_{tf}")
            if not mt.empty:
                _color_scale_block(xw.sheets[f"Monthly_{tf}"], 2, len(mt) + 1, 2, 13)
            _equity_frame(res).to_excel(xw, sheet_name=f"Equity_{tf}", index=False)
            _bold_header(xw.sheets[f"Equity_{tf}"])

        params = _info_table({k: run_info[k] for k in ("grid", "initial_equity", "risk_pct", "concurrency",
                                                        "spread_points", "commission_per_lot_rt",
                                                        "slippage_points", "is_frac", "git_hash") if k in run_info})
        params.to_excel(xw, sheet_name="Params", index=False)
        _bold_header(xw.sheets["Params"])


def _color_scale_block(ws, r1: int, r2: int, c1: int, c2: int) -> None:
    ws.conditional_formatting.add(
        f"{get_column_letter(c1)}{r1}:{get_column_letter(c2)}{r2}",
        ColorScaleRule(start_type="min", start_color=_RED, mid_type="num", mid_value=0, mid_color=_WHITE,
                       end_type="max", end_color=_GREEN))


# ------------------------------------------------------------------ HTML ----
_CSS = """
body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#222;background:#fafafa}
h1{font-size:22px} h2{font-size:18px;margin-top:36px;border-bottom:1px solid #ddd;padding-bottom:4px}
table{border-collapse:collapse;font-size:13px} th,td{border:1px solid #ddd;padding:4px 8px;text-align:right}
th{background:#f0f0f0} td:first-child,th:first-child{text-align:left}
.rec{background:#fff;border:1px solid #ddd;border-radius:6px;padding:12px 16px;margin:8px 0}
.rec.none{border-color:#e0a000} .warn{color:#a40000} .muted{color:#666;font-size:12px}
"""


def _fig_equity(tf: str, res: BacktestResult) -> go.Figure:
    eq = _downsample(res.equity, 5000)
    peak = eq.cummax()
    dd_pct = ((peak - eq) / peak * 100)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.04)
    fig.add_trace(go.Scatter(x=eq.index, y=eq.values, name="Equity", line=dict(width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=dd_pct.index, y=-dd_pct.values, name="Drawdown %", fill="tozeroy",
                             line=dict(width=1)), row=2, col=1)
    fig.update_layout(title=f"{tf} — Equity & drawdown (recommended parameters)", height=520,
                      margin=dict(l=40, r=20, t=50, b=30), legend=dict(orientation="h"))
    fig.update_yaxes(title_text="USD", row=1, col=1)
    fig.update_yaxes(title_text="DD %", row=2, col=1)
    return fig


def _fig_r_hist(tf: str, res: BacktestResult) -> go.Figure:
    fig = go.Figure(go.Histogram(x=res.trades["r_multiple"], nbinsx=40))
    fig.update_layout(title=f"{tf} — Distribution of R per trade", height=320, bargap=0.05,
                      margin=dict(l=40, r=20, t=50, b=30), xaxis_title="R", yaxis_title="trades")
    return fig


def _fig_heatmaps(tf: str, g: pd.DataFrame) -> go.Figure:
    combos = sorted(set(zip(g["ob"], g["os"], g["f_hi"], g["f_lo"])))
    n = len(combos)
    cols = min(3, n)
    rows = int(np.ceil(n / cols))
    titles = [f"RSI14 {int(ob)}/{int(os_)} · RSI2 {int(fh)}/{int(fl)}" for ob, os_, fh, fl in combos]
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=titles, horizontal_spacing=0.06, vertical_spacing=0.12)
    zmax = float(np.nanmax(np.abs(g["oos_avg_r"].to_numpy()))) if len(g) else 1.0
    zmax = max(zmax, 1e-9)
    for i, (ob, os_, fh, fl) in enumerate(combos):
        gg = g[(g["ob"] == ob) & (g["os"] == os_) & (g["f_hi"] == fh) & (g["f_lo"] == fl)]
        piv = gg.pivot(index="atr_mult", columns="tp_r", values="oos_avg_r").sort_index()
        ntr = gg.pivot(index="atr_mult", columns="tp_r", values="n_trades").reindex_like(piv)
        text = [[f"{v:+.2f}<br>n={int(k)}" for v, k in zip(rv, rk)] for rv, rk in zip(piv.values, ntr.values)]
        fig.add_trace(go.Heatmap(z=piv.values, x=[f"TP {c:g}R" for c in piv.columns],
                                 y=[f"ATR×{r:g}" for r in piv.index], colorscale="RdYlGn", zmid=0,
                                 zmin=-zmax, zmax=zmax, text=text, texttemplate="%{text}",
                                 showscale=(i == 0), colorbar=dict(title="OOS avg R")),
                      row=i // cols + 1, col=i % cols + 1)
    fig.update_layout(title=f"{tf} — OOS avg R heatmap (TP × ATR mult) per RSI level set",
                      height=300 * rows + 80, margin=dict(l=40, r=20, t=70, b=30))
    return fig


def _fig_is_oos(tf: str, g: pd.DataFrame) -> go.Figure:
    labels = [f"TP {r.tp_r:g}R · ATR×{r.atr_mult:g} · RSI14 {int(r.ob)}/{int(r.os)} · RSI2 {int(r.f_hi)}/{int(r.f_lo)}"
              f"<br>n={int(r.n_trades)} · flags: {r.flags or '-'}" for r in g.itertuples()]
    fig = go.Figure(go.Scatter(x=g["is_avg_r"], y=g["oos_avg_r"], mode="markers", text=labels,
                               hovertemplate="%{text}<br>IS %{x:+.2f}R · OOS %{y:+.2f}R<extra></extra>",
                               marker=dict(size=8, color=g["n_trades"], colorscale="Viridis", showscale=True,
                                           colorbar=dict(title="n trades"))))
    lim = float(np.nanmax(np.abs(np.r_[g["is_avg_r"].to_numpy(), g["oos_avg_r"].to_numpy()]))) if len(g) else 1.0
    lim = max(lim, 0.1) * 1.1
    fig.add_shape(type="line", x0=-lim, y0=-lim, x1=lim, y1=lim, line=dict(dash="dot", color="#999"))
    fig.add_hline(y=0, line=dict(color="#bbb", width=1))
    fig.add_vline(x=0, line=dict(color="#bbb", width=1))
    fig.update_layout(title=f"{tf} — IS vs OOS avg R (each point = one combo)", height=420,
                      xaxis_title="IS avg R", yaxis_title="OOS avg R", margin=dict(l=40, r=20, t=50, b=30))
    return fig


def _fmt_table(df: pd.DataFrame, cols: list[str]) -> str:
    d = df[cols].copy()
    for c in cols:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: f"{v:.3f}" if pd.notna(v) else "")
    return d.to_html(index=False, escape=True, border=0)


def write_html(path: Path, grid_df: pd.DataFrame, rec: dict, rec_results: dict[str, BacktestResult],
               run_info: dict, offline: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    include = True if offline else "cdn"
    state = {"first": True}

    def fig_html(fig: go.Figure) -> str:
        js = include if state["first"] else False
        state["first"] = False
        return fig.to_html(full_html=False, include_plotlyjs=js)

    e = _html.escape
    parts = [f"<h1>RSI2 Swing Pullback — Backtest & Optimisation — {e(str(run_info.get('symbol', '')))}</h1>",
             f"<p class='muted'>Generated {e(str(run_info.get('generated_at', '')))} · code {e(str(run_info.get('git_hash', '')))}</p>",
             _fmt_table(_info_table(run_info), ["key", "value"])]

    parts.append("<h2>Recommendation</h2>")
    for tf, r in rec.items():
        if r is None:
            parts.append(f"<div class='rec none'><b>{e(tf)}</b>: no reliable parameter set. "
                         "No combo passed: IS n ≥ 30, IS avg R > 0, OOS avg R > 0, oversized ≤ 10%.</div>")
        else:
            p = r["params"]
            parts.append(f"<div class='rec'><b>{e(tf)}</b>: TP <b>{p['tp_r']:g}R</b>, ATR mult <b>{p['atr_mult']:g}</b>, "
                         f"RSI14 <b>{p['ob']:g}/{p['os']:g}</b>, RSI2 <b>{p['f_hi']:g}/{p['f_lo']:g}</b>"
                         f"<br><span class='muted'>{e(r['reason'])}</span></div>")

    for tf, res in rec_results.items():
        parts.append(f"<h2>{e(tf)} — recommended parameters</h2>")
        parts.append(fig_html(_fig_equity(tf, res)))
        parts.append(fig_html(_fig_r_hist(tf, res)))

    for tf, g in grid_df.groupby("tf", sort=False):
        parts.append(f"<h2>{e(tf)} — parameter grid</h2>")
        parts.append(fig_html(_fig_heatmaps(tf, g)))
        parts.append(fig_html(_fig_is_oos(tf, g)))
        top = g.sort_values(["oos_avg_r", "is_avg_r"], ascending=False).head(10)
        parts.append("<h3>Top 10 by OOS avg R</h3>")
        parts.append(_fmt_table(top, [c for c in GRID_FIRST_COLS if c in top.columns]))

    parts.append("<h2>Warnings</h2>")
    flagged = grid_df[grid_df["flags"].astype(str) != ""]
    if flagged.empty:
        parts.append("<p>none</p>")
    else:
        parts.append(f"<p class='warn'>{len(flagged)} of {len(grid_df)} combos carry flags "
                     "(n&lt;30, oos_sign_flip, buy_sell_imbalance, oversized). See the Grid sheet / grid.csv.</p>")
        counts = flagged["flags"].str.split(";").explode().value_counts()
        parts.append(_fmt_table(counts.rename_axis("flag").reset_index(name="combos"), ["flag", "combos"]))

    html = ("<!doctype html><html><head><meta charset='utf-8'><title>RSI2 Swing report</title>"
            f"<style>{_CSS}</style></head><body>{''.join(parts)}</body></html>")
    path.write_text(html, encoding="utf-8")
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_export.py -q`
Expected: `4 passed`. If openpyxl complains about tz-aware datetimes, a time column slipped past `_strip_tz` — check `split_time` and the Trades sheet.

- [ ] **Step 6: Commit**

```bash
git add rsi_fvg/backtest/export.py tests/test_export.py requirements.txt
git commit -m "feat: xlsx workbook and plotly html report for optimisation runs"
```

---

### Task 15: CLI, real data run, README

**Files:**
- Create: `scripts/run_rsi2_swing.py`
- Modify: `README.md`

**Interfaces:**
- Consumes everything above plus `load_config`, `load_or_fetch`, `Bars.from_dataframe`.
- Produces: `results/rsi2_swing/<YYYYMMDD_HHMMSS>/{grid.csv, trades_<TF>.csv, report_<symbol>.xlsx, report_<symbol>.html}` and a console summary.

- [ ] **Step 1: Write scripts/run_rsi2_swing.py**

```python
"""Grid-optimise the RSI2 swing strategy on cached MT5 data and export xlsx + html.

Usage:
  python scripts/run_rsi2_swing.py                                   # full grid, M5 M15 H1, risk 5%
  python scripts/run_rsi2_swing.py --tf M15 --tp 2 3 --atr-mult 1 1.5 --rsi14 75/25 --rsi2 90/10
  python scripts/run_rsi2_swing.py --concurrency single --offline    # Pine-comparable, self-contained html
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from rsi_fvg.backtest.export import write_csvs, write_html, write_xlsx  # noqa: E402
from rsi_fvg.backtest.optimize import (KEY_COLS, GridSpec, make_params, recommend,  # noqa: E402
                                       run_optimization, run_single)
from rsi_fvg.bars import Bars  # noqa: E402
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.params import load_config  # noqa: E402
from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams  # noqa: E402


def _pairs(values: list[str]) -> tuple[tuple[float, float], ...]:
    out = []
    for v in values:
        a, b = v.split("/")
        out.append((float(a), float(b)))
    return tuple(out)


def _git_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    ap.add_argument("--symbol")
    ap.add_argument("--tf", nargs="*")
    ap.add_argument("--risk", type=float, default=5.0)
    ap.add_argument("--concurrency", choices=["hedge", "single"], default="hedge")
    ap.add_argument("--tp", nargs="*", type=float, default=[1, 1.5, 2, 3, 4])
    ap.add_argument("--atr-mult", nargs="*", type=float, default=[0, 0.5, 1, 1.5, 2])
    ap.add_argument("--rsi14", nargs="*", default=["70/30", "75/25", "80/20"])
    ap.add_argument("--rsi2", nargs="*", default=["85/15", "90/10", "95/5"])
    ap.add_argument("--max-wait", type=int, default=0)
    ap.add_argument("--is-frac", type=float, default=0.7)
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--out", default=str(ROOT / "results" / "rsi2_swing"))
    ap.add_argument("--offline", action="store_true", help="embed plotly.js in the html (bigger file, works without internet)")
    a = ap.parse_args()

    cfg = load_config(a.config)
    symbol = a.symbol or cfg.symbol
    tfs = a.tf or cfg.timeframes
    sizing = replace(cfg.sizing, risk_pct=a.risk)
    grid = GridSpec(tp_r=tuple(float(x) for x in a.tp), atr_mult=tuple(float(x) for x in a.atr_mult),
                    rsi_slow_levels=_pairs(a.rsi14), rsi_fast_levels=_pairs(a.rsi2))
    base = Rsi2SwingParams(max_wait=a.max_wait)

    bars_by_tf, spec_by_tf, ranges = {}, {}, {}
    for tf in tfs:
        df, spec = load_or_fetch(symbol, tf, Path(a.data_dir), fallback_spec=cfg.spec_fallback)
        bars = Bars.from_dataframe(df)
        bars_by_tf[tf], spec_by_tf[tf] = bars, spec
        dt = bars.datetimes()
        ranges[tf] = (f"{dt[0]:%Y-%m-%d}", f"{dt[-1]:%Y-%m-%d}")
        print(f"{tf}: {len(bars):,d} bars {ranges[tf][0]} -> {ranges[tf][1]}  point={spec.point} contract={spec.contract_size}")

    t0 = time.time()
    last = {"pct": -1}

    def progress(done: int, total: int) -> None:
        pct = done * 100 // total
        if pct // 5 != last["pct"] // 5:
            last["pct"] = pct
            print(f"  {done}/{total} ({pct}%)  {time.time() - t0:.0f}s", flush=True)

    print(f"grid: {grid.size()} combos x {len(tfs)} TF")
    grid_df = run_optimization(bars_by_tf, spec_by_tf, base, grid, cfg.costs, sizing, a.concurrency,
                               is_frac=a.is_frac, progress=progress)
    rec = recommend(grid_df)

    rec_results = {}
    for tf, r in rec.items():
        if r is None:
            continue
        p = r["params"]
        params = make_params(base, p["ob"], p["os"], p["f_hi"], p["f_lo"], p["atr_mult"])
        _, res = run_single(bars_by_tf[tf], spec_by_tf[tf], params, p["tp_r"], cfg.costs, sizing, a.concurrency)
        rec_results[tf] = res

    run_info = {"symbol": symbol, "timeframes": tfs, "data_range": ranges, "initial_equity": sizing.initial_equity,
                "risk_pct": sizing.risk_pct, "concurrency": a.concurrency, "spread_points": cfg.costs.spread_points,
                "commission_per_lot_rt": cfg.costs.commission_per_lot_rt, "slippage_points": cfg.costs.slippage_points,
                "is_frac": a.is_frac, "max_wait": a.max_wait,
                "grid": {"tp_r": list(grid.tp_r), "atr_mult": list(grid.atr_mult), "rsi14": a.rsi14, "rsi2": a.rsi2},
                "git_hash": _git_hash(), "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}

    out_dir = Path(a.out) / datetime.now().strftime("%Y%m%d_%H%M%S")
    write_csvs(out_dir, grid_df, rec_results)
    write_xlsx(out_dir / f"report_{symbol}.xlsx", grid_df, rec, rec_results, run_info)
    write_html(out_dir / f"report_{symbol}.html", grid_df, rec, rec_results, run_info, offline=a.offline)

    pd.set_option("display.width", 220)
    print("\n=== Recommendation ===")
    for tf, r in rec.items():
        if r is None:
            print(f"{tf}: no reliable parameter set")
        else:
            p = r["params"]
            print(f"{tf}: TP {p['tp_r']:g}R  ATRx{p['atr_mult']:g}  RSI14 {p['ob']:g}/{p['os']:g}  RSI2 {p['f_hi']:g}/{p['f_lo']:g}")
            print(f"     {r['reason']}")
    cols = KEY_COLS + ["n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct", "is_avg_r", "oos_avg_r", "robust_r", "flags"]
    for tf, g in grid_df.groupby("tf", sort=False):
        print(f"\n--- {tf}: top 5 by OOS avg R ---")
        print(g.sort_values(["oos_avg_r", "is_avg_r"], ascending=False)[cols].head(5).to_string(index=False))
    print(f"\nwritten: {out_dir}  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-run the CLI on a tiny grid**

Run: `python scripts/run_rsi2_swing.py --tf M15 --tp 2 --atr-mult 1 --rsi14 75/25 --rsi2 90/10`
Expected: data line for M15 (from `data/XAUUSDc_M15.parquet`; if missing, run `python scripts/fetch_data.py` first — MT5 terminal must be open), `grid: 1 combos x 1 TF`, a recommendation (or "no reliable parameter set" — a 1-combo grid may not pass the n≥30 filter on OOS), and a `results/rsi2_swing/<ts>/` folder with `grid.csv`, `report_XAUUSDc.xlsx`, `report_XAUUSDc.html`. Open the html in a browser once to confirm it renders (plotly via CDN).

- [ ] **Step 3: Full run**

Run: `python scripts/run_rsi2_swing.py`
Expected: 225 combos × 3 TF; progress lines; finished in well under 15 minutes on this machine (M5 is the heavy TF). Report to the user, verbatim from the console: the data ranges per TF, the `=== Recommendation ===` block, and the three top-5 tables. **Do not editorialise on whether the strategy is good** — numbers, flags, and the recommendation reason only. Include the output folder path.

Also run: `python scripts/run_rsi2_swing.py --concurrency single` and list its folder — the Pine-comparable variant.

- [ ] **Step 4: Update README.md**

Append this section (keep the existing content):

```markdown
## RSI2 Swing Pullback — optimisation & report

Strategy: `rsi_fvg/strategies/rsi2_swing.py` (port of `pine/rsi2_swing_strategy.pine`).

    python scripts/run_rsi2_swing.py                     # 225 combos x M5/M15/H1, risk 5%, hedge
    python scripts/run_rsi2_swing.py --concurrency single
    python scripts/run_rsi2_swing.py --tf M15 --tp 2 3 --atr-mult 1 1.5 --rsi14 75/25 --rsi2 90/10
    python scripts/run_rsi2_swing.py --offline           # html with plotly.js embedded

Output `results/rsi2_swing/<timestamp>/`:
- `report_<symbol>.xlsx` — Summary (recommendation + run config), Grid (all combos, IS/OOS, robustness, flags),
  Trades_<TF>, Monthly_<TF>, Equity_<TF> for recommended combos, Params.
- `report_<symbol>.html` — equity/drawdown, R distribution, OOS heatmaps (TP x ATR per RSI set), IS-vs-OOS scatter, top-10, warnings.
- `grid.csv`, `trades_<TF>.csv`.

How the recommendation is chosen (spec §4): IS = first 70% of bars, OOS = last 30%. A combo qualifies when
IS n >= 30, IS avg R > 0, OOS avg R > 0 and <= 10% of its trades hit the min-lot floor. Score =
0.5·z(OOS avg R) + 0.3·z(robustness) + 0.2·z(IS avg R); robustness = median IS avg R of the grid neighbours
(±1 step in TP and ATR mult). Sharp peaks lose to plateaus on purpose. No qualifier → "no reliable parameter set".
```

- [ ] **Step 5: Full test suite**

Run: `python -m pytest -q`
Expected: all passed (MT5 integration tests pass or skip).

- [ ] **Step 6: Commit**

```bash
git add scripts/run_rsi2_swing.py README.md
git commit -m "feat: rsi2 swing optimisation CLI with xlsx/html export; README"
```

---

## Plan self-review (done at authoring time)

- **Spec coverage:** §2.1–2.4 → Task 11 (cross helpers, swing_structure, state machine, params, `swing_price`, `variant="SWING"`); §2.5 → inherited engine (Phase 1 Task 6) with `risk_pct=5`, `tp_r=2` defaults in the CLI; §3 → Task 12; §4.1–4.3 → Task 13 (grid, one strategy pass per RSI/ATR combo, IS/OOS 70/30, robustness, flags, weighted z-score recommendation, `None` when nothing qualifies); §5.1 → Task 14 `write_xlsx` (Summary, Grid with colour scale/freeze/autofilter, Trades/Monthly/Equity per TF, Params); §5.2 → `write_html` sections 1–7 with `cdn`/`--offline`; §5.3 → `write_csvs`; §6 → Task 15 CLI flags; §7 → Task 10 layout (`signals.py`, `strategies/`, shim); §8 → tests in Tasks 11–14. Pine spot-check (§8 last bullet) is manual and listed in README's known limits from Phase 1.
- **Type consistency:** `Signal.variant: str` everywhere (Task 10 engine change, Task 11 `VARIANT`, Phase 1 test_engine helper updated). `Rsi2SwingParams` field names (`overbought, oversold, fast_hi, fast_lo, atr_mult, max_wait`) match `make_params` and CLI. `KEY_COLS` order matches the Grid header assertion in `test_export`. `compute_metrics(..., n_bars=)` signature used identically in Task 12 tests and Task 13. `run_single` returns `(signals, BacktestResult)` in Task 13 and is consumed that way in Tasks 14–15.
- **Placeholders:** none.
- **Deferred:** Phase 1 Task 9 (RSI-FVG runner/report) — recorded in the header; not needed for this deliverable.
