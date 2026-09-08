# RSI2 Swing + EMA Trend — Strategy & Generic Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `rsi2_ema_swing` strategy (enter on every confirmed RSI(2) swing that agrees with an EMA 20/100 trend) as a Python plugin plus a Pine script, and generalise the optimizer/export/CLI behind a strategy adapter so both strategies share one grid engine.

**Architecture:** A `StrategyAdapter` (in `rsi_fvg/strategies/registry.py`) declares a strategy's grid axes, the grid columns each axis expands to, how to build its params object, and how to run it. `GridSpec` becomes `{axis name: values}` + `tp_r`. `optimize.run_optimization` iterates the adapter's axes generically; robustness, flags, recommendation, export and the CLIs read column names from the adapter instead of module constants. The existing `rsi2_swing` results are pinned by a golden CSV written from the current code **before** the refactor.

**Tech Stack:** Python 3.13, numpy, pandas, openpyxl, plotly, pytest. Pine Script v6.

**Spec:** `docs/superpowers/specs/2026-09-08-rsi2-ema-swing-strategy-design.md` (inherits `2026-09-08-rsi2-swing-backtest-optimizer-design.md` and `2026-09-08-rsi-fvg-pullback-strategy-design.md`).

## Global Constraints

- Repo `C:\Users\MeoMeo\Desktop\AI BOT TRADING NEW FLOW`, branch `feat/python-backtest`. Python 3.13 (`python`). Tests: `python -m pytest -q` from the repo root — **143 tests pass at HEAD `25208d0`**; the suite must stay green after every task. Commit with `git -c user.name="MeoMeo" -c user.email="kienpham@cungbai.vn" commit -m "..."`. Stage files explicitly, never `git add -A` (`data/`, `results/`, `.superpowers/` are ignored but untracked scratch may exist).
- **The `rsi2_swing` grid must keep producing identical numbers.** Task 1 writes `tests/data/golden_rsi2_swing_grid.csv` from the current code; every later task keeps `tests/test_golden_grid.py` green. If a refactor changes a single golden value, the refactor is wrong — do not regenerate the fixture.
- `scripts/run_rsi2_swing.py` keeps every existing flag and its output layout (`results/rsi2_swing/<timestamp>/`), so the runs already delivered stay reproducible.
- Strategy modules never look at positions; signals are emitted at bar close `t` and filled at `open[t+1]` by the engine; all engine rules (spread/slippage, SL-before-TP, ruin floor, `oversized`/`capped`, `rejected_min_sl`, hedge/single) are inherited unchanged.
- No look-ahead: a signal at bar `t` may only use data at indices `<= t`. Every new strategy gets a prefix-invariance test.
- `Signal.variant` for the new strategy is the literal `"EMASWING"`; `rsi2_swing` keeps `"SWING"`.
- New strategy defaults (spec §2.3): `rsi_fast=2, fast_hi=90.0, fast_lo=10.0, ema_fast=20, ema_slow=100, atr_len=14, atr_mult=1.5, htf_seconds=0, htf_rsi_len=14, htf_level=50.0`; run defaults `tp_r=8.0`, `risk_pct=1.0`, `concurrency=hedge`.
- New strategy default grid (spec §3.1): `rsi_fast ∈ (2,3,5)`, `rsi2 ∈ ((90,10),(95,5))`, `ema ∈ ((20,100),(20,200),(50,200),(10,50))`, `atr_mult ∈ (1.0,1.5,2.0,3.0)`, `tp_r ∈ (2.0,4.0,6.0,8.0)` → **384 combos per timeframe**.
- `rsi2_swing` axis names and column order stay exactly `tf, rsi_fast, ob, os, f_hi, f_lo, atr_mult, tp_r`.
- EMA definition: `alpha = 2/(period+1)`, recursion seeded with `close[0]`, and `out[:period-1] = NaN` so the strategy skips the warm-up. Pine's `ta.ema` has no NaN prefix — that is the only intended divergence and it is documented.

---

## File Structure

| Path | Responsibility | Task |
|---|---|---|
| `tests/data/golden_rsi2_swing_grid.csv` | frozen grid output of the current optimizer | 1 |
| `tests/test_golden_grid.py` | regression guard that pins it | 1 |
| `rsi_fvg/strategies/registry.py` | `Axis`, `StrategyAdapter`, `STRATEGIES`, `get_adapter` | 2 |
| `rsi_fvg/backtest/optimize.py` | generic `GridSpec`, `run_optimization`, robustness, flags, recommend | 3 |
| `rsi_fvg/backtest/export.py` | generic grid header, heatmap panels, scatter labels, recommendation table | 4 |
| `scripts/run_rsi2_swing.py` | unchanged behaviour on top of the generic core | 4 |
| `rsi_fvg/indicators.py` | `+ ema(close, period)` | 5 |
| `rsi_fvg/strategies/rsi2_ema_swing.py` | the new strategy | 5 |
| `pine/rsi2_ema_swing_strategy.pine` | Pine version | 6 |
| `scripts/optimize.py` | generic CLI (`--strategy`, `--axis`) | 7 |
| `README.md`, spec | usage + the EMA warm-up divergence | 7 |
| `tests/test_registry.py`, `tests/test_rsi2_ema_swing.py`, `tests/test_optimize.py`, `tests/test_export.py`, `tests/test_cli.py`, `tests/test_indicators.py` | tests | 2–7 |

---

### Task 1: Golden fixture pinning the current `rsi2_swing` grid

**Files:**
- Create: `tests/data/golden_rsi2_swing_grid.csv`, `tests/test_golden_grid.py`

**Interfaces:**
- Consumes: today's `optimize.GridSpec`, `optimize.run_optimization` (current signature `run_optimization(bars_by_tf, spec_by_tf, base, grid, costs, sizing, concurrency="hedge", is_frac=0.7, progress=None, min_sl_spread_mult=0.0)`), `Rsi2SwingParams`.
- Produces: `tests/test_golden_grid.py::GOLDEN_COLS` (the compared column list), `golden_bars()`, `golden_inputs()` — later tasks reuse these helpers and must not change the CSV.

- [ ] **Step 1: Write the test that reads the fixture**

`tests/test_golden_grid.py`:
```python
"""Pins the rsi2_swing grid output so the generic-adapter refactor cannot change it.

The CSV was generated from the pre-refactor optimizer (see the plan, Task 1 Step 2).
If a later change makes this fail, the change is wrong — do not regenerate the file.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rsi_fvg.bars import Bars
from rsi_fvg.params import CostParams, SizingParams, SymbolSpec
from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams

GOLDEN = Path(__file__).parent / "data" / "golden_rsi2_swing_grid.csv"
GOLDEN_COLS = ["tf", "rsi_fast", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r",
               "n_signals", "n_trades", "win_rate", "avg_r", "profit_factor", "net_pnl",
               "max_dd_pct", "is_n_trades", "is_avg_r", "oos_n_trades", "oos_avg_r",
               "robust_r", "robust_ratio", "ruined", "grid_edge", "flags"]
SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0)
COSTS = CostParams(spread_points=20, commission_per_lot_rt=0.0, slippage_points=0)
SIZING = SizingParams(risk_pct=1.0, initial_equity=10_000.0)


def golden_bars(n=8000, seed=17):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    return Bars(time=1_700_000_000 + np.arange(n, dtype=np.int64) * 300,
                open=open_, high=high, low=low, close=close)


def golden_inputs():
    """(bars_by_tf, spec_by_tf, base, axis values) for the pinned run."""
    bars = golden_bars()
    return ({"M5": bars}, {"M5": SPEC}, Rsi2SwingParams(),
            dict(tp_r=(1.0, 2.0, 4.0), atr_mult=(0.5, 1.5), rsi_fast=(2, 5),
                 rsi_slow_levels=((75.0, 25.0),), rsi_fast_levels=((90.0, 10.0),)))


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    out = df[GOLDEN_COLS].copy()
    out["flags"] = out["flags"].fillna("")
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].round(9)
    return out.sort_values(GOLDEN_COLS[:8]).reset_index(drop=True)


def build_grid_df() -> pd.DataFrame:
    """Run the optimizer the way the fixture was produced."""
    from rsi_fvg.backtest.optimize import GridSpec, run_optimization
    bars_by_tf, spec_by_tf, base, ax = golden_inputs()
    grid = GridSpec(tp_r=ax["tp_r"], atr_mult=ax["atr_mult"], rsi_fast=ax["rsi_fast"],
                    rsi_slow_levels=ax["rsi_slow_levels"], rsi_fast_levels=ax["rsi_fast_levels"])
    return run_optimization(bars_by_tf, spec_by_tf, base, grid, COSTS, SIZING, "hedge")


def test_golden_fixture_exists():
    assert GOLDEN.exists(), "generate the fixture first (plan Task 1 Step 2)"


def test_rsi2_swing_grid_matches_golden():
    got = normalise(build_grid_df())
    want = normalise(pd.read_csv(GOLDEN))
    assert len(got) == 12, "3 tp x 2 atr x 2 rsi_fast x 1 x 1"
    pd.testing.assert_frame_equal(got, want, check_dtype=False, rtol=0, atol=1e-9)
```

- [ ] **Step 2: Generate the fixture from the current code**

Run this exact snippet (it imports the test module so the fixture and the test agree by construction):

```bash
mkdir -p tests/data
python -c "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'tests'); import test_golden_grid as g; df=g.build_grid_df(); g.normalise(df).to_csv(g.GOLDEN, index=False); print(len(df), 'rows ->', g.GOLDEN)"
```
Expected: `12 rows -> ...tests\data\golden_rsi2_swing_grid.csv`.

- [ ] **Step 3: Run the test to verify it passes against the freshly written fixture**

Run: `python -m pytest tests/test_golden_grid.py -q`
Expected: `2 passed`. (It passes immediately — this task's deliverable is the pin, not a red-to-green cycle. If it fails, the run is not deterministic and that must be reported, not worked around.)

- [ ] **Step 4: Prove the pin actually bites**

Temporarily edit `rsi_fvg/backtest/optimize.py` line `W_IS_AVG_R = 0.6` to `0.61`, run `python -m pytest tests/test_golden_grid.py -q`, and confirm it still passes (that constant only affects `recommend`, not the grid) — then temporarily change `MIN_TRADES = 30` to `31`, run again, and confirm **it fails** on the `flags` column. Revert both edits and re-run to green. Record both outcomes in your report; this is the evidence that the fixture guards real behaviour.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: `145 passed` (143 + 2 new).

- [ ] **Step 6: Commit**

```bash
git add tests/data/golden_rsi2_swing_grid.csv tests/test_golden_grid.py
git commit -m "test: pin rsi2_swing grid output with a golden fixture"
```

---

### Task 2: Strategy adapter and registry

**Files:**
- Create: `rsi_fvg/strategies/registry.py`, `tests/test_registry.py`

**Interfaces:**
- Consumes: `Rsi2SwingParams`, `rsi2_swing.run_strategy`, `Bars`, `Signal`.
- Produces:
  - `Axis(name: str, columns: tuple[str, ...], params: tuple[str, ...], int_cols: tuple[str, ...] = ())` frozen dataclass; `Axis.expand(value) -> dict[str, float | int]` maps one axis value (scalar or tuple) to `{column: value}`; `Axis.param_kwargs(value) -> dict[str, float | int]` maps it to params-field kwargs.
  - `StrategyAdapter(name, axes: tuple[Axis, ...], default_axes: dict[str, tuple], default_tp_r: tuple[float, ...], params_cls, run, robust_axis: str = "atr_mult", panel_title: Callable[[dict], str] | None = None)` frozen dataclass with:
    - `key_cols -> tuple[str, ...]` — every axis column in axis order (no `tf`, no `tp_r`).
    - `full_key_cols() -> list[str]` — `["tf", *key_cols, "tp_r"]`.
    - `int_cols -> tuple[str, ...]` — union of axis `int_cols`.
    - `robust_cols -> list[str]` — `["tf", *(c for c in key_cols if c not in axis(robust_axis).columns)]`.
    - `panel_cols -> list[str]` — `[c for c in key_cols if c not in axis(robust_axis).columns]`.
    - `axis(name) -> Axis`, `make_params(base, axis_values: dict[str, object])`, `columns_for(axis_values) -> dict[str, float | int]`, `title(row: dict) -> str`.
  - `STRATEGIES: dict[str, StrategyAdapter]` with key `"rsi2_swing"`; `get_adapter(name) -> StrategyAdapter` (raises `KeyError` listing valid names).

- [ ] **Step 1: Write the failing tests**

`tests/test_registry.py`:
```python
import pytest

from rsi_fvg.strategies.registry import STRATEGIES, Axis, get_adapter
from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams


def test_axis_expand_scalar_and_pair():
    a = Axis("rsi_fast", ("rsi_fast",), ("rsi_fast",), int_cols=("rsi_fast",))
    assert a.expand(5) == {"rsi_fast": 5}
    assert a.param_kwargs(5) == {"rsi_fast": 5}
    p = Axis("rsi14", ("ob", "os"), ("overbought", "oversold"))
    assert p.expand((80, 20)) == {"ob": 80.0, "os": 20.0}
    assert p.param_kwargs((80, 20)) == {"overbought": 80.0, "oversold": 20.0}


def test_axis_arity_mismatch_raises():
    p = Axis("rsi14", ("ob", "os"), ("overbought", "oversold"))
    with pytest.raises(ValueError):
        p.expand(80)


def test_rsi2_swing_adapter_shape():
    a = get_adapter("rsi2_swing")
    assert a.name == "rsi2_swing"
    assert a.key_cols == ("rsi_fast", "ob", "os", "f_hi", "f_lo", "atr_mult")
    assert a.full_key_cols() == ["tf", "rsi_fast", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r"]
    assert a.int_cols == ("rsi_fast",)
    assert a.robust_cols == ["tf", "rsi_fast", "ob", "os", "f_hi", "f_lo"]
    assert a.panel_cols == ["rsi_fast", "ob", "os", "f_hi", "f_lo"]
    assert a.default_tp_r == (1.0, 1.5, 2.0, 3.0, 4.0)
    assert a.default_axes["atr_mult"] == (0.0, 0.5, 1.0, 1.5, 2.0)
    assert a.default_axes["rsi14"] == ((70.0, 30.0), (75.0, 25.0), (80.0, 20.0))
    assert a.default_axes["rsi2"] == ((85.0, 15.0), (90.0, 10.0), (95.0, 5.0))
    assert a.default_axes["rsi_fast"] == (2,)


def test_rsi2_swing_adapter_params_and_columns():
    a = get_adapter("rsi2_swing")
    vals = {"rsi_fast": 5, "rsi14": (80.0, 20.0), "rsi2": (95.0, 5.0), "atr_mult": 1.5}
    assert a.columns_for(vals) == {"rsi_fast": 5, "ob": 80.0, "os": 20.0,
                                   "f_hi": 95.0, "f_lo": 5.0, "atr_mult": 1.5}
    p = a.make_params(Rsi2SwingParams(), vals)
    assert (p.rsi_fast, p.overbought, p.oversold, p.fast_hi, p.fast_lo, p.atr_mult) == (5, 80.0, 20.0, 95.0, 5.0, 1.5)
    assert p.rsi_slow == 14 and p.htf_seconds == 0      # untouched fields survive


def test_adapter_title_is_readable():
    a = get_adapter("rsi2_swing")
    row = {"rsi_fast": 5, "ob": 80.0, "os": 20.0, "f_hi": 90.0, "f_lo": 10.0, "atr_mult": 1.5}
    assert a.title(row) == "RSI(5) 90/10 · RSI14 80/20"


def test_get_adapter_unknown_lists_names():
    with pytest.raises(KeyError) as e:
        get_adapter("nope")
    assert "rsi2_swing" in str(e.value)


def test_registry_run_is_the_strategy_entry_point():
    from rsi_fvg.strategies import rsi2_swing
    assert STRATEGIES["rsi2_swing"].run is rsi2_swing.run_strategy
    assert STRATEGIES["rsi2_swing"].params_cls is Rsi2SwingParams
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_registry.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.strategies.registry'`.

- [ ] **Step 3: Write `rsi_fvg/strategies/registry.py`**

```python
"""Strategy adapters: what the optimizer needs to know about a strategy (spec §3.1).

An adapter is the only place that knows a strategy's grid axes, the grid columns each axis
expands to, and how axis values become a params object. `optimize`, `export` and the CLIs read
column names from here, so adding a strategy is one module plus one registry entry.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Sequence

from ..bars import Bars
from ..signals import Signal
from .rsi2_swing import Rsi2SwingParams
from .rsi2_swing import run_strategy as run_rsi2_swing


@dataclass(frozen=True)
class Axis:
    """One grid axis. A value is a scalar for a single column, or a tuple for several.

    `columns` are the grid/report column names; `params` the params-object field names, in the
    same order. `int_cols` lists the columns that are lengths rather than levels.
    """

    name: str
    columns: tuple[str, ...]
    params: tuple[str, ...]
    int_cols: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len(self.columns) != len(self.params):
            raise ValueError(f"axis {self.name}: {len(self.columns)} columns vs {len(self.params)} params")

    def _parts(self, value) -> tuple:
        parts = tuple(value) if isinstance(value, (tuple, list)) else (value,)
        if len(parts) != len(self.columns):
            raise ValueError(f"axis {self.name} expects {len(self.columns)} value(s), got {value!r}")
        return parts

    def _cast(self, column: str, v):
        return int(v) if column in self.int_cols else float(v)

    def expand(self, value) -> dict:
        return {c: self._cast(c, v) for c, v in zip(self.columns, self._parts(value))}

    def param_kwargs(self, value) -> dict:
        return {p: self._cast(c, v) for c, p, v in zip(self.columns, self.params, self._parts(value))}


@dataclass(frozen=True)
class StrategyAdapter:
    name: str
    axes: tuple[Axis, ...]
    default_axes: dict[str, tuple]
    default_tp_r: tuple[float, ...]
    params_cls: type
    run: Callable[..., list[Signal]]
    robust_axis: str = "atr_mult"
    panel_title: Callable[[dict], str] | None = None

    def axis(self, name: str) -> Axis:
        for a in self.axes:
            if a.name == name:
                return a
        raise KeyError(f"{self.name}: no axis {name!r}; have {[a.name for a in self.axes]}")

    @property
    def key_cols(self) -> tuple[str, ...]:
        return tuple(c for a in self.axes for c in a.columns)

    def full_key_cols(self) -> list[str]:
        return ["tf", *self.key_cols, "tp_r"]

    @property
    def int_cols(self) -> tuple[str, ...]:
        return tuple(c for a in self.axes for c in a.int_cols)

    @property
    def _robust_axis_cols(self) -> tuple[str, ...]:
        return self.axis(self.robust_axis).columns

    @property
    def robust_cols(self) -> list[str]:
        return ["tf", *(c for c in self.key_cols if c not in self._robust_axis_cols)]

    @property
    def panel_cols(self) -> list[str]:
        return [c for c in self.key_cols if c not in self._robust_axis_cols]

    def columns_for(self, axis_values: dict) -> dict:
        out: dict = {}
        for a in self.axes:
            out.update(a.expand(axis_values[a.name]))
        return out

    def make_params(self, base, axis_values: dict):
        kwargs: dict = {}
        for a in self.axes:
            kwargs.update(a.param_kwargs(axis_values[a.name]))
        return replace(base, **kwargs)

    def title(self, row: dict) -> str:
        if self.panel_title is not None:
            return self.panel_title(row)
        parts = []
        for c in self.panel_cols:
            v = row[c]
            parts.append(f"{c}={int(v)}" if c in self.int_cols else f"{c}={float(v):g}")
        return " · ".join(parts)


def _rsi2_swing_title(row: dict) -> str:
    return (f"RSI({int(row['rsi_fast'])}) {int(row['f_hi'])}/{int(row['f_lo'])}"
            f" · RSI14 {int(row['ob'])}/{int(row['os'])}")


RSI2_SWING = StrategyAdapter(
    name="rsi2_swing",
    axes=(Axis("rsi_fast", ("rsi_fast",), ("rsi_fast",), int_cols=("rsi_fast",)),
          Axis("rsi14", ("ob", "os"), ("overbought", "oversold")),
          Axis("rsi2", ("f_hi", "f_lo"), ("fast_hi", "fast_lo")),
          Axis("atr_mult", ("atr_mult",), ("atr_mult",))),
    default_axes={"rsi_fast": (2,),
                  "rsi14": ((70.0, 30.0), (75.0, 25.0), (80.0, 20.0)),
                  "rsi2": ((85.0, 15.0), (90.0, 10.0), (95.0, 5.0)),
                  "atr_mult": (0.0, 0.5, 1.0, 1.5, 2.0)},
    default_tp_r=(1.0, 1.5, 2.0, 3.0, 4.0),
    params_cls=Rsi2SwingParams,
    run=run_rsi2_swing,
    panel_title=_rsi2_swing_title,
)

STRATEGIES: dict[str, StrategyAdapter] = {RSI2_SWING.name: RSI2_SWING}


def get_adapter(name: str) -> StrategyAdapter:
    try:
        return STRATEGIES[name]
    except KeyError as e:
        raise KeyError(f"unknown strategy {name!r}; have {sorted(STRATEGIES)}") from e
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_registry.py -q`
Expected: `7 passed`.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: `152 passed`.

- [ ] **Step 6: Commit**

```bash
git add rsi_fvg/strategies/registry.py tests/test_registry.py
git commit -m "feat: strategy adapter and registry for the optimizer"
```

---

### Task 3: Generic optimizer

**Files:**
- Modify: `rsi_fvg/backtest/optimize.py`, `tests/test_optimize.py`, `tests/test_golden_grid.py` (call sites only — the golden CSV must not change)
- Modify (call sites so the suite stays green): `scripts/run_rsi2_swing.py`, `rsi_fvg/backtest/export.py` (import of `KEY_COLS` only; the full export rework is Task 4)

**Interfaces:**
- Consumes: `StrategyAdapter`, `get_adapter` (Task 2).
- Produces:
  - `GridSpec(axes: dict[str, tuple], tp_r: tuple[float, ...])` with `GridSpec.for_strategy(adapter, axes: dict | None = None, tp_r: Sequence | None = None) -> GridSpec`, `size() -> int`, `combos(adapter) -> Iterator[dict[str, object]]` (axis-name → value, in adapter axis order).
  - `run_optimization(strategy, bars_by_tf, spec_by_tf, base, grid, costs, sizing, concurrency="hedge", is_frac=0.7, progress=None, min_sl_spread_mult=0.0) -> pd.DataFrame`
  - `run_single(strategy, bars, spec, params, tp_r, costs, sizing, concurrency, min_sl_spread_mult=0.0) -> tuple[list[Signal], BacktestResult]`
  - `add_robustness(df, grid, strategy) -> pd.DataFrame`; `recommend(df, strategy, min_trades=MIN_TRADES, min_oos_trades=MIN_OOS_TRADES) -> dict[str, dict | None]`
  - `KEY_COLS` stays as a module constant equal to `get_adapter("rsi2_swing").full_key_cols()` (kept so nothing that imports it breaks mid-refactor; Task 4 removes the last consumer).
  - `make_params(base, ob, os_, f_hi, f_lo, atr_mult, rsi_fast=None)` unchanged (rsi2_swing-specific helper still used by the old CLI).

- [ ] **Step 1: Add the arity guard the generic robustness code relies on**

In `rsi_fvg/strategies/registry.py`, add to `StrategyAdapter` a `__post_init__`:
```python
    def __post_init__(self) -> None:
        if len(self.axis(self.robust_axis).columns) != 1:
            raise ValueError(f"{self.name}: robust axis {self.robust_axis!r} must map to exactly one column")
```
And in `tests/test_registry.py` add:
```python
def test_robust_axis_must_be_single_column():
    from rsi_fvg.strategies.registry import Axis, StrategyAdapter
    from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams, run_strategy
    with pytest.raises(ValueError):
        StrategyAdapter(name="bad", axes=(Axis("pair", ("a", "b"), ("x", "y")),),
                        default_axes={"pair": ((1, 2),)}, default_tp_r=(1.0,),
                        params_cls=Rsi2SwingParams, run=run_strategy, robust_axis="pair")
```
Run: `python -m pytest tests/test_registry.py -q` → `8 passed`.

- [ ] **Step 2: Write the failing tests for the generic API**

Replace the top of `tests/test_optimize.py` (imports + fixtures) with:
```python
import numpy as np
import pandas as pd
import pytest

from rsi_fvg.backtest.optimize import (MIN_TRADES, SPLIT_KEYS, GridSpec, add_robustness,
                                       compute_flags, recommend, run_optimization, run_single,
                                       split_time)
from rsi_fvg.bars import Bars
from rsi_fvg.params import CostParams, SizingParams, SymbolSpec
from rsi_fvg.strategies.registry import get_adapter
from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams

ADAPTER = get_adapter("rsi2_swing")
KEY_COLS = ADAPTER.full_key_cols()
SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0)
COSTS = CostParams(spread_points=20, commission_per_lot_rt=0.0, slippage_points=0)
SIZING = SizingParams(risk_pct=5.0, initial_equity=10_000.0)
SMALL = GridSpec.for_strategy(ADAPTER, axes={"rsi_fast": (2,), "rsi14": ((75.0, 25.0),),
                                             "rsi2": ((90.0, 10.0),), "atr_mult": (0.5, 1.0)},
                              tp_r=(1.0, 2.0))
```
Then, throughout the file, apply these mechanical edits:
- `GridSpec(tp_r=..., atr_mult=..., rsi_slow_levels=..., rsi_fast_levels=..., rsi_fast=...)` → `GridSpec.for_strategy(ADAPTER, axes={"rsi_fast": ..., "rsi14": <rsi_slow_levels>, "rsi2": <rsi_fast_levels>, "atr_mult": ...}, tp_r=...)`.
- `run_optimization(` → `run_optimization(ADAPTER, ` (adapter first).
- `run_single(` → `run_single(ADAPTER, `.
- `add_robustness(df, grid)` → `add_robustness(df, grid, ADAPTER)`.
- `recommend(df)` → `recommend(df, ADAPTER)`; `recommend(df, min_trades=n)` → `recommend(df, ADAPTER, min_trades=n)`.
- `GridSpec().size() == 225` → `GridSpec.for_strategy(ADAPTER).size() == 225`; the `rsi_fast=(2,5)` size case → `GridSpec.for_strategy(ADAPTER, axes={"rsi_fast": (2, 5)}).size() == 450`.

Add these new tests at the end of `tests/test_optimize.py`:
```python
def test_gridspec_for_strategy_fills_defaults_and_rejects_unknown_axis():
    g = GridSpec.for_strategy(ADAPTER, axes={"atr_mult": (1.0,)})
    assert g.axes["rsi14"] == ADAPTER.default_axes["rsi14"]      # untouched axis keeps its default
    assert g.axes["atr_mult"] == (1.0,)
    assert g.tp_r == ADAPTER.default_tp_r
    with pytest.raises(KeyError):
        GridSpec.for_strategy(ADAPTER, axes={"ema": ((20, 100),)})


def test_combos_follow_adapter_axis_order():
    g = GridSpec.for_strategy(ADAPTER, axes={"rsi_fast": (2, 5), "rsi14": ((75.0, 25.0),),
                                             "rsi2": ((90.0, 10.0),), "atr_mult": (0.5, 1.0)},
                              tp_r=(1.0,))
    combos = list(g.combos(ADAPTER))
    assert len(combos) == 4
    assert list(combos[0]) == ["rsi_fast", "rsi14", "rsi2", "atr_mult"]
    assert [c["rsi_fast"] for c in combos] == [2, 2, 5, 5]       # first axis varies slowest


def test_grid_columns_come_from_the_adapter():
    df = run_optimization(ADAPTER, {"M5": _bars()}, {"M5": SPEC}, Rsi2SwingParams(), SMALL, COSTS, SIZING)
    for c in KEY_COLS:
        assert c in df.columns
    assert df["rsi_fast"].dtype.kind == "i"
    assert list(df.columns[:len(KEY_COLS) - 1]) == KEY_COLS[:-1] or set(KEY_COLS) <= set(df.columns)
```
(`_bars()` is the existing helper in that file; keep it.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_optimize.py -q`
Expected: failures/errors on `GridSpec.for_strategy` not existing and on `run_optimization` receiving an adapter.

- [ ] **Step 4: Rewrite the generic parts of `rsi_fvg/backtest/optimize.py`**

Replace the imports/constants block and the four functions below. Everything not mentioned (`SPLIT_KEYS`, gate constants, `_col`, `_segment_metrics`, `split_time`, `make_params`, `compute_flags`, `_zscore`, `FILTER_TEXT`, `_reason`) stays exactly as it is.

Imports: drop `from ..strategies.rsi2_swing import Rsi2SwingParams, run_strategy`, add
```python
import itertools
from typing import Callable, Iterator, Sequence

from ..strategies.registry import StrategyAdapter, get_adapter
from ..strategies.rsi2_swing import Rsi2SwingParams   # still used by make_params' annotation
```
Constants: replace the `KEY_COLS` / `ROBUST_KEYS` / `INT_KEY_COLS` lines with
```python
# Column names now come from the strategy adapter; this constant is the rsi2_swing view of them,
# kept because the delivered reports and CSVs use it.
KEY_COLS = get_adapter("rsi2_swing").full_key_cols()
```

`GridSpec`:
```python
@dataclass(frozen=True)
class GridSpec:
    """Grid as {axis name: values} plus the TP axis (spec §3.2).

    An axis value is a scalar (one column) or a tuple (several, e.g. `rsi2 = (90, 10)`).
    Signals are computed once per axis combination; the engine runs once per `tp_r`, because
    TP is the only axis that does not change the signal.
    """

    axes: dict[str, tuple]
    tp_r: tuple[float, ...]

    @classmethod
    def for_strategy(cls, adapter: StrategyAdapter, axes: dict | None = None,
                     tp_r: Sequence | None = None) -> "GridSpec":
        known = {a.name for a in adapter.axes}
        unknown = set(axes or {}) - known
        if unknown:
            raise KeyError(f"{adapter.name}: unknown axis {sorted(unknown)}; have {sorted(known)}")
        merged = {k: tuple(v) for k, v in adapter.default_axes.items()}
        merged.update({k: tuple(v) for k, v in (axes or {}).items()})
        return cls(axes=merged, tp_r=tuple(float(x) for x in (tp_r if tp_r is not None else adapter.default_tp_r)))

    def size(self) -> int:
        n = len(self.tp_r)
        for values in self.axes.values():
            n *= len(values)
        return n

    def combos(self, adapter: StrategyAdapter) -> Iterator[dict]:
        names = [a.name for a in adapter.axes]
        for values in itertools.product(*(self.axes[n] for n in names)):
            yield dict(zip(names, values))
```

`run_single`:
```python
def run_single(strategy: StrategyAdapter, bars: Bars, spec: SymbolSpec, params, tp_r: float,
               costs: CostParams, sizing: SizingParams, concurrency: str,
               min_sl_spread_mult: float = 0.0) -> tuple[list[Signal], BacktestResult]:
    signals = strategy.run(bars, params)
    return signals, run_backtest(bars, signals, float(tp_r), spec, costs, sizing, concurrency,
                                 min_sl_spread_mult=min_sl_spread_mult)
```

`run_optimization` — same body as today with three changes: the signature gains `strategy` first, the two innermost loops become the adapter-driven pair, and the row's key columns come from `strategy.columns_for`:
```python
def run_optimization(strategy: StrategyAdapter, bars_by_tf: dict[str, Bars],
                     spec_by_tf: dict[str, SymbolSpec], base, grid: GridSpec, costs: CostParams,
                     sizing: SizingParams, concurrency: str = "hedge", is_frac: float = 0.7,
                     progress: Callable[[int, int], None] | None = None,
                     min_sl_spread_mult: float = 0.0) -> pd.DataFrame:
    total = grid.size() * len(bars_by_tf)
    init = sizing.initial_equity
    rows: list[dict] = []
    for tf, bars in bars_by_tf.items():
        split = split_time(bars, is_frac)
        n_bars = len(bars)
        spec = spec_by_tf[tf]
        for axis_values in grid.combos(strategy):
            params = strategy.make_params(base, axis_values)
            signals = strategy.run(bars, params)
            key_cols = strategy.columns_for(axis_values)
            for tp in grid.tp_r:
                res = run_backtest(bars, signals, float(tp), spec, costs, sizing, concurrency,
                                   min_sl_spread_mult=min_sl_spread_mult)
                tr = res.trades
                reasons = res.skipped["reason"] if len(res.skipped) else None
                n_blocked = int((reasons == "blocked").sum()) if reasons is not None else 0
                n_min_sl = int((reasons == "rejected_min_sl").sum()) if reasons is not None else 0
                full = compute_metrics(tr, res.equity, init, n_blocked=n_blocked, n_bars=n_bars)
                is_tr = tr[tr["entry_time"] < split]
                oos_tr = tr[tr["entry_time"] >= split]
                eq = res.equity
                is_m = _segment_metrics(is_tr, eq[eq.index < split], init)
                oos_m = _segment_metrics(oos_tr, eq[eq.index >= split], init)
                row = {"tf": tf, **key_cols, "tp_r": float(tp), "n_signals": len(signals),
                       "min_sl_mult": float(min_sl_spread_mult), "n_rejected_min_sl": n_min_sl,
                       "htf_seconds": int(getattr(base, "htf_seconds", 0)),
                       "split_time": split, "ruined": bool(res.ruined), "ruin_time": res.ruin_time,
                       "oversized_share": float(tr["oversized"].astype(bool).mean()) if len(tr) else 0.0,
                       "capped_share": float(tr["capped"].astype(bool).mean()) if len(tr) else 0.0}
                row.update(full)
                row.update({f"is_{k}": is_m[k] for k in SPLIT_KEYS})
                row.update({f"oos_{k}": oos_m[k] for k in SPLIT_KEYS})
                rows.append(row)
                if progress:
                    progress(len(rows), total)
    df = pd.DataFrame(rows)
    df["ruin_time"] = pd.to_datetime(df["ruin_time"], utc=True)   # NaT where the run survived
    df = add_robustness(df, grid, strategy)
    df["flags"] = df.apply(lambda r: ";".join(compute_flags(r)), axis=1)
    return df
```

`add_robustness` — keep the docstring's reasoning, swap the hardcoded columns for the adapter's:
```python
def add_robustness(df: pd.DataFrame, grid: GridSpec, strategy: StrategyAdapter) -> pd.DataFrame:
    """Add `robust_r` / `robust_ratio` (neighbourhood plateau) and `grid_edge`.

    Neighbours share every grid axis except `tp_r` and the strategy's robust axis (`atr_mult`),
    and sit within one grid step of this combo on those two. Ruined combos are excluded from the
    pool (their `is_avg_r` is not a sample of anything a live account could have earned) and get
    `robust_r = 0` themselves.
    """
    df = df.reset_index(drop=True).copy()
    robust_col = strategy.axis(strategy.robust_axis).columns[0]
    tp_idx = {float(v): i for i, v in enumerate(grid.tp_r)}
    am_idx = {float(v): i for i, v in enumerate(grid.axes[strategy.robust_axis])}
    ti = df["tp_r"].astype(float).map(tp_idx).to_numpy()
    ai = df[robust_col].astype(float).map(am_idx).to_numpy()
    vals = df["is_avg_r"].astype(float).to_numpy()
    ruined = _col(df, "ruined", False).astype(bool).to_numpy()
    robust = np.full(len(df), np.nan)
    keys = [k for k in strategy.robust_cols if k in df.columns]   # caller-built frames may predate a key
    for _, g in df.groupby(keys, sort=False):
        idx = g.index.to_numpy()
        alive = idx[~ruined[idx]]
        for k in idx:
            if ruined[k]:
                continue
            mask = (np.abs(ti[alive] - ti[k]) <= 1) & (np.abs(ai[alive] - ai[k]) <= 1)
            mask &= alive != k
            if mask.any():
                robust[k] = float(np.median(vals[alive[mask]]))
    df["robust_r"] = np.nan_to_num(robust, nan=0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(vals > 0, np.clip(df["robust_r"].to_numpy() / vals, 0.0, 1.5), 0.0)
    df["robust_ratio"] = ratio
    edge_tp = {float(grid.tp_r[0]), float(grid.tp_r[-1])}
    am_values = grid.axes[strategy.robust_axis]
    edge_am = {float(am_values[0]), float(am_values[-1])}
    df["grid_edge"] = (df["tp_r"].astype(float).isin(edge_tp) | df[robust_col].astype(float).isin(edge_am))
    return df
```

`_param_value` and `recommend`:
```python
def _param_value(row: pd.Series, key: str, int_cols: tuple[str, ...]):
    """One recommended parameter, typed: `tf` stays a string, lengths int, levels float."""
    if key == "tf":
        return row[key]
    return int(row[key]) if key in int_cols else float(row[key])


def recommend(df: pd.DataFrame, strategy: StrategyAdapter, min_trades: int = MIN_TRADES,
              min_oos_trades: int = MIN_OOS_TRADES) -> dict[str, dict | None]:
```
…body unchanged except the final `out[tf] = {...}` line, which becomes
```python
        out[tf] = {"params": {k: _param_value(best, k, strategy.int_cols) for k in strategy.full_key_cols()},
                   "score": float(score.max()), "row": best.to_dict(), "reason": _reason(best)}
```

- [ ] **Step 5: Update the three call sites so the suite compiles**

`tests/test_golden_grid.py` — in `build_grid_df` only, replace the body with:
```python
    from rsi_fvg.backtest.optimize import GridSpec, run_optimization
    from rsi_fvg.strategies.registry import get_adapter
    adapter = get_adapter("rsi2_swing")
    bars_by_tf, spec_by_tf, base, ax = golden_inputs()
    grid = GridSpec.for_strategy(adapter, axes={"rsi_fast": ax["rsi_fast"], "rsi14": ax["rsi_slow_levels"],
                                                "rsi2": ax["rsi_fast_levels"], "atr_mult": ax["atr_mult"]},
                                 tp_r=ax["tp_r"])
    return run_optimization(adapter, bars_by_tf, spec_by_tf, base, grid, COSTS, SIZING, "hedge")
```
**Do not touch `tests/data/golden_rsi2_swing_grid.csv`.**

`scripts/run_rsi2_swing.py` — keep every flag and printed line; change only:
- import `from rsi_fvg.strategies.registry import get_adapter` and set `ADAPTER = get_adapter("rsi2_swing")` next to the other module constants;
- grid construction → `GridSpec.for_strategy(ADAPTER, axes={"rsi_fast": tuple(int(x) for x in a.rsi_fast), "rsi14": _pairs(a.rsi14), "rsi2": _pairs(a.rsi2), "atr_mult": tuple(float(x) for x in a.atr_mult)}, tp_r=a.tp)`;
- `run_optimization(...)` → `run_optimization(ADAPTER, ...)`; `recommend(grid_df)` → `recommend(grid_df, ADAPTER)`; `run_single(...)` → `run_single(ADAPTER, ...)`;
- the top-5 column list → `cols = ADAPTER.full_key_cols() + ["n_trades", ...]` (keep the existing metric columns after it);
- add `run_info["strategy"] = "rsi2_swing"` (Task 4's export reads it).

`rsi_fvg/backtest/export.py` — no rework yet; it imports `KEY_COLS` from `optimize`, which still exists, so it keeps working unchanged.

- [ ] **Step 6: Run the tests**

Run: `python -m pytest tests/test_optimize.py tests/test_golden_grid.py -q`
Expected: all pass, including `test_rsi2_swing_grid_matches_golden` — that green is the proof the refactor is behaviour-preserving.

- [ ] **Step 7: Run the full suite and a CLI smoke run**

Run: `python -m pytest -q` → all pass.
Run: `python scripts/run_rsi2_swing.py --tf M15 --tp 2 --atr-mult 1 --rsi14 75/25 --rsi2 90/10 --risk 1`
Expected: exit 0, one data line, `grid: 1 combos x 1 TF`, a recommendation block (or "no reliable parameter set"), and a new `results/rsi2_swing/<ts>/` folder with `grid.csv`, `report_XAUUSDc.xlsx`, `report_XAUUSDc.html`.

- [ ] **Step 8: Commit**

```bash
git add rsi_fvg/backtest/optimize.py rsi_fvg/strategies/registry.py scripts/run_rsi2_swing.py tests/test_optimize.py tests/test_registry.py tests/test_golden_grid.py
git commit -m "refactor: optimizer drives strategies through the adapter"
```

---

### Task 4: Generic export

**Files:**
- Modify: `rsi_fvg/backtest/export.py`, `tests/test_export.py`

**Interfaces:**
- Consumes: `StrategyAdapter`, `get_adapter`, the grid frame from Task 3.
- Produces:
  - `grid_first_cols(adapter) -> list[str]` — `adapter.full_key_cols()` followed by the existing metric columns.
  - `adapter_from_run_info(run_info) -> StrategyAdapter` — `get_adapter(run_info.get("strategy", "rsi2_swing"))`.
  - `write_csvs(out_dir, grid_df, rec_results, run_info)` — **new fourth argument** (needed for the column order).
  - `write_xlsx(path, grid_df, rec, rec_results, run_info)` and `write_html(path, grid_df, rec, rec_results, run_info, offline=False)` — unchanged signatures; they resolve the adapter from `run_info["strategy"]`.
  - `GRID_FIRST_COLS` stays, equal to `grid_first_cols(get_adapter("rsi2_swing"))`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_export.py`: add `from rsi_fvg.strategies.registry import get_adapter`, set `ADAPTER = get_adapter("rsi2_swing")`, update `_fixture()` to the Task 3 API (`GridSpec.for_strategy(ADAPTER, axes={...}, tp_r=...)`, `run_optimization(ADAPTER, ...)`, `recommend(df, ADAPTER)`, `run_single(ADAPTER, ...)`), add `"strategy": "rsi2_swing"` to the `info` dict it builds, and change every `write_csvs(tmp_path, df, res)` call to `write_csvs(tmp_path, df, res, info)`. Then add:
```python
def test_grid_first_cols_follow_the_adapter():
    from rsi_fvg.backtest.export import grid_first_cols
    cols = grid_first_cols(ADAPTER)
    assert cols[:8] == ["tf", "rsi_fast", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r"]
    assert "flags" in cols and "robust_r" in cols


def test_heatmap_has_one_panel_per_panel_col_combo():
    from rsi_fvg.backtest.export import _fig_heatmaps
    df, rec, res, info = _fixture()
    g = df[df["tf"] == "M5"]
    n_panels = g.groupby(ADAPTER.panel_cols).ngroups
    fig = _fig_heatmaps("M5", g, ADAPTER)
    assert len(fig.data) == n_panels
    assert "RSI(" in fig.layout.annotations[0].text          # adapter title used as the subplot title


def test_unknown_strategy_in_run_info_is_an_error(tmp_path):
    from rsi_fvg.backtest.export import write_xlsx
    df, rec, res, info = _fixture()
    with pytest.raises(KeyError):
        write_xlsx(tmp_path / "r.xlsx", df, rec, res, info | {"strategy": "nope"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_export.py -q`
Expected: `ImportError: cannot import name 'grid_first_cols'` / `_fig_heatmaps() takes 2 positional arguments`.

- [ ] **Step 3: Rewrite the strategy-aware parts of `rsi_fvg/backtest/export.py`**

Imports: replace `from .optimize import KEY_COLS` with
```python
from ..strategies.registry import StrategyAdapter, get_adapter
from .optimize import FILTER_TEXT
```
Constants: replace the `GRID_FIRST_COLS = KEY_COLS + [...]` assignment with
```python
GRID_METRIC_COLS = ["n_signals", "n_rejected_min_sl",
                    "n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct",
                    "net_pnl", "final_equity", "ruined", "oversized_share", "capped_share",
                    "is_n_trades", "is_avg_r", "is_max_dd_pct", "oos_n_trades", "oos_avg_r",
                    "oos_max_dd_pct", "robust_r", "robust_ratio", "grid_edge", "flags"]


def grid_first_cols(adapter: StrategyAdapter) -> list[str]:
    return adapter.full_key_cols() + GRID_METRIC_COLS


def adapter_from_run_info(run_info: dict) -> StrategyAdapter:
    return get_adapter(run_info.get("strategy", "rsi2_swing"))


GRID_FIRST_COLS = grid_first_cols(get_adapter("rsi2_swing"))
```
`_order_grid` gains the adapter:
```python
def _order_grid(df: pd.DataFrame, adapter: StrategyAdapter) -> pd.DataFrame:
    first = [c for c in grid_first_cols(adapter) if c in df.columns]
    rest = [c for c in df.columns if c not in first]
    return df[first + rest]
```
`_rec_table` becomes strategy-agnostic — replace its `row.update({k: r["params"][k] for k in KEY_COLS if k != "tf"})` line with
```python
            row.update({k: v for k, v in r["params"].items() if k != "tf"})
```
`_fig_heatmaps` — panels and titles from the adapter, y axis from its robust column:
```python
def _fig_heatmaps(tf: str, g: pd.DataFrame, adapter: StrategyAdapter) -> go.Figure:
    y_col = adapter.axis(adapter.robust_axis).columns[0]
    panel_cols = adapter.panel_cols
    groups = list(g.groupby(panel_cols, sort=True))
    n = len(groups)
    cols = min(3, max(n, 1))
    rows = int(np.ceil(n / cols)) if n else 1
    titles = [adapter.title(dict(zip(panel_cols, key if isinstance(key, tuple) else (key,))))
              for key, _ in groups]
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=titles,
                        horizontal_spacing=0.06, vertical_spacing=0.12)
    zmax = float(np.nanmax(np.abs(g["oos_avg_r"].to_numpy()))) if len(g) else 1.0
    zmax = max(zmax, 1e-9)
    for i, (_, gg) in enumerate(groups):
        piv = gg.pivot(index=y_col, columns="tp_r", values="oos_avg_r").sort_index()
        ntr = gg.pivot(index=y_col, columns="tp_r", values="n_trades").reindex_like(piv)
        text = [[("" if (pd.isna(v) or pd.isna(k)) else f"{v:+.2f}<br>n={int(k)}")
                 for v, k in zip(rv, rk)] for rv, rk in zip(piv.values, ntr.values)]
        fig.add_trace(go.Heatmap(z=piv.values, x=[f"TP {c:g}R" for c in piv.columns],
                                 y=[f"{y_col}×{r:g}" for r in piv.index], colorscale=_DIVERGING, zmid=0,
                                 zmin=-zmax, zmax=zmax, text=text, texttemplate="%{text}",
                                 showscale=(i == 0), colorbar=dict(title="OOS avg R")),
                      row=i // cols + 1, col=i % cols + 1)
    fig.update_layout(title=f"{tf} — OOS avg R heatmap (TP × {y_col}) per parameter set",
                      height=300 * rows + 80, margin=dict(l=40, r=20, t=70, b=30))
    return _apply_theme(fig)
```
`_fig_is_oos` — label via the adapter:
```python
def _fig_is_oos(tf: str, g: pd.DataFrame, adapter: StrategyAdapter) -> go.Figure:
    labels = [f"TP {row['tp_r']:g}R · {adapter.title(row)}"
              f"<br>n={int(row['n_trades'])} · flags: {row['flags'] or '-'}"
              for row in g.to_dict("records")]
```
…rest of the function unchanged.

`write_csvs`, `write_xlsx`, `write_html` — resolve the adapter and pass it down:
```python
def write_csvs(out_dir: Path, grid_df: pd.DataFrame, rec_results: dict[str, BacktestResult],
               run_info: dict) -> None:
    adapter = adapter_from_run_info(run_info)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _order_grid(grid_df, adapter).to_csv(out_dir / "grid.csv", index=False)
    for tf, res in rec_results.items():
        res.trades.to_csv(out_dir / f"trades_{tf}.csv", index=False)
        if len(res.skipped):
            res.skipped.to_csv(out_dir / f"skipped_{tf}.csv", index=False)
```
In `write_xlsx`: first line of the body becomes `adapter = adapter_from_run_info(run_info)`, and `grid = _order_grid(grid_df.copy())` becomes `grid = _order_grid(grid_df.copy(), adapter)`.
In `write_html`: add `adapter = adapter_from_run_info(run_info)` next to `include = ...`, pass `adapter` to both `_fig_heatmaps(tf, g, adapter)` and `_fig_is_oos(tf, g, adapter)`, and change the top-10 table's column list from `GRID_FIRST_COLS` to `grid_first_cols(adapter)`.

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_export.py tests/test_golden_grid.py -q`
Expected: all pass.

- [ ] **Step 5: Update the one remaining `write_csvs` caller and run everything**

`scripts/run_rsi2_swing.py`: `write_csvs(out_dir, grid_df, rec_results)` → `write_csvs(out_dir, grid_df, rec_results, run_info)` (move the `run_info` assignment above it if needed).
Run: `python -m pytest -q` → all pass.
Run: `python scripts/run_rsi2_swing.py --tf M15 --tp 2 --atr-mult 1 --rsi14 75/25 --rsi2 90/10 --risk 1` → exit 0; open the produced `report_XAUUSDc.html` size check only (`ls -l`), no browser needed.

- [ ] **Step 6: Commit**

```bash
git add rsi_fvg/backtest/export.py scripts/run_rsi2_swing.py tests/test_export.py
git commit -m "refactor: export reads grid columns from the strategy adapter"
```

---

### Task 5: EMA indicator, the `rsi2_ema_swing` strategy, and its adapter

**Files:**
- Create: `rsi_fvg/strategies/rsi2_ema_swing.py`, `tests/test_rsi2_ema_swing.py`
- Modify: `rsi_fvg/indicators.py`, `tests/test_indicators.py`, `rsi_fvg/strategies/registry.py`, `tests/test_registry.py`

**Interfaces:**
- Consumes: `Bars`, `Signal`, `Direction`, `rsi_wilder`, `atr_wilder`, and from `rsi2_swing`: `cross_up`, `cross_down`, `swing_structure`, `htf_rsi`.
- Produces:
  - `indicators.ema(close: np.ndarray, period: int) -> np.ndarray`
  - `Rsi2EmaParams(rsi_fast=2, fast_hi=90.0, fast_lo=10.0, ema_fast=20, ema_slow=100, atr_len=14, atr_mult=1.5, htf_seconds=0, htf_rsi_len=14, htf_level=50.0)` frozen dataclass
  - `rsi2_ema_swing.VARIANT = "EMASWING"`
  - `compute_inputs(bars, params) -> tuple[rsi_fast, ema_fast, ema_slow, atr, htf | None]`
  - `run_strategy(bars, params, directions=(Direction.BUY, Direction.SELL)) -> list[Signal]`
  - registry entry `"rsi2_ema_swing"` with `key_cols == ("rsi_fast", "f_hi", "f_lo", "ema_fast", "ema_slow", "atr_mult")` and `GridSpec.for_strategy(adapter).size() == 384`

- [ ] **Step 1: Write the failing EMA test**

Append to `tests/test_indicators.py`:
```python
def test_ema_hand_computed_with_nan_warmup():
    from rsi_fvg.indicators import ema
    close = np.array([10.0, 20.0, 30.0, 40.0])
    got = ema(close, 3)                      # alpha = 0.5, seed = close[0]
    assert np.isnan(got[0]) and np.isnan(got[1])
    assert got[2] == pytest.approx(22.5)     # 10 -> 15 -> 22.5
    assert got[3] == pytest.approx(31.25)


def test_ema_period_one_is_the_close_and_short_input_is_safe():
    from rsi_fvg.indicators import ema
    close = np.array([5.0, 7.0, 9.0])
    np.testing.assert_allclose(ema(close, 1), close)
    assert np.all(np.isnan(ema(close, 10)))
    assert ema(np.array([]), 5).shape == (0,)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_indicators.py -q`
Expected: `ImportError: cannot import name 'ema'`.

- [ ] **Step 3: Add `ema` to `rsi_fvg/indicators.py`**

```python
def ema(close: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average, `alpha = 2/(period+1)`, recursion seeded with `close[0]`.

    The first `period-1` values are NaN so callers skip the warm-up. Pine's `ta.ema` emits
    values there instead — that prefix is the one intended Python/Pine divergence, and it is
    far behind the first tradable bar on any real series.
    """
    close = np.asarray(close, dtype=np.float64)
    n = close.shape[0]
    out = np.full(n, np.nan)
    if n == 0:
        return out
    alpha = 2.0 / (period + 1.0)
    prev = float(close[0])
    for i in range(n):
        if i:
            prev += alpha * (float(close[i]) - prev)
        if i >= period - 1:
            out[i] = prev
    return out
```

Run: `python -m pytest tests/test_indicators.py -q` → all pass.

- [ ] **Step 4: Write the failing strategy tests**

`tests/test_rsi2_ema_swing.py`:
```python
import numpy as np
import pytest

from rsi_fvg.bars import Bars
from rsi_fvg.signals import Direction
from rsi_fvg.strategies.rsi2_ema_swing import Rsi2EmaParams, compute_inputs, run_strategy

P = Rsi2EmaParams()


def _bars(closes, wick=0.5, step=300):
    closes = np.asarray(closes, dtype=np.float64)
    opens = np.r_[closes[0], closes[:-1]]
    high = np.maximum(opens, closes) + wick
    low = np.minimum(opens, closes) - wick
    return Bars(time=1_700_000_000 + np.arange(len(closes), dtype=np.int64) * step,
                open=opens, high=high, low=low, close=closes)


def _rng_bars(n=4000, seed=9, drift=0.0):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(drift, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    return Bars(time=1_700_000_000 + np.arange(n, dtype=np.int64) * 300,
                open=open_, high=high, low=low, close=close)


def test_signals_only_where_the_ema_trend_agrees():
    """Same price path, two EMA settings: the up-trend one buys, the reversed one does not."""
    bars = _rng_bars(seed=3, drift=0.6)          # rising series -> ema_fast > ema_slow
    up = run_strategy(bars, Rsi2EmaParams(ema_fast=20, ema_slow=100))
    down = run_strategy(bars, Rsi2EmaParams(ema_fast=100, ema_slow=20))   # inverted comparison
    assert any(s.direction == Direction.BUY for s in up)
    assert all(s.direction == Direction.SELL for s in down) or not down
    assert all(s.variant == "EMASWING" for s in up + down)


def test_buy_carries_swing_low_sl_and_segment_anchor():
    bars = _rng_bars(seed=3, drift=0.6)
    params = Rsi2EmaParams(atr_mult=1.5)
    rsi_f, ema_f, ema_s, atr, _ = compute_inputs(bars, params)
    buys = [s for s in run_strategy(bars, params) if s.direction == Direction.BUY]
    assert buys
    s = buys[0]
    lo = bars.low[s.anchor_bar:s.signal_bar + 1].min()
    assert s.swing_price == pytest.approx(lo)
    assert s.sl_price == pytest.approx(s.swing_price - 1.5 * atr[s.signal_bar])
    assert s.ref_price == bars.close[s.signal_bar]
    assert s.bars_in_wait == s.signal_bar - s.anchor_bar > 0
    assert ema_f[s.signal_bar] > ema_s[s.signal_bar]


def test_sell_mirrors_on_swing_high():
    bars = _rng_bars(seed=4, drift=-0.6)
    params = Rsi2EmaParams(atr_mult=2.0)
    _, ema_f, ema_s, atr, _ = compute_inputs(bars, params)
    sells = [s for s in run_strategy(bars, params) if s.direction == Direction.SELL]
    assert sells
    s = sells[0]
    hi = bars.high[s.anchor_bar:s.signal_bar + 1].max()
    assert s.swing_price == pytest.approx(hi)
    assert s.sl_price == pytest.approx(s.swing_price + 2.0 * atr[s.signal_bar])
    assert ema_f[s.signal_bar] < ema_s[s.signal_bar]


def test_equal_emas_produce_no_signal():
    bars = _rng_bars(seed=5)
    same = run_strategy(bars, Rsi2EmaParams(ema_fast=20, ema_slow=20))
    assert same == []


def test_directions_argument_filters():
    bars = _rng_bars(seed=3, drift=0.6)
    only_buy = run_strategy(bars, P, directions=(Direction.BUY,))
    assert only_buy and all(s.direction == Direction.BUY for s in only_buy)


def test_no_signal_during_the_ema_warmup():
    bars = _rng_bars(seed=6)
    sigs = run_strategy(bars, Rsi2EmaParams(ema_slow=200))
    assert all(s.signal_bar >= 199 for s in sigs)


def test_htf_gate_blocks_and_allows():
    bars = _rng_bars(seed=3, drift=0.6)
    off = run_strategy(bars, Rsi2EmaParams())
    on = run_strategy(bars, Rsi2EmaParams(htf_seconds=3600))
    assert len(on) <= len(off)
    assert {(s.signal_bar, s.direction) for s in on} <= {(s.signal_bar, s.direction) for s in off}
    impossible = run_strategy(bars, Rsi2EmaParams(htf_seconds=3600, htf_level=1000.0))
    assert not [s for s in impossible if s.direction == Direction.BUY]


def test_sorted_and_deterministic():
    bars = _rng_bars(seed=7)
    sigs = run_strategy(bars, P)
    keys = [(s.signal_bar, int(s.direction)) for s in sigs]
    assert keys == sorted(keys)
    assert sigs == run_strategy(bars, P)


@pytest.mark.parametrize("k", [500, 1000, 2500, 3999])
def test_prefix_invariance_no_lookahead(k):
    bars = _rng_bars(seed=8)
    full = run_strategy(bars, P)
    prefix = run_strategy(bars.slice(0, k), P)
    want = [s for s in full if s.signal_bar < k]
    assert prefix == want
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `python -m pytest tests/test_rsi2_ema_swing.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.strategies.rsi2_ema_swing'`.

- [ ] **Step 6: Write `rsi_fvg/strategies/rsi2_ema_swing.py`**

```python
"""RSI2 swing + EMA trend strategy.

Spec: docs/superpowers/specs/2026-09-08-rsi2-ema-swing-strategy-design.md §2.

The RSI(2) swing structure is the same one `rsi2_swing` uses (imported, not copied). What
changes is the trigger: there is no RSI(14) arm-and-wait state machine, so every confirmed
swing whose side agrees with the EMA trend is a signal. Whether that signal can actually open
a position (one per direction) is the engine's business, not this module's.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..bars import Bars
from ..indicators import atr_wilder, ema, rsi_wilder
from ..signals import Direction, Signal
from .rsi2_swing import cross_down, cross_up, htf_rsi, swing_structure

VARIANT = "EMASWING"


@dataclass(frozen=True)
class Rsi2EmaParams:
    rsi_fast: int = 2
    fast_hi: float = 90.0
    fast_lo: float = 10.0
    ema_fast: int = 20
    ema_slow: int = 100
    atr_len: int = 14
    atr_mult: float = 1.5
    htf_seconds: int = 0            # 0 = trend gate off; 3600 = H1
    htf_rsi_len: int = 14
    htf_level: float = 50.0


def compute_inputs(bars: Bars, params: Rsi2EmaParams):
    rsi_f = rsi_wilder(bars.close, params.rsi_fast)
    ema_f = ema(bars.close, params.ema_fast)
    ema_s = ema(bars.close, params.ema_slow)
    atr = atr_wilder(bars.high, bars.low, bars.close, params.atr_len)
    htf = htf_rsi(bars, params.htf_seconds, params.htf_rsi_len) if params.htf_seconds > 0 else None
    return rsi_f, ema_f, ema_s, atr, htf


def run_strategy(bars: Bars, params: Rsi2EmaParams,
                 directions: tuple[Direction, ...] = (Direction.BUY, Direction.SELL)) -> list[Signal]:
    rsi_f, ema_f, ema_s, atr, htf = compute_inputs(bars, params)
    f_up = cross_up(rsi_f, params.fast_hi)
    f_dn = cross_down(rsi_f, params.fast_lo)
    ev = swing_structure(bars.high, bars.low, f_up, f_dn)
    want_buy = Direction.BUY in directions
    want_sell = Direction.SELL in directions

    out: list[Signal] = []
    low_start = -1        # bar the current LOW segment started on (the last cross under fast_lo)
    high_start = -1
    for t in range(len(bars)):
        usable = not (math.isnan(ema_f[t]) or math.isnan(ema_s[t]) or math.isnan(atr[t]))
        if htf is None:
            gate_buy = gate_sell = True
        else:                                  # NaN htf fails both comparisons, which is the intent
            gate_buy = bool(htf[t] > params.htf_level)
            gate_sell = bool(htf[t] < params.htf_level)
        if usable and want_buy and ev.low_conf[t] and low_start >= 0 and gate_buy \
                and ema_f[t] > ema_s[t]:
            swing = float(ev.low_price[t])
            out.append(Signal(direction=Direction.BUY, variant=VARIANT, signal_bar=t,
                              anchor_bar=low_start, ref_price=float(bars.close[t]),
                              sl_price=swing - params.atr_mult * float(atr[t]),
                              bars_in_wait=t - low_start, swing_price=swing))
        if usable and want_sell and ev.high_conf[t] and high_start >= 0 and gate_sell \
                and ema_f[t] < ema_s[t]:
            swing = float(ev.high_price[t])
            out.append(Signal(direction=Direction.SELL, variant=VARIANT, signal_bar=t,
                              anchor_bar=high_start, ref_price=float(bars.close[t]),
                              sl_price=swing + params.atr_mult * float(atr[t]),
                              bars_in_wait=t - high_start, swing_price=swing))
        # segment starts are updated AFTER emitting: the swing confirmed at t belongs to the
        # segment that began at the previous opposite cross.
        if f_dn[t]:
            low_start = t
        if f_up[t]:
            high_start = t
    out.sort(key=lambda s: (s.signal_bar, int(s.direction)))
    return out
```

- [ ] **Step 7: Run the strategy tests**

Run: `python -m pytest tests/test_rsi2_ema_swing.py -q`
Expected: `13 passed` (9 tests + 4 parametrised prefix cases). If `test_signals_only_where_the_ema_trend_agrees` finds no BUY, raise the drift or the seed until the rising series produces swings — do not weaken the assertion that a signal requires `ema_fast > ema_slow`.

- [ ] **Step 8: Register the adapter**

In `rsi_fvg/strategies/registry.py`, add the import `from .rsi2_ema_swing import Rsi2EmaParams` and `from .rsi2_ema_swing import run_strategy as run_rsi2_ema_swing`, then after `RSI2_SWING`:
```python
def _rsi2_ema_title(row: dict) -> str:
    return (f"RSI({int(row['rsi_fast'])}) {int(row['f_hi'])}/{int(row['f_lo'])}"
            f" · EMA {int(row['ema_fast'])}/{int(row['ema_slow'])}")


RSI2_EMA_SWING = StrategyAdapter(
    name="rsi2_ema_swing",
    axes=(Axis("rsi_fast", ("rsi_fast",), ("rsi_fast",), int_cols=("rsi_fast",)),
          Axis("rsi2", ("f_hi", "f_lo"), ("fast_hi", "fast_lo")),
          Axis("ema", ("ema_fast", "ema_slow"), ("ema_fast", "ema_slow"),
               int_cols=("ema_fast", "ema_slow")),
          Axis("atr_mult", ("atr_mult",), ("atr_mult",))),
    default_axes={"rsi_fast": (2, 3, 5),
                  "rsi2": ((90.0, 10.0), (95.0, 5.0)),
                  "ema": ((20, 100), (20, 200), (50, 200), (10, 50)),
                  "atr_mult": (1.0, 1.5, 2.0, 3.0)},
    default_tp_r=(2.0, 4.0, 6.0, 8.0),
    params_cls=Rsi2EmaParams,
    run=run_rsi2_ema_swing,
    panel_title=_rsi2_ema_title,
)

STRATEGIES: dict[str, StrategyAdapter] = {a.name: a for a in (RSI2_SWING, RSI2_EMA_SWING)}
```
(delete the previous single-entry `STRATEGIES` assignment).

Add to `tests/test_registry.py`:
```python
def test_rsi2_ema_swing_adapter():
    from rsi_fvg.backtest.optimize import GridSpec
    from rsi_fvg.strategies.rsi2_ema_swing import Rsi2EmaParams
    a = get_adapter("rsi2_ema_swing")
    assert a.key_cols == ("rsi_fast", "f_hi", "f_lo", "ema_fast", "ema_slow", "atr_mult")
    assert a.robust_cols == ["tf", "rsi_fast", "f_hi", "f_lo", "ema_fast", "ema_slow"]
    assert GridSpec.for_strategy(a).size() == 384
    p = a.make_params(Rsi2EmaParams(), {"rsi_fast": 5, "rsi2": (95.0, 5.0),
                                        "ema": (50, 200), "atr_mult": 2.0})
    assert (p.rsi_fast, p.fast_hi, p.fast_lo, p.ema_fast, p.ema_slow, p.atr_mult) == (5, 95.0, 5.0, 50, 200, 2.0)
    assert isinstance(p.ema_fast, int) and isinstance(p.ema_slow, int)
    assert a.title({"rsi_fast": 2, "f_hi": 90.0, "f_lo": 10.0, "ema_fast": 20,
                    "ema_slow": 100}) == "RSI(2) 90/10 · EMA 20/100"
```

- [ ] **Step 9: Run a small end-to-end grid on the new strategy**

Run:
```bash
python -c "import sys; sys.path.insert(0,'.'); \
from rsi_fvg.backtest.optimize import GridSpec, run_optimization, recommend; \
from rsi_fvg.strategies.registry import get_adapter; \
from rsi_fvg.strategies.rsi2_ema_swing import Rsi2EmaParams; \
from rsi_fvg.params import CostParams, SizingParams, SymbolSpec; \
import numpy as np; from rsi_fvg.bars import Bars; \
rng=np.random.default_rng(2); n=6000; c=2000+np.cumsum(rng.normal(0,2,n)); o=np.r_[c[0],c[:-1]]; \
b=Bars(time=np.arange(n,dtype=np.int64)*300, open=o, high=np.maximum(o,c)+1, low=np.minimum(o,c)-1, close=c); \
a=get_adapter('rsi2_ema_swing'); g=GridSpec.for_strategy(a, axes={'rsi_fast':(2,),'rsi2':((90.,10.),),'ema':((20,100),(50,200)),'atr_mult':(1.5,)}, tp_r=(4.,8.)); \
df=run_optimization(a,{'M5':b},{'M5':SymbolSpec(name='T',point=0.01,digits=2,contract_size=1.0)},Rsi2EmaParams(),g,CostParams(spread_points=20,commission_per_lot_rt=0.0,slippage_points=0),SizingParams(risk_pct=1.0,initial_equity=10000.0)); \
print(len(df), list(df.columns[:8])); print(df[['ema_fast','ema_slow','tp_r','n_signals','n_trades','avg_r']].to_string(index=False))"
```
Expected: 4 rows, columns start `tf, rsi_fast, f_hi, f_lo, ema_fast, ema_slow, atr_mult, tp_r`, `n_signals > 0`, and the two `tp_r` rows of one EMA pair share the same `n_signals`. Paste this output into your report.

- [ ] **Step 10: Full suite and commit**

Run: `python -m pytest -q` → all pass.
```bash
git add rsi_fvg/indicators.py rsi_fvg/strategies/rsi2_ema_swing.py rsi_fvg/strategies/registry.py tests/test_indicators.py tests/test_rsi2_ema_swing.py tests/test_registry.py
git commit -m "feat: rsi2 swing + EMA trend strategy and its adapter"
```

---

### Task 6: Pine version

**Files:**
- Create: `pine/rsi2_ema_swing_strategy.pine`

**Interfaces:** none (Pine is standalone). The reference file is `pine/rsi2_swing_strategy.pine` at this commit — read it fully first; the new file is that file with the edits below.

Pine cannot be compiled in this environment. Write carefully: no comma-chained statements on one line, no `str.format` with literal braces (build alert JSON by concatenation), keep the file's 4-space indentation per level, and do not redeclare a variable in the same scope.

- [ ] **Step 1: Copy the reference file**

```bash
cp pine/rsi2_swing_strategy.pine pine/rsi2_ema_swing_strategy.pine
```

- [ ] **Step 2: Header and `strategy()` call**

Replace the whole header comment block with:
```
//@version=6
// =============================================================================
//  RSI2 Swing + EMA Trend Strategy
//
//  Structure (same as RSI2 Swing Pullback):
//    RSI(rsiFastLen) with levels fHi/fLo splits the chart into alternating segments.
//    HIGH segment: cross UP fHi -> ... -> cross DOWN fLo  => swing high = highest(high)
//    LOW  segment: cross DOWN fLo -> ... -> cross UP fHi  => swing low  = lowest(low)
//    A swing is only KNOWN when its segment ends; that bar is the signal bar.
//
//  Entry (no RSI14 arm-and-wait here):
//    BUY  when a swing LOW is confirmed AND emaFast > emaSlow.
//    SELL when a swing HIGH is confirmed AND emaFast < emaSlow.
//    SL = swing -/+ AtrMult*ATR(14).  TP = TP_R x risk, from the real fill price.
//    Optional H1 RSI(rsiSlowLen) trend gate on top (same idiom as the sibling script).
//
//  Python twin: rsi_fvg/strategies/rsi2_ema_swing.py. Spec:
//    docs/superpowers/specs/2026-09-08-rsi2-ema-swing-strategy-design.md
//  Known divergence: Python leaves the first ema_slow-1 bars NaN (no signals there); Pine's
//  ta.ema emits values from bar 0. Everything after the warm-up matches.
//
//  Known divergences vs a hedging MT5 backtest (by design):
//   1. Pine has no spread model. `slippage` (~spread/2 in ticks) approximates it.
//   2. Pine cannot hedge (net position). `Block opposite while in trade` = true skips
//      opposite signals instead of reversing.
// =============================================================================
```
and in the `strategy(...)` call change the two names only:
`strategy("RSI2 EMA Swing", shorttitle="RSI2-EMA", overlay=true,` (keep every other argument identical).

- [ ] **Step 3: Inputs**

In the `grpTrig` block, **delete** the `sHi` and `sLo` inputs (the RSI14 arm levels are gone) and keep `rsiSlowLen`, `useHtf`, `htfTf` (the gate still uses RSI(rsiSlowLen) on the higher timeframe). Change the group label string to `grpTrig = "Trend filter"`.

In the `grpStruct` block set `rsiFastLen = input.int(2, ...)`, `fHi = input.float(90, ...)`, `fLo = input.float(10, ...)` (defaults unchanged from the reference).

Add a new group directly after `grpStruct`'s inputs:
```
grpEma = "EMA trend"
emaFastLen = input.int(20, "EMA fast", minval=1, group=grpEma)
emaSlowLen = input.int(100, "EMA slow", minval=1, group=grpEma)
```
In `grpEntry` set `tpR = input.float(8.0, ...)` and `riskPct = input.float(1.0, ...)`; delete the `maxWait` input. In `grpSL` set `atrMult = input.float(1.5, ...)` and keep `minSlTicks`.

- [ ] **Step 4: Indicators**

After the existing `atr = ta.atr(atrLen)` line add:
```
emaFast = ta.ema(close, emaFastLen)
emaSlow = ta.ema(close, emaSlowLen)
bool trendUp = emaFast > emaSlow
bool trendDn = emaFast < emaSlow
```
Delete the `sUp` / `sDn` cross definitions (RSI14 arm crosses) and keep `fUp` / `fDn`. Keep the `ok` guard and the `htfRsi` line unchanged.

- [ ] **Step 5: Replace both state machines with the swing-confirmation trigger**

Delete everything from the `// ---- BUY state machine ----` comment through the end of the SELL state machine (the `bState`/`sState` blocks and their `var` declarations), and delete the two `bgcolor(...)` state-shading lines plus the `bTxt`/`sTxt` rows of the status table. Keep the swing-structure block (`seg`, `segHigh`, `segLow`, `swingLowConf`, `confSwingLow`, `swingHighConf`, `confSwingHigh`, the labels and zigzag) exactly as it is.

In its place put:
```
// ------------------------------------------------------------- triggers ----
// Every confirmed swing whose side agrees with the EMA trend is a signal. There is no
// arm-and-wait flag to consume, so a failed gate simply produces nothing.
bool buyTrig  = false
float buySL   = na
bool sellTrig = false
float sellSL  = na

if ok and swingLowConf and trendUp and (not useHtf or htfRsi > 50)
    buyTrig := true
    buySL   := confSwingLow - atrMult * atr

if ok and swingHighConf and trendDn and (not useHtf or htfRsi < 50)
    sellTrig := true
    sellSL   := confSwingHigh + atrMult * atr
```

- [ ] **Step 6: Execution block and visuals**

The execution block stays as it is except: remove `buyWait` / `sellWait` from the alert JSON (they no longer exist) — the two `alertJson :=` lines lose their `,"bars_since_flag":' + str.tostring(...)` term and end with `+ '}'` after `ref_price`. Change both entry comments to `comment="BUY ema swing"` / `comment="SELL ema swing"`.

Add the EMA plots next to the SL/TP plots:
```
plot(emaFast, "EMA fast", color=color.new(color.aqua, 0), linewidth=1)
plot(emaSlow, "EMA slow", color=color.new(color.orange, 0), linewidth=1)
```
In the status table, keep the RSI row and the segment row, and replace the two state rows with:
```
    table.cell(tbl, 0, 3, "EMA f/s", text_size=size.small)
    table.cell(tbl, 1, 3, str.tostring(emaFast, "#.##") + " / " + str.tostring(emaSlow, "#.##"), text_size=size.small)
    table.cell(tbl, 0, 4, "Trend", text_size=size.small)
    table.cell(tbl, 1, 4, trendUp ? "UP" : trendDn ? "DOWN" : "flat", text_size=size.small)
```

- [ ] **Step 7: Mechanical checks**

Run:
```bash
grep -nE ", [a-zA-Z]+ := |alertcondition|str\.format|bState|sState|sUp|sDn|maxWait|buyWait|sellWait" pine/rsi2_ema_swing_strategy.pine || echo "clean"
grep -c "" pine/rsi2_ema_swing_strategy.pine
python - <<'PY'
import re
s = open("pine/rsi2_ema_swing_strategy.pine", encoding="utf-8").read()
assert "emaFast = ta.ema(close, emaFastLen)" in s
assert s.count("//@version=6") == 1
bad = [i for i, l in enumerate(s.splitlines(), 1)
       if l.startswith(" ") and (len(l) - len(l.lstrip(" "))) % 4]
print("indent-not-multiple-of-4 lines:", bad)
PY
```
Expected: `clean`, a line count around 250, and an empty indent list.

- [ ] **Step 8: Commit**

```bash
git add pine/rsi2_ema_swing_strategy.pine
git commit -m "feat(pine): RSI2 swing + EMA trend strategy"
```

---

### Task 7: Generic CLI, docs, smoke tests

**Files:**
- Create: `scripts/optimize.py`
- Modify: `README.md`, `docs/superpowers/specs/2026-09-08-rsi2-ema-swing-strategy-design.md`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `get_adapter`, `STRATEGIES`, `GridSpec.for_strategy`, `run_optimization`, `recommend`, `run_single`, `write_csvs/write_xlsx/write_html`, `load_or_fetch`, `load_config`.
- Produces: `scripts/optimize.py` writing `results/<strategy>/<YYYYMMDD_HHMMSS>/{grid.csv,trades_<TF>.csv,report_<symbol>.xlsx,report_<symbol>.html}`; helpers `parse_axis(text) -> tuple[str, tuple]` and `build_base(adapter, htf_seconds, max_wait) -> params`.

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/test_cli.py` (it already has `_write_cache(data_dir: Path, n=3000, seed=7) -> None`, which writes `XAUUSDc_M5.parquet` plus its `.spec.json` sidecar into `data_dir`; the three new tests below call it as `data_dir = tmp_path / "data"; data_dir.mkdir(); _write_cache(data_dir)`):
```python
def test_optimize_cli_runs_rsi2_ema_swing(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_cache(data_dir)
    out = tmp_path / "results"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "optimize.py"),
                        "--strategy", "rsi2_ema_swing", "--tf", "M5",
                        "--axis", "ema=20/100", "--axis", "atr_mult=1.5",
                        "--axis", "rsi_fast=2", "--axis", "rsi2=90/10",
                        "--tp", "4", "--risk", "1",
                        "--data-dir", str(data_dir), "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    folders = list((out).glob("*"))
    assert len(folders) == 1
    produced = {p.name for p in folders[0].iterdir()}
    assert "grid.csv" in produced
    assert any(n.startswith("report_") and n.endswith(".xlsx") for n in produced)
    assert any(n.startswith("report_") and n.endswith(".html") for n in produced)
    head = (folders[0] / "grid.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert head[:8] == ["tf", "rsi_fast", "f_hi", "f_lo", "ema_fast", "ema_slow", "atr_mult", "tp_r"]


def test_optimize_cli_runs_rsi2_swing_too(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_cache(data_dir)
    out = tmp_path / "results2"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "optimize.py"),
                        "--strategy", "rsi2_swing", "--tf", "M5",
                        "--axis", "rsi14=80/20", "--axis", "rsi2=90/10",
                        "--axis", "rsi_fast=2", "--axis", "atr_mult=1.5",
                        "--tp", "4", "--risk", "1",
                        "--data-dir", str(data_dir), "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    head = (next((out).glob("*")) / "grid.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert head[:8] == ["tf", "rsi_fast", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r"]


def test_optimize_cli_rejects_bad_axis(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_cache(data_dir)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "optimize.py"),
                        "--strategy", "rsi2_ema_swing", "--tf", "M5", "--axis", "nope=1",
                        "--data-dir", str(data_dir), "--out", str(tmp_path / "r3")],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode != 0
    assert "nope" in (r.stdout + r.stderr)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_cli.py -q`
Expected: failures because `scripts/optimize.py` does not exist.

- [ ] **Step 3: Write `scripts/optimize.py`**

```python
"""Grid-optimise a registered strategy on cached MT5 data and export xlsx + html.

Usage:
  python scripts/optimize.py --strategy rsi2_ema_swing --tf M5 M15 H1 --risk 1
  python scripts/optimize.py --strategy rsi2_ema_swing --tf M5 --axis ema=20/100,50/200 --tp 4 8
  python scripts/optimize.py --strategy rsi2_swing --tf M15 --axis rsi14=80/20 --htf 3600

An axis not named on the command line keeps the strategy's default values. Pairs are written
`a/b` (`--axis ema=20/100`, `--axis rsi2=95/5`). `--list-axes` prints what a strategy accepts.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import fields, replace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from rsi_fvg.backtest.export import write_csvs, write_html, write_xlsx  # noqa: E402
from rsi_fvg.backtest.optimize import GridSpec, recommend, run_optimization, run_single  # noqa: E402
from rsi_fvg.bars import Bars  # noqa: E402
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.params import load_config  # noqa: E402
from rsi_fvg.strategies.registry import STRATEGIES, get_adapter  # noqa: E402


def parse_axis(text: str) -> tuple[str, tuple]:
    """`ema=20/100,50/200` -> ("ema", ((20.0, 100.0), (50.0, 200.0)))."""
    if "=" not in text:
        raise argparse.ArgumentTypeError(f"expected name=v1,v2 — got {text!r}")
    name, values = text.split("=", 1)
    out = []
    for chunk in values.split(","):
        chunk = chunk.strip()
        if not chunk:
            raise argparse.ArgumentTypeError(f"axis {name}: empty value in {text!r}")
        try:
            out.append(tuple(float(x) for x in chunk.split("/")) if "/" in chunk else float(chunk))
        except ValueError as e:
            raise argparse.ArgumentTypeError(f"axis {name}: {chunk!r} is not a number") from e
    return name.strip(), tuple(out)


def build_base(adapter, htf_seconds: int, max_wait: int):
    """Params object with the run-level switches applied, skipping fields it does not have."""
    have = {f.name for f in fields(adapter.params_cls)}
    overrides = {k: v for k, v in (("htf_seconds", htf_seconds), ("max_wait", max_wait)) if k in have}
    return replace(adapter.params_cls(), **overrides)


def _git_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strategy", default="rsi2_ema_swing", choices=sorted(STRATEGIES))
    ap.add_argument("--list-axes", action="store_true", help="print the strategy's axes and defaults, then exit")
    ap.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    ap.add_argument("--symbol")
    ap.add_argument("--tf", nargs="*")
    ap.add_argument("--axis", action="append", default=[], metavar="NAME=V1,V2",
                    help="override one grid axis; repeatable. Pairs are a/b")
    ap.add_argument("--tp", nargs="*", type=float)
    ap.add_argument("--risk", type=float, default=1.0)
    ap.add_argument("--concurrency", choices=["hedge", "single"], default="hedge")
    ap.add_argument("--min-sl-mult", type=float, default=0.0,
                    help="skip signals whose SL is closer than this many spreads (0 = off)")
    ap.add_argument("--htf", type=int, default=0, help="higher-timeframe RSI trend gate, in seconds (0 = off)")
    ap.add_argument("--max-wait", type=int, default=0, help="rsi2_swing only: bars from flag to entry (0 = off)")
    ap.add_argument("--is-frac", type=float, default=0.7)
    ap.add_argument("--data-dir", default=str(ROOT / "data"),
                    help="parquet cache dir; a missing cache triggers a live MT5 fetch of full history")
    ap.add_argument("--out", default=None, help="default results/<strategy>")
    ap.add_argument("--offline", action="store_true", help="embed plotly.js in the html")
    a = ap.parse_args()

    adapter = get_adapter(a.strategy)
    if a.list_axes:
        print(f"{adapter.name} axes:")
        for ax in adapter.axes:
            print(f"  {ax.name:<10} -> columns {list(ax.columns)}  default {adapter.default_axes[ax.name]}")
        print(f"  tp_r       -> default {adapter.default_tp_r}")
        return 0

    axes = dict(parse_axis(t) for t in a.axis)
    grid = GridSpec.for_strategy(adapter, axes=axes or None, tp_r=a.tp)   # raises KeyError on a bad axis
    cfg = load_config(a.config)
    symbol = a.symbol or cfg.symbol
    tfs = a.tf or cfg.timeframes
    sizing = replace(cfg.sizing, risk_pct=a.risk)
    base = build_base(adapter, a.htf, a.max_wait)

    bars_by_tf, spec_by_tf, ranges = {}, {}, {}
    for tf in tfs:
        df, spec = load_or_fetch(symbol, tf, Path(a.data_dir), fallback_spec=cfg.spec_fallback)
        bars = Bars.from_dataframe(df)
        bars_by_tf[tf], spec_by_tf[tf] = bars, spec
        dt = bars.datetimes()
        ranges[tf] = (f"{dt[0]:%Y-%m-%d}", f"{dt[-1]:%Y-%m-%d}")
        print(f"{tf}: {len(bars):,d} bars usable {ranges[tf][0]} -> {ranges[tf][1]}  point={spec.point}")

    t0 = time.time()
    last = {"pct": -1}

    def progress(done: int, total: int) -> None:
        pct = done * 100 // total
        if pct // 5 != last["pct"] // 5:
            last["pct"] = pct
            print(f"  {done}/{total} ({pct}%)  {time.time() - t0:.0f}s", flush=True)

    print(f"{adapter.name}: grid {grid.size()} combos x {len(tfs)} TF")
    grid_df = run_optimization(adapter, bars_by_tf, spec_by_tf, base, grid, cfg.costs, sizing,
                               a.concurrency, is_frac=a.is_frac, progress=progress,
                               min_sl_spread_mult=a.min_sl_mult)
    rec = recommend(grid_df, adapter)

    rec_results = {}
    for tf, r in rec.items():
        if r is None:
            continue
        axis_values = {ax.name: (tuple(r["params"][c] for c in ax.columns) if len(ax.columns) > 1
                                 else r["params"][ax.columns[0]]) for ax in adapter.axes}
        params = adapter.make_params(base, axis_values)
        _, res = run_single(adapter, bars_by_tf[tf], spec_by_tf[tf], params, r["params"]["tp_r"],
                            cfg.costs, sizing, a.concurrency, min_sl_spread_mult=a.min_sl_mult)
        rec_results[tf] = res

    run_info = {"strategy": adapter.name, "symbol": symbol, "timeframes": tfs, "data_range": ranges,
                "initial_equity": sizing.initial_equity, "risk_pct": sizing.risk_pct,
                "concurrency": a.concurrency, "spread_points": cfg.costs.spread_points,
                "commission_per_lot_rt": cfg.costs.commission_per_lot_rt,
                "slippage_points": cfg.costs.slippage_points, "is_frac": a.is_frac,
                "min_sl_mult": a.min_sl_mult, "htf_seconds": a.htf, "max_wait": a.max_wait,
                "grid": {**{k: list(v) for k, v in grid.axes.items()}, "tp_r": list(grid.tp_r)},
                "git_hash": _git_hash(), "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}

    out_root = Path(a.out) if a.out else ROOT / "results" / adapter.name
    out_dir = out_root / datetime.now().strftime("%Y%m%d_%H%M%S")
    write_csvs(out_dir, grid_df, rec_results, run_info)
    write_xlsx(out_dir / f"report_{symbol}.xlsx", grid_df, rec, rec_results, run_info)
    write_html(out_dir / f"report_{symbol}.html", grid_df, rec, rec_results, run_info, offline=a.offline)

    pd.set_option("display.width", 240)
    print("\n=== Recommendation ===")
    n_ruined = int(grid_df["ruined"].sum()) if "ruined" in grid_df.columns else 0
    if n_ruined:
        print(f"note: {n_ruined} of {len(grid_df)} combos blew the account (equity <= 10% of start) and were excluded")
    for tf, r in rec.items():
        if r is None:
            print(f"{tf}: no reliable parameter set")
        else:
            shown = " ".join(f"{k} {v:g}" if isinstance(v, float) else f"{k} {v}"
                             for k, v in r["params"].items() if k != "tf")
            print(f"{tf}: {shown}")
            print(f"     {r['reason']}")
    cols = adapter.full_key_cols() + ["n_trades", "win_rate", "avg_r", "profit_factor", "net_pnl",
                                      "max_dd_pct", "is_avg_r", "oos_avg_r", "robust_r", "ruined", "flags"]
    for tf, g in grid_df.groupby("tf", sort=False):
        print(f"\n--- {tf}: top 5 by IS avg R (then robust_r) ---")
        print(g.sort_values(["is_avg_r", "robust_r"], ascending=False)[cols].head(5).to_string(index=False))
    print(f"\nwritten: {out_dir}  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the CLI tests**

Run: `python -m pytest tests/test_cli.py -q`
Expected: all pass. If `test_optimize_cli_rejects_bad_axis` fails because the `KeyError` traceback exits with a code the test does not expect, wrap the `GridSpec.for_strategy` call in `try/except KeyError as e: ap.error(str(e))` — that is the intended behaviour (argparse exits 2 with the axis name in stderr).

- [ ] **Step 5: `--list-axes` smoke check**

Run: `python scripts/optimize.py --strategy rsi2_ema_swing --list-axes`
Expected: four axis lines (`rsi_fast`, `rsi2`, `ema`, `atr_mult`) with their columns and defaults, plus the `tp_r` line; exit 0.

- [ ] **Step 6: Documentation**

Append to `README.md`:
```markdown
## RSI2 Swing + EMA Trend — `rsi2_ema_swing`

Enter on every confirmed RSI(2) swing whose side agrees with an EMA trend: BUY on a confirmed
swing low while EMA fast > EMA slow, SELL on a confirmed swing high while EMA fast < EMA slow.
SL = swing ∓ ATR×mult, TP = R multiple of that risk. Strategy: `rsi_fvg/strategies/rsi2_ema_swing.py`,
Pine twin: `pine/rsi2_ema_swing_strategy.pine`. Spec: `docs/superpowers/specs/2026-09-08-rsi2-ema-swing-strategy-design.md`.

    python scripts/optimize.py --strategy rsi2_ema_swing --tf M5 M15 H1 --risk 1
    python scripts/optimize.py --strategy rsi2_ema_swing --tf M5 --axis ema=20/100,50/200 --tp 4 8
    python scripts/optimize.py --strategy rsi2_ema_swing --list-axes
    python scripts/optimize.py --strategy rsi2_swing --tf M15 --axis rsi14=80/20 --htf 3600

`scripts/optimize.py` is the generic front end: `--strategy` picks a registered strategy,
`--axis NAME=V1,V2` overrides one grid axis (pairs written `a/b`), and any axis you leave out
keeps that strategy's defaults. Output goes to `results/<strategy>/<timestamp>/` with the same
`grid.csv` / `report_<symbol>.xlsx` / `report_<symbol>.html` set as before.
`scripts/run_rsi2_swing.py` still works and is unchanged.

Default grid for `rsi2_ema_swing`: RSI fast (2, 3, 5) × levels (90/10, 95/5) ×
EMA (20/100, 20/200, 50/200, 10/50) × ATR mult (1, 1.5, 2, 3) × TP (2, 4, 6, 8) = 384 combos per timeframe.

Adding a strategy: write the module, then one `StrategyAdapter` entry in
`rsi_fvg/strategies/registry.py` declaring its axes and the grid columns they expand to. The
optimizer, the reports and both CLIs read the column names from there.
```
In `README.md`'s "Known limits" section add one bullet:
```markdown
- `ema()` leaves the first `period-1` bars NaN (no signals in the EMA warm-up); Pine's `ta.ema` emits values there.
```
In the spec `docs/superpowers/specs/2026-09-08-rsi2-ema-swing-strategy-design.md`, append to §2.1 the sentence: `Python để NaN cho `ema_slow-1` bar đầu (không có tín hiệu trong warm-up); Pine's `ta.ema` có giá trị từ bar 0 — đây là sai lệch duy nhất có chủ ý.`

- [ ] **Step 7: Full suite and commit**

Run: `python -m pytest -q` → all pass (expect roughly 175+ tests).
```bash
git add scripts/optimize.py README.md docs/superpowers/specs/2026-09-08-rsi2-ema-swing-strategy-design.md tests/test_cli.py
git commit -m "feat: generic optimize CLI for any registered strategy; docs"
```

---

## Plan self-review (done at authoring time)

- **Spec coverage.** §1.1 → Tasks 5 (Python) and 6 (Pine); §1.2 → Tasks 2–4 with Task 1 as the behaviour pin; §1.3 → Task 7's CLI (the runs themselves are the controller's, after the plan). §2.1 → Task 5 Steps 3, 6 (RSI/EMA/ATR, warm-up NaN documented in Task 7 Step 6); §2.2 → Task 5 Step 6 (`swing_structure` reused, EMA gate, SL formula, `anchor_bar`/`bars_in_wait`, engine owns `blocked`, prefix-invariance test in Step 4); §2.3 → `Rsi2EmaParams` defaults, run defaults in the CLI (`--risk 1`, `default_tp_r` includes 8); §2.4 → Task 6. §3.1 → Task 2 (`Axis`, `StrategyAdapter`, `key_cols`, single-column robust-axis guard) and Task 5 Step 8 (`rsi2_ema_swing` entry, 384 combos); §3.2 → Task 3 (`GridSpec.axes` + `for_strategy` + `combos`, signals once per axis combo, engine per `tp_r`, generic robustness/flags/recommend, golden regression); §3.3 → Task 4 (generic Grid header, heatmap panels, scatter labels, `_rec_table`) and Task 7 (`optimize.py`, `run_rsi2_swing.py` unchanged). §5 → tests listed per task; the Pine "user compiles it" caveat is stated in Task 6.
- **Placeholder scan.** No "TBD"/"handle edge cases"/"similar to Task N". Task 6 references `pine/rsi2_swing_strategy.pine` by path with exact replacement text rather than restating 300 lines — the file exists in the repo at this commit, so the instruction is concrete.
- **Type consistency.** `StrategyAdapter` members used later all exist in Task 2: `axes`, `key_cols`, `full_key_cols()`, `int_cols`, `robust_cols`, `panel_cols`, `axis()`, `columns_for()`, `make_params()`, `title()`, `run`, `params_cls`, `default_axes`, `default_tp_r`, `robust_axis`. `GridSpec.for_strategy/size/combos/axes/tp_r` (Task 3) match every call in Tasks 4–7 and the tests. `run_optimization`/`run_single`/`add_robustness`/`recommend` take the adapter in the positions the call sites use. `write_csvs` gains its fourth argument in Task 4 and every caller is updated in the same task. `ema` (Task 5 Step 3) is imported by the strategy in Step 6. `Rsi2EmaParams` field names match the adapter's `params` tuples exactly (`fast_hi`/`fast_lo`, `ema_fast`/`ema_slow`, `atr_mult`, `rsi_fast`).
- **Ordering risk noted.** Task 3 changes `run_optimization`'s signature, so Task 3 Step 5 updates every in-repo caller in the same commit; the golden test's `build_grid_df` is edited there too, while its CSV is explicitly frozen.
