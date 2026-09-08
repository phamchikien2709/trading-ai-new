# RSI-FVG Pullback — Phase 1: Python Core + Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared strategy core (`rsi_fvg/`) and an event-driven backtester that runs the 3 entry variants × 5 TP levels × 3 timeframes grid on XAUUSDc data pulled from MT5, producing `results/<ts>/summary.csv|md`, trade logs, and charts.

**Architecture:** `strategy.run_strategy(bars, params, variant)` is a pure function that turns OHLC arrays into `list[Signal]` via two independent per-direction state machines; it knows nothing about positions or money. `backtest.engine.run_backtest` consumes those signals bar-by-bar, fills at next open with spread/slippage, manages ≤1 position per direction, and emits a trade log + equity curve. `runner` loops the grid and `report` writes CSV/MD/PNG. Data comes from `data.mt5_loader` (parquet cache + JSON symbol-spec sidecar).

**Tech Stack:** Python 3.13, numpy 2.2, pandas 2.3, pyarrow, MetaTrader5 5.0.5370, matplotlib 3.10, pyyaml, pytest 9. No external backtest library.

**Spec:** `docs/superpowers/specs/2026-09-08-rsi-fvg-pullback-strategy-design.md` — sections 2 (logic), 3 (Python architecture), 6.1 (unit tests) are implemented here. Sections 4 (live), 5 (Pine), 6.2–6.3 (integration/parity) are **Phase 2**, planned after this phase ships so the EA/Pine ports copy a finalized `strategy.py`.

## Global Constraints

- Python 3.13 (`python` on PATH resolves to 3.13.4). Run everything from repo root `C:\Users\MeoMeo\Desktop\AI BOT TRADING NEW FLOW`.
- All numeric indicator code uses Wilder smoothing exactly as spec §2.1: RSI seeded with SMA of the first `period` gains/losses; ATR seeded with SMA of the first `period` TR values, then `rma[i] = (rma[i-1]*(period-1) + x[i]) / period`.
- Pivot definition is **strict** `>` (high) / `<` (low) on both sides, confirmed `pivot_len` bars later. Phase 2 ports must implement the same loop rather than call `ta.pivothigh`.
- Signals are computed at bar close `t`; fills happen at `open[t+1]`. Candles are **bid** prices; buy fills/exits at `bid + spread`, sell fills/exits at bid; buy SL/TP trigger on bid, sell SL/TP trigger on ask = `bid + spread`.
- Same-bar SL and TP hit → **SL wins**.
- The state machine never inspects positions. `blocked`, `rejected_invalid_sl`, `rejected_stops_level` are engine/bot decisions.
- Entry trigger is evaluated only when `t > wait_start` (not on the bar that entered WAIT). Event priority inside WAIT: re-cross → expiry → trigger.
- Symbol/broker facts discovered 2026-09-08: symbol **`XAUUSDc`**, `point=0.001`, `digits=3`, `contract_size=1.0`, `min_lot=0.01`, `lot_step=0.01`, `max_lot=200`, `stops_level=0`, spread ≈ 260 points, account margin mode = hedging. **The logged-in MT5 account is a REAL Exness cent account (server `Exness-MT5Real25`), not demo.** Phase 1 only reads data; never send orders in this phase.
- Config file: `config/default.yaml`. Any numeric default lives there, not in code (code dataclass defaults are the same values as a fallback).
- Commit after every task with a conventional-commit message. Git identity for commits: `git -c user.name="MeoMeo" -c user.email="kienpham@cungbai.vn" commit ...` (or set once with `git config user.name/user.email`).
- Tests: `python -m pytest -q` from repo root. `tests/conftest.py` adds repo root to `sys.path`.

---

## File Structure (Phase 1)

| Path | Responsibility |
|---|---|
| `requirements.txt` | pinned-ish deps |
| `config/default.yaml` | symbol, timeframes, strategy/costs/sizing params, variants, tp grid, spec fallback |
| `rsi_fvg/__init__.py` | package marker, `__version__` |
| `rsi_fvg/params.py` | `StrategyParams`, `CostParams`, `SizingParams`, `SymbolSpec`, `Config`, `load_config(path)` |
| `rsi_fvg/bars.py` | `Bars` container (numpy arrays) + `Bars.from_dataframe` |
| `rsi_fvg/indicators.py` | `rsi_wilder`, `atr_wilder`, `candle_color`, `pivot_high`, `pivot_low` |
| `rsi_fvg/fvg.py` | `FvgArrays`, `detect_fvg` |
| `rsi_fvg/strategy.py` | `Direction`, `Variant`, `State`, `Signal`, `run_direction`, `run_strategy` |
| `rsi_fvg/sizing.py` | `lots_for_risk` |
| `rsi_fvg/backtest/__init__.py` | empty |
| `rsi_fvg/backtest/engine.py` | `Position`, `BacktestResult`, `run_backtest` |
| `rsi_fvg/backtest/metrics.py` | `compute_metrics`, `max_drawdown` |
| `rsi_fvg/backtest/runner.py` | `run_grid` (TF × variant × TP, IS/OOS split) |
| `rsi_fvg/backtest/report.py` | `write_report` (summary.csv/md, trades csv, equity png, heatmap png) |
| `rsi_fvg/data/__init__.py` | empty |
| `rsi_fvg/data/mt5_loader.py` | `fetch_rates`, `fetch_symbol_spec`, `load_or_fetch` (parquet + json sidecar) |
| `rsi_fvg/data/csv_loader.py` | `load_csv` fallback |
| `scripts/fetch_data.py` | CLI wrapper around `load_or_fetch` |
| `scripts/run_backtest.py` | CLI wrapper around `run_grid` + `write_report` |
| `tests/conftest.py` | `make_bars` helper, sys.path |
| `tests/test_*.py` | one per module |
| `README.md` | install, fetch, backtest, known limits |

---

### Task 1: Project scaffold, params, config

**Files:**
- Create: `requirements.txt`, `rsi_fvg/__init__.py`, `rsi_fvg/params.py`, `rsi_fvg/bars.py`, `config/default.yaml`, `tests/conftest.py`, `tests/test_params.py`, `tests/test_bars.py`

**Interfaces:**
- Produces:
  - `StrategyParams(rsi_period=14, atr_period=14, overbought=75.0, oversold=25.0, mid_high=60.0, mid_low=40.0, atr_mult=1.0, pivot_len=2, max_wait_bars=0)` frozen dataclass
  - `CostParams(spread_points=260.0, commission_per_lot_rt=0.0, slippage_points=10.0)` frozen dataclass
  - `SizingParams(risk_pct=1.0, initial_equity=10_000.0)` frozen dataclass
  - `SymbolSpec(name="XAUUSDc", point=0.001, digits=3, contract_size=1.0, min_lot=0.01, max_lot=200.0, lot_step=0.01, stops_level_points=0)` frozen dataclass with `.to_dict()` / `SymbolSpec.from_dict(d)`
  - `Config(symbol: str, timeframes: list[str], strategy: StrategyParams, costs: CostParams, sizing: SizingParams, spec_fallback: SymbolSpec, variants: list[str], tp_r: list[float], concurrency: str, oos_frac: float)`; `load_config(path: str | Path) -> Config`
  - `Bars(time: np.ndarray[int64], open, high, low, close: np.ndarray[float64], spread: np.ndarray[int64] | None)` with `__len__`, `Bars.from_dataframe(df)` (expects columns `time` (int seconds or datetime64), `open, high, low, close`, optional `spread`), `Bars.slice(start, stop)`.

- [ ] **Step 1: Write requirements.txt and package init**

`requirements.txt`:
```
numpy>=2.0
pandas>=2.2
pyarrow>=15
MetaTrader5>=5.0.45
matplotlib>=3.8
pyyaml>=6.0
pytest>=8.0
```

`rsi_fvg/__init__.py`:
```python
"""RSI-FVG pullback strategy: shared core, backtest, live."""
__version__ = "0.1.0"
```

- [ ] **Step 2: Write tests/conftest.py with the synthetic-bars helper**

```python
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rsi_fvg.bars import Bars  # noqa: E402


def make_bars(open_, high, low, close, start=1_700_000_000, step=300, spread=None):
    """Build Bars from python lists. step = seconds per bar (300 = M5)."""
    n = len(close)
    assert len(open_) == len(high) == len(low) == n
    time = np.arange(start, start + step * n, step, dtype=np.int64)
    return Bars(
        time=time,
        open=np.asarray(open_, dtype=np.float64),
        high=np.asarray(high, dtype=np.float64),
        low=np.asarray(low, dtype=np.float64),
        close=np.asarray(close, dtype=np.float64),
        spread=None if spread is None else np.asarray(spread, dtype=np.int64),
    )


def bars_from_closes(closes, wick=0.5, start=1_700_000_000, step=300):
    """Bars where open = previous close, high/low = body ± wick."""
    closes = list(map(float, closes))
    opens = [closes[0]] + closes[:-1]
    highs = [max(o, c) + wick for o, c in zip(opens, closes)]
    lows = [min(o, c) - wick for o, c in zip(opens, closes)]
    return make_bars(opens, highs, lows, closes, start=start, step=step)


@pytest.fixture
def mk_bars():
    return make_bars


@pytest.fixture
def mk_closes():
    return bars_from_closes
```

- [ ] **Step 3: Write failing tests for params and bars**

`tests/test_params.py`:
```python
from pathlib import Path

from rsi_fvg.params import (Config, CostParams, SizingParams, StrategyParams,
                            SymbolSpec, load_config)

ROOT = Path(__file__).resolve().parents[1]


def test_defaults_match_spec():
    p = StrategyParams()
    assert (p.rsi_period, p.atr_period) == (14, 14)
    assert (p.overbought, p.oversold, p.mid_high, p.mid_low) == (75.0, 25.0, 60.0, 40.0)
    assert p.atr_mult == 1.0 and p.pivot_len == 2 and p.max_wait_bars == 0
    assert SizingParams().risk_pct == 1.0
    assert SizingParams().initial_equity == 10_000.0


def test_symbol_spec_roundtrip():
    s = SymbolSpec(name="XAUUSDc", point=0.001, digits=3, contract_size=1.0,
                   min_lot=0.01, max_lot=200.0, lot_step=0.01, stops_level_points=0)
    assert SymbolSpec.from_dict(s.to_dict()) == s


def test_load_default_yaml():
    cfg = load_config(ROOT / "config" / "default.yaml")
    assert isinstance(cfg, Config)
    assert cfg.symbol == "XAUUSDc"
    assert cfg.timeframes == ["M5", "M15", "H1"]
    assert cfg.variants == ["A", "B", "C"]
    assert cfg.tp_r == [1.0, 1.5, 2.0, 3.0, 4.0]
    assert cfg.concurrency == "hedge"
    assert cfg.oos_frac == 0.2
    assert isinstance(cfg.strategy, StrategyParams)
    assert isinstance(cfg.costs, CostParams)
    assert cfg.spec_fallback.point == 0.001
```

`tests/test_bars.py`:
```python
import numpy as np
import pandas as pd

from rsi_fvg.bars import Bars


def test_from_dataframe_with_epoch_seconds():
    df = pd.DataFrame({"time": [0, 300, 600], "open": [1, 2, 3.0], "high": [2, 3, 4.0],
                       "low": [0, 1, 2.0], "close": [1.5, 2.5, 3.5], "spread": [10, 11, 12]})
    b = Bars.from_dataframe(df)
    assert len(b) == 3
    assert b.time.dtype == np.int64 and b.time[1] == 300
    assert b.close.dtype == np.float64
    assert b.spread is not None and b.spread[2] == 12


def test_from_dataframe_with_datetime():
    df = pd.DataFrame({"time": pd.to_datetime([0, 300], unit="s", utc=True),
                       "open": [1, 2.0], "high": [2, 3.0], "low": [0, 1.0], "close": [1, 2.0]})
    b = Bars.from_dataframe(df)
    assert list(b.time) == [0, 300]
    assert b.spread is None


def test_slice(mk_closes):
    b = mk_closes([1, 2, 3, 4, 5])
    s = b.slice(1, 3)
    assert len(s) == 2 and list(s.close) == [2.0, 3.0]
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_params.py tests/test_bars.py -q`
Expected: errors — `ModuleNotFoundError: No module named 'rsi_fvg.params'` / `'rsi_fvg.bars'`.

- [ ] **Step 5: Write rsi_fvg/bars.py**

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Bars:
    """OHLC arrays. Prices are BID. time = epoch seconds (int64)."""

    time: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    spread: np.ndarray | None = None

    def __len__(self) -> int:
        return int(self.close.shape[0])

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "Bars":
        t = df["time"]
        if pd.api.types.is_datetime64_any_dtype(t):
            time = (t.astype("int64") // 1_000_000_000).to_numpy(dtype=np.int64)
        else:
            time = t.to_numpy(dtype=np.int64)
        spread = df["spread"].to_numpy(dtype=np.int64) if "spread" in df.columns else None
        return cls(
            time=time,
            open=df["open"].to_numpy(dtype=np.float64),
            high=df["high"].to_numpy(dtype=np.float64),
            low=df["low"].to_numpy(dtype=np.float64),
            close=df["close"].to_numpy(dtype=np.float64),
            spread=spread,
        )

    def slice(self, start: int, stop: int) -> "Bars":
        return Bars(
            time=self.time[start:stop],
            open=self.open[start:stop],
            high=self.high[start:stop],
            low=self.low[start:stop],
            close=self.close[start:stop],
            spread=None if self.spread is None else self.spread[start:stop],
        )

    def datetimes(self) -> pd.DatetimeIndex:
        return pd.to_datetime(self.time, unit="s", utc=True)
```

- [ ] **Step 6: Write rsi_fvg/params.py**

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class StrategyParams:
    rsi_period: int = 14
    atr_period: int = 14
    overbought: float = 75.0
    oversold: float = 25.0
    mid_high: float = 60.0
    mid_low: float = 40.0
    atr_mult: float = 1.0
    pivot_len: int = 2
    max_wait_bars: int = 0  # 0 = disabled


@dataclass(frozen=True)
class CostParams:
    spread_points: float = 260.0
    commission_per_lot_rt: float = 0.0
    slippage_points: float = 10.0


@dataclass(frozen=True)
class SizingParams:
    risk_pct: float = 1.0
    initial_equity: float = 10_000.0


@dataclass(frozen=True)
class SymbolSpec:
    name: str = "XAUUSDc"
    point: float = 0.001
    digits: int = 3
    contract_size: float = 1.0
    min_lot: float = 0.01
    max_lot: float = 200.0
    lot_step: float = 0.01
    stops_level_points: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SymbolSpec":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class Config:
    symbol: str
    timeframes: list[str]
    strategy: StrategyParams
    costs: CostParams
    sizing: SizingParams
    spec_fallback: SymbolSpec
    variants: list[str] = field(default_factory=lambda: ["A", "B", "C"])
    tp_r: list[float] = field(default_factory=lambda: [1.0, 1.5, 2.0, 3.0, 4.0])
    concurrency: str = "hedge"  # hedge | single
    oos_frac: float = 0.2


def load_config(path: str | Path) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    engine = raw.get("engine", {})
    return Config(
        symbol=raw["symbol"],
        timeframes=list(raw["timeframes"]),
        strategy=StrategyParams(**raw.get("strategy", {})),
        costs=CostParams(**raw.get("costs", {})),
        sizing=SizingParams(**raw.get("sizing", {})),
        spec_fallback=SymbolSpec.from_dict({"name": raw["symbol"], **raw.get("symbol_spec_fallback", {})}),
        variants=[str(v) for v in raw.get("variants", ["A", "B", "C"])],
        tp_r=[float(x) for x in raw.get("tp_r", [1, 1.5, 2, 3, 4])],
        concurrency=engine.get("concurrency", "hedge"),
        oos_frac=float(engine.get("oos_frac", 0.2)),
    )
```

- [ ] **Step 7: Write config/default.yaml**

```yaml
# RSI-FVG pullback — default config (Exness cent account, XAUUSDc)
symbol: XAUUSDc
timeframes: [M5, M15, H1]

strategy:
  rsi_period: 14
  atr_period: 14
  overbought: 75
  oversold: 25
  mid_high: 60
  mid_low: 40
  atr_mult: 1.0
  pivot_len: 2
  max_wait_bars: 0        # 0 = flag never expires (spec default)

costs:
  spread_points: 260      # XAUUSDc point=0.001 -> 260 pts = $0.26/oz (observed 2026-09-08)
  commission_per_lot_rt: 0.0   # Exness Standard Cent: no commission. Set per broker.
  slippage_points: 10     # $0.01/oz, applied adversely on entry and SL exit

sizing:
  risk_pct: 1.0
  initial_equity: 10000

engine:
  concurrency: hedge      # hedge | single  (single = compare with Pine)
  oos_frac: 0.2           # last 20% of bars = out-of-sample

variants: [A, B, C]
tp_r: [1, 1.5, 2, 3, 4]

# Used only when data/<symbol>_<tf>.spec.json is missing
symbol_spec_fallback:
  point: 0.001
  digits: 3
  contract_size: 1.0
  min_lot: 0.01
  max_lot: 200
  lot_step: 0.01
  stops_level_points: 0
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/test_params.py tests/test_bars.py -q`
Expected: `6 passed`.

- [ ] **Step 9: Commit**

```bash
git add requirements.txt config rsi_fvg/__init__.py rsi_fvg/params.py rsi_fvg/bars.py tests/conftest.py tests/test_params.py tests/test_bars.py
git commit -m "feat: project scaffold, params dataclasses, config, Bars container"
```

---

### Task 2: Indicators (RSI/ATR Wilder, candle color, pivots)

**Files:**
- Create: `rsi_fvg/indicators.py`, `tests/test_indicators.py`

**Interfaces:**
- Produces:
  - `rsi_wilder(close: np.ndarray, period: int) -> np.ndarray` — NaN for indices `< period`, values in `[0, 100]`.
  - `atr_wilder(high, low, close: np.ndarray, period: int) -> np.ndarray` — NaN for indices `< period - 1`.
  - `true_range(high, low, close) -> np.ndarray` — `tr[0] = high[0]-low[0]`.
  - `candle_color(open_, close) -> np.ndarray[int8]` — `1` green, `-1` red, `0` doji.
  - `pivot_high(high: np.ndarray, left: int, right: int) -> np.ndarray[bool]` — `True` at pivot index `i` (strict `>` both sides). Caller adds `right` to get the confirmation bar.
  - `pivot_low(low, left, right) -> np.ndarray[bool]` — mirror with strict `<`.

- [ ] **Step 1: Write failing tests**

`tests/test_indicators.py`:
```python
import numpy as np
import pytest

from rsi_fvg.indicators import (atr_wilder, candle_color, pivot_high, pivot_low,
                                rsi_wilder, true_range)


def _ref_rsi(close, period):
    """Straightforward reference: SMA seed then Wilder smoothing."""
    close = np.asarray(close, float)
    n = len(close)
    out = np.full(n, np.nan)
    d = np.diff(close)
    gains = np.where(d > 0, d, 0.0)
    losses = np.where(d < 0, -d, 0.0)
    ag = gains[:period].mean()
    al = losses[:period].mean()
    out[period] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(period + 1, n):
        ag = (ag * (period - 1) + gains[i - 1]) / period
        al = (al * (period - 1) + losses[i - 1]) / period
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def test_rsi_matches_reference_and_nan_prefix():
    rng = np.random.default_rng(0)
    close = 2000 + np.cumsum(rng.normal(0, 1, 200))
    got = rsi_wilder(close, 14)
    ref = _ref_rsi(close, 14)
    assert np.all(np.isnan(got[:14]))
    np.testing.assert_allclose(got[14:], ref[14:], atol=1e-9)
    assert np.nanmin(got) >= 0 and np.nanmax(got) <= 100


def test_rsi_all_up_is_100_all_down_is_0():
    up = np.arange(1, 40, dtype=float)
    assert rsi_wilder(up, 14)[-1] == pytest.approx(100.0)
    down = np.arange(40, 1, -1, dtype=float)
    assert rsi_wilder(down, 14)[-1] == pytest.approx(0.0)


def test_true_range_first_bar_and_gap():
    h = np.array([10, 12, 20.0]); l = np.array([9, 11, 19.0]); c = np.array([9.5, 11.5, 19.5])
    tr = true_range(h, l, c)
    assert tr[0] == 1.0
    assert tr[1] == pytest.approx(max(12 - 11, abs(12 - 9.5), abs(11 - 9.5)))  # 2.5
    assert tr[2] == pytest.approx(max(1.0, abs(20 - 11.5), abs(19 - 11.5)))   # 8.5


def test_atr_wilder_seed_and_smoothing():
    n = 30
    h = np.full(n, 11.0); l = np.full(n, 10.0); c = np.full(n, 10.5)
    h[20] = 15.0  # one spike -> TR jumps
    atr = atr_wilder(h, l, c, 14)
    assert np.all(np.isnan(atr[:13])) and not np.isnan(atr[13])
    assert atr[13] == pytest.approx(1.0)
    tr20 = max(15 - 10, abs(15 - 10.5), abs(10 - 10.5))  # 5.0 (prev close 10.5)
    expected20 = (atr[19] * 13 + tr20) / 14
    assert atr[20] == pytest.approx(expected20)
    assert atr[21] == pytest.approx((atr[20] * 13 + 1.0) / 14)


def test_candle_color():
    o = np.array([1.0, 2.0, 3.0]); c = np.array([2.0, 1.0, 3.0])
    np.testing.assert_array_equal(candle_color(o, c), np.array([1, -1, 0], dtype=np.int8))


def test_pivot_high_strict_and_edges():
    high = np.array([1, 2, 5, 2, 1, 5, 5, 1, 9.0])
    ph = pivot_high(high, 2, 2)
    assert ph[2]  # 5 > [1,2] and > [2,1]
    assert not ph[5] and not ph[6]  # equal highs are not strict pivots
    assert not ph[8]  # not enough bars on the right
    assert ph.dtype == bool and len(ph) == len(high)


def test_pivot_low_mirror():
    low = np.array([5, 4, 1, 4, 5, 1, 1, 5.0])
    pl = pivot_low(low, 2, 2)
    assert pl[2] and not pl[5] and not pl[6]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_indicators.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.indicators'`.

- [ ] **Step 3: Write rsi_fvg/indicators.py**

```python
"""Vectorised/loop indicators with Wilder smoothing. All inputs float64 numpy arrays."""
from __future__ import annotations

import numpy as np


def _rma(x: np.ndarray, period: int, first_valid: int) -> np.ndarray:
    """Wilder RMA seeded with SMA of x[first_valid : first_valid+period]."""
    n = x.shape[0]
    out = np.full(n, np.nan)
    seed_end = first_valid + period
    if seed_end > n:
        return out
    out[seed_end - 1] = np.mean(x[first_valid:seed_end])
    alpha_prev = (period - 1) / period
    for i in range(seed_end, n):
        out[i] = out[i - 1] * alpha_prev + x[i] / period
    return out


def rsi_wilder(close: np.ndarray, period: int) -> np.ndarray:
    close = np.asarray(close, dtype=np.float64)
    n = close.shape[0]
    delta = np.empty(n)
    delta[0] = 0.0
    delta[1:] = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    # deltas start at index 1 -> seed over indices 1..period, first RSI at index `period`
    avg_gain = _rma(gain, period, first_valid=1)
    avg_loss = _rma(loss, period, first_valid=1)
    out = np.full(n, np.nan)
    valid = ~np.isnan(avg_gain)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = np.where(avg_loss == 0, 100.0, rsi)
    out[valid] = rsi[valid]
    return out


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    high = np.asarray(high, float); low = np.asarray(low, float); close = np.asarray(close, float)
    tr = high - low
    if tr.shape[0] > 1:
        prev_close = close[:-1]
        tr[1:] = np.maximum(tr[1:], np.maximum(np.abs(high[1:] - prev_close), np.abs(low[1:] - prev_close)))
    return tr


def atr_wilder(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    return _rma(true_range(high, low, close), period, first_valid=0)


def candle_color(open_: np.ndarray, close: np.ndarray) -> np.ndarray:
    return np.sign(np.asarray(close, float) - np.asarray(open_, float)).astype(np.int8)


def pivot_high(high: np.ndarray, left: int, right: int) -> np.ndarray:
    high = np.asarray(high, float)
    n = high.shape[0]
    out = np.zeros(n, dtype=bool)
    for i in range(left, n - right):
        v = high[i]
        if np.all(high[i - left:i] < v) and np.all(high[i + 1:i + 1 + right] < v):
            out[i] = True
    return out


def pivot_low(low: np.ndarray, left: int, right: int) -> np.ndarray:
    low = np.asarray(low, float)
    n = low.shape[0]
    out = np.zeros(n, dtype=bool)
    for i in range(left, n - right):
        v = low[i]
        if np.all(low[i - left:i] > v) and np.all(low[i + 1:i + 1 + right] > v):
            out[i] = True
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_indicators.py -q`
Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/indicators.py tests/test_indicators.py
git commit -m "feat: Wilder RSI/ATR, candle color, strict pivots"
```

---

### Task 3: FVG detection

**Files:**
- Create: `rsi_fvg/fvg.py`, `tests/test_fvg.py`

**Interfaces:**
- Consumes: `candle_color` from `rsi_fvg.indicators`.
- Produces:
  - `FvgArrays(bull: np.ndarray[bool], bear: np.ndarray[bool], lo: np.ndarray[float], hi: np.ndarray[float])` — `lo/hi` hold the zone at index `t` where a FVG is flagged, NaN elsewhere.
  - `detect_fvg(open_, high, low, close) -> FvgArrays` — index `t` is the third candle (C3). Bull: `color[t-2]==color[t-1]==color[t]==1 and high[t-2] < low[t]`, zone `[high[t-2], low[t]]`. Bear: all `-1` and `low[t-2] > high[t]`, zone `[high[t], low[t-2]]`.

- [ ] **Step 1: Write failing tests**

`tests/test_fvg.py`:
```python
import numpy as np

from rsi_fvg.fvg import detect_fvg


def _fvg(o, h, l, c):
    return detect_fvg(np.array(o, float), np.array(h, float), np.array(l, float), np.array(c, float))


def test_bull_fvg_three_green_with_gap():
    # C1: 10->11 (h 11.2), C2: 11->13, C3: 13->14 (low 13.0 > 11.2)
    f = _fvg(o=[10, 11, 13], h=[11.2, 13.1, 14.2], l=[9.9, 10.9, 13.0], c=[11, 13, 14])
    assert list(f.bull) == [False, False, True]
    assert not f.bear.any()
    assert (f.lo[2], f.hi[2]) == (11.2, 13.0)
    assert np.isnan(f.lo[0]) and np.isnan(f.lo[1])


def test_three_green_without_gap_is_not_fvg():
    f = _fvg(o=[10, 11, 13], h=[11.2, 13.1, 14.2], l=[9.9, 10.9, 11.0], c=[11, 13, 14])  # low C3 11.0 < high C1 11.2
    assert not f.bull.any()


def test_doji_breaks_streak():
    f = _fvg(o=[10, 11, 13], h=[11.2, 13.1, 14.2], l=[9.9, 10.9, 13.0], c=[11, 11, 14])  # C2 doji
    assert not f.bull.any()


def test_mixed_color_with_gap_is_not_fvg():
    f = _fvg(o=[10, 11, 13], h=[11.2, 13.1, 14.2], l=[9.9, 10.9, 13.0], c=[11, 10.95, 14])  # C2 red
    assert not f.bull.any()


def test_bear_fvg_mirror():
    # C1: 14->13 (low 12.8), C2: 13->11, C3: 11->10 (high 10.9 < 12.8)
    f = _fvg(o=[14, 13, 11], h=[14.1, 13.1, 10.9], l=[12.8, 10.9, 9.8], c=[13, 11, 10])
    assert list(f.bear) == [False, False, True]
    assert not f.bull.any()
    assert (f.lo[2], f.hi[2]) == (10.9, 12.8)


def test_short_series_no_crash():
    f = _fvg(o=[1, 2], h=[2, 3], l=[0, 1], c=[2, 3])
    assert len(f.bull) == 2 and not f.bull.any()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fvg.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.fvg'`.

- [ ] **Step 3: Write rsi_fvg/fvg.py**

```python
"""Fair Value Gap on 3 consecutive same-colour candles (spec §2.2)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .indicators import candle_color


@dataclass
class FvgArrays:
    bull: np.ndarray  # bool, True at C3 index
    bear: np.ndarray  # bool
    lo: np.ndarray    # zone low at C3 index, NaN elsewhere
    hi: np.ndarray    # zone high


def detect_fvg(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> FvgArrays:
    n = close.shape[0]
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    lo = np.full(n, np.nan)
    hi = np.full(n, np.nan)
    if n < 3:
        return FvgArrays(bull, bear, lo, hi)
    color = candle_color(open_, close)
    c1, c2, c3 = color[:-2], color[1:-1], color[2:]
    all_green = (c1 == 1) & (c2 == 1) & (c3 == 1)
    all_red = (c1 == -1) & (c2 == -1) & (c3 == -1)
    gap_up = high[:-2] < low[2:]
    gap_down = low[:-2] > high[2:]
    bull[2:] = all_green & gap_up
    bear[2:] = all_red & gap_down
    idx_b = np.flatnonzero(bull)
    lo[idx_b] = high[idx_b - 2]
    hi[idx_b] = low[idx_b]
    idx_s = np.flatnonzero(bear)
    lo[idx_s] = high[idx_s]
    hi[idx_s] = low[idx_s - 2]
    return FvgArrays(bull, bear, lo, hi)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_fvg.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/fvg.py tests/test_fvg.py
git commit -m "feat: FVG detection on 3 same-colour candles"
```

---

### Task 4: Strategy core — state machine and signals

**Files:**
- Create: `rsi_fvg/strategy.py`, `tests/test_strategy.py`

**Interfaces:**
- Consumes: `Bars`, `StrategyParams`, `rsi_wilder`, `atr_wilder`, `pivot_high`, `pivot_low`, `detect_fvg`, `FvgArrays`.
- Produces:
  - `class Direction(IntEnum): BUY = 1; SELL = -1`
  - `class Variant(str, Enum): A = "A"; B = "B"; C = "C"`
  - `class State(IntEnum): IDLE = 0; ARMED = 1; WAIT = 2`
  - `Signal(direction: Direction, variant: Variant, signal_bar: int, anchor_bar: int, ref_price: float, sl_price: float, bars_in_wait: int, fvg_zone: tuple[float, float] | None, pivot_price: float | None)` frozen dataclass
  - `Indicators(rsi, atr: np.ndarray, fvg: FvgArrays, piv_high, piv_low: np.ndarray[bool])`
  - `compute_indicators(bars: Bars, params: StrategyParams) -> Indicators`
  - `run_direction(direction, bars, ind, params, variant) -> list[Signal]`
  - `run_strategy(bars, params, variant, directions=(Direction.BUY, Direction.SELL)) -> list[Signal]` sorted by `(signal_bar, direction)`.

- [ ] **Step 1: Write failing tests**

`tests/test_strategy.py`:
```python
import numpy as np
import pytest

from rsi_fvg.fvg import FvgArrays
from rsi_fvg.indicators import pivot_high, pivot_low
from rsi_fvg.params import StrategyParams
from rsi_fvg.strategy import (Direction, Indicators, Signal, Variant, compute_indicators,
                              run_direction, run_strategy)

P = StrategyParams()  # 75/25/60/40, atr_mult 1, pivot_len 2


def mk_ind(bars, rsi, atr=1.0, fvg_bull=(), fvg_bear=()):
    n = len(bars)
    rsi = np.asarray(rsi, float)
    assert len(rsi) == n
    fvg = FvgArrays(np.zeros(n, bool), np.zeros(n, bool), np.full(n, np.nan), np.full(n, np.nan))
    for t in fvg_bull:
        fvg.bull[t] = True; fvg.lo[t] = bars.high[t - 2]; fvg.hi[t] = bars.low[t]
    for t in fvg_bear:
        fvg.bear[t] = True; fvg.lo[t] = bars.high[t]; fvg.hi[t] = bars.low[t - 2]
    return Indicators(rsi=rsi, atr=np.full(n, float(atr)), fvg=fvg,
                      piv_high=pivot_high(bars.high, P.pivot_len, P.pivot_len),
                      piv_low=pivot_low(bars.low, P.pivot_len, P.pivot_len))


def test_buy_variant_b_basic(mk_closes):
    #        t: 0   1   2   3   4   5
    bars = mk_closes([100, 101, 99, 98, 99, 100])
    rsi =        [70, 80, 55, 50, 58, 65]   # cross@1, wait@2, reclaim@5
    sigs = run_direction(Direction.BUY, bars, mk_ind(bars, rsi), P, Variant.B)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == Direction.BUY and s.variant == Variant.B
    assert s.signal_bar == 5 and s.anchor_bar == 1 and s.bars_in_wait == 3
    assert s.ref_price == 100.0
    assert s.sl_price == pytest.approx(bars.low[1:6].min() - 1.0)
    assert s.fvg_zone is None and s.pivot_price is None


def test_no_cross_no_signal(mk_closes):
    bars = mk_closes([100, 101, 102, 103, 104])
    assert run_direction(Direction.BUY, bars, mk_ind(bars, [50, 60, 70, 74, 74.9]), P, Variant.B) == []


def test_one_cross_one_signal(mk_closes):
    bars = mk_closes([100, 101, 99, 100, 99, 100])
    rsi =        [70, 80, 55, 65, 55, 65]   # reclaim @3 and again @5, no new cross
    sigs = run_direction(Direction.BUY, bars, mk_ind(bars, rsi), P, Variant.B)
    assert [s.signal_bar for s in sigs] == [3]


def test_recross_resets_anchor_and_flag(mk_closes):
    #        t: 0    1    2   3   4    5   6   7
    bars = mk_closes([100, 101, 95, 94, 102, 101, 100, 101])
    rsi =        [70,  80,  55, 50, 80,  70, 55, 65]  # cross@1, wait@2, RE-cross@4, wait@6, reclaim@7
    sigs = run_direction(Direction.BUY, bars, mk_ind(bars, rsi), P, Variant.B)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.anchor_bar == 4 and s.signal_bar == 7 and s.bars_in_wait == 1
    assert s.sl_price == pytest.approx(bars.low[4:8].min() - 1.0)  # ignores the 94 low before re-cross


def test_trigger_not_evaluated_on_wait_entry_bar(mk_closes):
    bars = mk_closes([100, 101, 102, 103, 104, 105])
    rsi =        [70, 80, 78, 55, 56, 57]  # wait@3
    ind = mk_ind(bars, rsi, fvg_bull=(3,))  # FVG on the same bar the flag turns on
    assert run_direction(Direction.BUY, bars, ind, P, Variant.A) == []
    ind2 = mk_ind(bars, rsi, fvg_bull=(4,))
    sigs = run_direction(Direction.BUY, bars, ind2, P, Variant.A)
    assert [s.signal_bar for s in sigs] == [4]
    assert sigs[0].fvg_zone == (bars.high[2], bars.low[4])


def test_max_wait_bars_expiry_has_priority_over_trigger(mk_closes):
    bars = mk_closes([100, 101, 99, 98, 97, 100])
    rsi =        [70, 80, 55, 50, 50, 65]   # wait@2; reclaim @5 -> 5-2=3 > 2 -> expired first
    p = StrategyParams(max_wait_bars=2)
    assert run_direction(Direction.BUY, bars, mk_ind(bars, rsi), p, Variant.B) == []
    p3 = StrategyParams(max_wait_bars=3)
    assert len(run_direction(Direction.BUY, bars, mk_ind(bars, rsi), p3, Variant.B)) == 1


def test_variant_c_pivot_break_and_no_pivot(mk_bars):
    o = [100, 101, 103, 104, 103, 102, 101, 102, 105]
    h = [101, 103, 105, 104.5, 103.5, 102.5, 101.5, 103, 106]   # pivot high at t=2 (105), confirmed t=4
    l = [99, 100, 102, 103, 102, 101, 100, 101, 104]
    c = [101, 103, 104, 103, 102, 101, 102, 103, 105.5]
    bars = mk_bars(o, h, l, c)
    rsi = [70, 80, 82, 78, 70, 55, 50, 58, 62]   # cross@1 (anchor 1), wait@5
    sigs = run_direction(Direction.BUY, bars, mk_ind(bars, rsi), P, Variant.C)
    assert [s.signal_bar for s in sigs] == [8]      # close 105.5 > pivot 105
    assert sigs[0].pivot_price == 105.0
    # same RSI path but pivot formed BEFORE anchor -> ignored
    rsi2 = [70, 74, 74, 74, 80, 55, 50, 58, 62]     # cross@4 -> pivot at t=2 < anchor
    assert run_direction(Direction.BUY, bars, mk_ind(bars, rsi2), P, Variant.C) == []


def test_sell_mirror_variant_b(mk_closes):
    bars = mk_closes([100, 99, 101, 102, 101, 100])
    rsi =        [30, 20, 45, 50, 42, 38]   # cross down@1, wait@2 (rsi>40), reclaim down @5
    sigs = run_direction(Direction.SELL, bars, mk_ind(bars, rsi), P, Variant.B)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == Direction.SELL and s.anchor_bar == 1 and s.signal_bar == 5
    assert s.sl_price == pytest.approx(bars.high[1:6].max() + 1.0)


def test_nan_rsi_prefix_is_skipped(mk_closes):
    bars = mk_closes([100] * 6)
    rsi = [np.nan, np.nan, 80, 55, 50, 65]
    sigs = run_direction(Direction.BUY, bars, mk_ind(bars, rsi), P, Variant.B)
    assert sigs == []  # cross needs rsi[t-1] valid: t=2 has nan prev -> no cross ever


def test_run_strategy_smoke_sorted_and_deterministic():
    rng = np.random.default_rng(42)
    n = 3000
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0, 1.5, n)
    from rsi_fvg.bars import Bars
    bars = Bars(time=np.arange(n, dtype=np.int64) * 300, open=open_, high=high, low=low, close=close)
    ind = compute_indicators(bars, P)
    assert ind.rsi.shape == (n,) and ind.atr.shape == (n,)
    for v in Variant:
        sigs = run_strategy(bars, P, v)
        keys = [(s.signal_bar, int(s.direction)) for s in sigs]
        assert keys == sorted(keys)
        assert sigs == run_strategy(bars, P, v)
        for s in sigs:
            assert s.anchor_bar <= s.signal_bar
            if s.direction == Direction.BUY:
                assert s.sl_price < bars.low[s.anchor_bar:s.signal_bar + 1].min()
            else:
                assert s.sl_price > bars.high[s.anchor_bar:s.signal_bar + 1].max()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_strategy.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.strategy'`.

- [ ] **Step 3: Write rsi_fvg/strategy.py**

```python
"""Strategy core: per-direction state machine -> Signals. Pure; knows nothing about positions.

Spec: docs/superpowers/specs/2026-09-08-rsi-fvg-pullback-strategy-design.md §2.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, IntEnum

import numpy as np

from .bars import Bars
from .fvg import FvgArrays, detect_fvg
from .indicators import atr_wilder, pivot_high, pivot_low, rsi_wilder
from .params import StrategyParams


class Direction(IntEnum):
    BUY = 1
    SELL = -1


class Variant(str, Enum):
    A = "A"  # FVG confirmation
    B = "B"  # RSI reclaim of mid level
    C = "C"  # close beyond pullback pivot


class State(IntEnum):
    IDLE = 0
    ARMED = 1
    WAIT = 2


@dataclass(frozen=True)
class Signal:
    direction: Direction
    variant: Variant
    signal_bar: int
    anchor_bar: int
    ref_price: float
    sl_price: float
    bars_in_wait: int
    fvg_zone: tuple[float, float] | None = None
    pivot_price: float | None = None


@dataclass
class Indicators:
    rsi: np.ndarray
    atr: np.ndarray
    fvg: FvgArrays
    piv_high: np.ndarray
    piv_low: np.ndarray


def compute_indicators(bars: Bars, params: StrategyParams) -> Indicators:
    return Indicators(
        rsi=rsi_wilder(bars.close, params.rsi_period),
        atr=atr_wilder(bars.high, bars.low, bars.close, params.atr_period),
        fvg=detect_fvg(bars.open, bars.high, bars.low, bars.close),
        piv_high=pivot_high(bars.high, params.pivot_len, params.pivot_len),
        piv_low=pivot_low(bars.low, params.pivot_len, params.pivot_len),
    )


def run_direction(direction: Direction, bars: Bars, ind: Indicators,
                  params: StrategyParams, variant: Variant) -> list[Signal]:
    buy = direction == Direction.BUY
    rsi, atr = ind.rsi, ind.atr
    close, high, low = bars.close, bars.high, bars.low
    ext = params.overbought if buy else params.oversold
    mid = params.mid_high if buy else params.mid_low
    fvg_hit = ind.fvg.bull if buy else ind.fvg.bear
    piv = ind.piv_high if buy else ind.piv_low
    piv_price = high if buy else low
    L = params.pivot_len
    n = len(bars)

    state = State.IDLE
    anchor = -1
    wait_start = -1
    last_pivot: float | None = None
    out: list[Signal] = []

    def reset_to(new_state: State, new_anchor: int) -> None:
        nonlocal state, anchor, wait_start, last_pivot
        state, anchor, wait_start, last_pivot = new_state, new_anchor, -1, None

    for t in range(1, n):
        r0, r1 = rsi[t], rsi[t - 1]
        if math.isnan(r0) or math.isnan(r1):
            continue
        cross = (r1 <= ext < r0) if buy else (r1 >= ext > r0)

        # pivot confirmed at t has index t-L; only pivots formed at/after anchor count
        p = t - L
        if p >= 0 and anchor >= 0 and p >= anchor and piv[p]:
            last_pivot = float(piv_price[p])

        if state == State.IDLE:
            if cross:
                reset_to(State.ARMED, t)
            continue

        if cross:  # ARMED or WAIT: a new cross replaces the old setup
            reset_to(State.ARMED, t)
            continue

        if state == State.ARMED:
            pulled_back = (r0 < mid) if buy else (r0 > mid)
            if pulled_back:
                state, wait_start = State.WAIT, t
            continue

        # state == WAIT
        if params.max_wait_bars > 0 and (t - wait_start) > params.max_wait_bars:
            reset_to(State.IDLE, -1)
            continue
        if t <= wait_start:
            continue

        trig = False
        zone: tuple[float, float] | None = None
        pp: float | None = None
        if variant == Variant.A:
            trig = bool(fvg_hit[t])
            if trig:
                zone = (float(ind.fvg.lo[t]), float(ind.fvg.hi[t]))
        elif variant == Variant.B:
            trig = (r1 < mid <= r0) if buy else (r1 > mid >= r0)
        elif variant == Variant.C:
            if last_pivot is not None:
                trig = (close[t] > last_pivot) if buy else (close[t] < last_pivot)
                pp = last_pivot
        if not trig:
            continue

        a = atr[t]
        if math.isnan(a):
            continue
        if buy:
            sl = float(low[anchor:t + 1].min() - params.atr_mult * a)
        else:
            sl = float(high[anchor:t + 1].max() + params.atr_mult * a)
        out.append(Signal(direction=direction, variant=variant, signal_bar=t, anchor_bar=anchor,
                          ref_price=float(close[t]), sl_price=sl, bars_in_wait=t - wait_start,
                          fvg_zone=zone, pivot_price=pp))
        reset_to(State.IDLE, -1)
    return out


def run_strategy(bars: Bars, params: StrategyParams, variant: Variant | str,
                 directions: tuple[Direction, ...] = (Direction.BUY, Direction.SELL)) -> list[Signal]:
    variant = Variant(variant)
    ind = compute_indicators(bars, params)
    out: list[Signal] = []
    for d in directions:
        out.extend(run_direction(d, bars, ind, params, variant))
    out.sort(key=lambda s: (s.signal_bar, int(s.direction)))
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_strategy.py -q`
Expected: `10 passed`. If `test_variant_c_pivot_break_and_no_pivot` fails, print `pivot_high(bars.high, 2, 2)` — it must be `True` only at index 2; adjust the `h` list in the test, not the implementation.

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -q`
Expected: all green (6 + 7 + 6 + 10 = 29 passed).

- [ ] **Step 6: Commit**

```bash
git add rsi_fvg/strategy.py tests/test_strategy.py
git commit -m "feat: strategy state machine with variants A/B/C and SL rule"
```

---

### Task 5: Position sizing

**Files:**
- Create: `rsi_fvg/sizing.py`, `tests/test_sizing.py`

**Interfaces:**
- Consumes: `SymbolSpec`.
- Produces: `lots_for_risk(equity: float, risk_pct: float, sl_dist: float, spec: SymbolSpec) -> tuple[float, bool]` — returns `(lots, oversized)`. `lots` floored to `lot_step`, clamped to `[min_lot, max_lot]`; `oversized=True` when the floored value was below `min_lot` (actual risk > target).

- [ ] **Step 1: Write failing tests**

`tests/test_sizing.py`:
```python
import pytest

from rsi_fvg.params import SymbolSpec
from rsi_fvg.sizing import lots_for_risk

SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0, min_lot=0.01, max_lot=200.0, lot_step=0.01)


def test_basic_floor_to_step():
    lots, oversized = lots_for_risk(10_000, 1.0, 10.2, SPEC)   # 100 / 10.2 = 9.8039
    assert lots == pytest.approx(9.80) and not oversized


def test_contract_size_scales():
    spec = SymbolSpec(name="X", point=0.01, digits=2, contract_size=100.0, min_lot=0.01, max_lot=100.0, lot_step=0.01)
    lots, _ = lots_for_risk(10_000, 1.0, 5.0, spec)   # 100 / (5*100) = 0.2
    assert lots == pytest.approx(0.20)


def test_min_lot_oversized_flag():
    lots, oversized = lots_for_risk(100, 1.0, 500.0, SPEC)   # 1 / 500 = 0.002 -> below min
    assert lots == 0.01 and oversized


def test_max_lot_clamp():
    lots, oversized = lots_for_risk(10_000_000, 1.0, 1.0, SPEC)   # 100000 lots -> clamp
    assert lots == 200.0 and not oversized


def test_invalid_sl_dist_raises():
    with pytest.raises(ValueError):
        lots_for_risk(10_000, 1.0, 0.0, SPEC)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sizing.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.sizing'`.

- [ ] **Step 3: Write rsi_fvg/sizing.py**

```python
"""Risk-based lot sizing (spec §2.7)."""
from __future__ import annotations

import math

from .params import SymbolSpec


def lots_for_risk(equity: float, risk_pct: float, sl_dist: float, spec: SymbolSpec) -> tuple[float, bool]:
    if sl_dist <= 0:
        raise ValueError(f"sl_dist must be > 0, got {sl_dist}")
    risk_usd = equity * risk_pct / 100.0
    raw = risk_usd / (sl_dist * spec.contract_size)
    steps = math.floor(raw / spec.lot_step + 1e-9)
    lots = steps * spec.lot_step
    oversized = False
    if lots < spec.min_lot:
        lots, oversized = spec.min_lot, True
    lots = min(lots, spec.max_lot)
    return round(lots, 8), oversized
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sizing.py -q`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/sizing.py tests/test_sizing.py
git commit -m "feat: risk-percent lot sizing"
```

---

### Task 6: Backtest engine

**Files:**
- Create: `rsi_fvg/backtest/__init__.py` (empty), `rsi_fvg/backtest/engine.py`, `tests/test_engine.py`

**Interfaces:**
- Consumes: `Bars`, `Signal`, `Direction`, `Variant`, `SymbolSpec`, `CostParams`, `SizingParams`, `lots_for_risk`.
- Produces:
  - `TRADE_COLUMNS: list[str]` = `["entry_time","exit_time","direction","variant","tp_r","entry_price","exit_price","sl_price","tp_price","lots","sl_dist","risk_usd","r_multiple","pnl_usd","commission","exit_reason","bars_held","bars_in_wait","anchor_time","oversized"]`
  - `SKIPPED_COLUMNS` = `["time","signal_time","direction","variant","reason"]`
  - `BacktestResult(trades: pd.DataFrame, skipped: pd.DataFrame, equity: pd.Series, tp_r: float, variant: str, concurrency: str, initial_equity: float)`
  - `run_backtest(bars: Bars, signals: list[Signal], tp_r: float, spec: SymbolSpec, costs: CostParams, sizing: SizingParams, concurrency: str = "hedge") -> BacktestResult`
  - Time columns are tz-aware UTC `datetime64[ns, UTC]`; `equity` is indexed by `bars.datetimes()`.

- [ ] **Step 1: Write failing tests**

`tests/test_engine.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.backtest'`.

- [ ] **Step 3: Write rsi_fvg/backtest/__init__.py (empty) and rsi_fvg/backtest/engine.py**

```python
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
from ..strategy import Direction, Signal

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
    variant_name = signals[0].variant.value if signals else ""

    def close_position(pos: Position, bar: int, price: float, reason: str) -> None:
        nonlocal equity
        d = int(pos.direction)
        gross = d * (price - pos.entry_price) * pos.lots * cs
        equity += gross
        net = gross - pos.commission
        trades.append({
            "entry_time": tm[pos.entry_bar], "exit_time": tm[bar], "direction": pos.direction.name,
            "variant": pos.signal.variant.value, "tp_r": tp_r, "entry_price": pos.entry_price,
            "exit_price": price, "sl_price": pos.sl, "tp_price": pos.tp, "lots": pos.lots,
            "sl_dist": pos.sl_dist, "risk_usd": pos.risk_usd, "r_multiple": net / pos.risk_usd,
            "pnl_usd": net, "commission": pos.commission, "exit_reason": reason,
            "bars_held": bar - pos.entry_bar, "bars_in_wait": pos.signal.bars_in_wait,
            "anchor_time": tm[pos.signal.anchor_bar], "oversized": pos.oversized,
        })

    def skip(s: Signal, bar: int, reason: str) -> None:
        skipped.append({"time": tm[bar], "signal_time": tm[s.signal_bar], "direction": s.direction.name,
                        "variant": s.variant.value, "reason": reason})

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -q`
Expected: `10 passed`. (`test_signal_on_last_bar_never_fills` has a harmless `mk_mk =` alias; leave it.)

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/backtest/__init__.py rsi_fvg/backtest/engine.py tests/test_engine.py
git commit -m "feat: event-driven backtest engine with hedge/single concurrency"
```

---

### Task 7: Metrics

**Files:**
- Create: `rsi_fvg/backtest/metrics.py`, `tests/test_metrics.py`

**Interfaces:**
- Consumes: trade DataFrame with `TRADE_COLUMNS`; equity `pd.Series` (UTC index).
- Produces:
  - `max_drawdown(equity: pd.Series) -> tuple[float, float]` → `(dd_usd, dd_pct)` both `>= 0`.
  - `equity_from_trades(trades: pd.DataFrame, initial_equity: float) -> pd.Series` — step curve at `exit_time`, starts with `initial_equity` at the first `entry_time` (or empty Series if no trades).
  - `compute_metrics(trades: pd.DataFrame, equity: pd.Series, initial_equity: float, n_blocked: int = 0) -> dict` with keys: `n_trades, n_wins, win_rate, avg_r, expectancy_r, profit_factor, max_dd_usd, max_dd_pct, sharpe_daily, cagr, avg_bars_held, net_pnl, final_equity, n_blocked, n_buy, n_sell, avg_r_buy, avg_r_sell`. Empty trades → all zeros (`profit_factor = 0.0`), `final_equity = initial_equity`.

- [ ] **Step 1: Write failing tests**

`tests/test_metrics.py`:
```python
import numpy as np
import pandas as pd
import pytest

from rsi_fvg.backtest.engine import TRADE_COLUMNS
from rsi_fvg.backtest.metrics import compute_metrics, equity_from_trades, max_drawdown


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_metrics.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.backtest.metrics'`.

- [ ] **Step 3: Write rsi_fvg/backtest/metrics.py**

```python
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


def _sharpe_daily(equity: pd.Series) -> float:
    if len(equity) < 3:
        return 0.0
    daily = equity.resample("1D").last().dropna().pct_change().dropna()
    if len(daily) < 2 or daily.std() == 0:
        return 0.0
    return float(daily.mean() / daily.std() * np.sqrt(252))


def _cagr(equity: pd.Series, initial_equity: float) -> float:
    if equity.empty or initial_equity <= 0:
        return 0.0
    years = (equity.index[-1] - equity.index[0]).total_seconds() / (365.25 * 86400)
    if years <= 0 or equity.iloc[-1] <= 0:
        return 0.0
    return float((equity.iloc[-1] / initial_equity) ** (1 / years) - 1)


def compute_metrics(trades: pd.DataFrame, equity: pd.Series, initial_equity: float, n_blocked: int = 0) -> dict:
    n = int(len(trades))
    if n == 0:
        return {"n_trades": 0, "n_wins": 0, "win_rate": 0.0, "avg_r": 0.0, "expectancy_r": 0.0,
                "profit_factor": 0.0, "max_dd_usd": 0.0, "max_dd_pct": 0.0, "sharpe_daily": 0.0, "cagr": 0.0,
                "avg_bars_held": 0.0, "net_pnl": 0.0, "final_equity": float(initial_equity),
                "n_blocked": int(n_blocked), "n_buy": 0, "n_sell": 0, "avg_r_buy": 0.0, "avg_r_sell": 0.0}
    pnl = trades["pnl_usd"].astype(float)
    r = trades["r_multiple"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_loss = float(-losses.sum())
    pf = float(wins.sum() / gross_loss) if gross_loss > 0 else (np.inf if wins.sum() > 0 else 0.0)
    dd_usd, dd_pct = max_drawdown(equity)
    buy = trades[trades["direction"] == "BUY"]
    sell = trades[trades["direction"] == "SELL"]
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
        "cagr": _cagr(equity, initial_equity),
        "avg_bars_held": float(trades["bars_held"].astype(float).mean()),
        "net_pnl": float(pnl.sum()),
        "final_equity": float(initial_equity + pnl.sum()),
        "n_blocked": int(n_blocked),
        "n_buy": int(len(buy)),
        "n_sell": int(len(sell)),
        "avg_r_buy": float(buy["r_multiple"].astype(float).mean()) if len(buy) else 0.0,
        "avg_r_sell": float(sell["r_multiple"].astype(float).mean()) if len(sell) else 0.0,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_metrics.py -q`
Expected: `5 passed`. If `test_max_drawdown_simple` fails on `dd_pct`, the expected value is `max(30/120, 30/130) = 0.25` — the assertion already encodes `30/120`.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/backtest/metrics.py tests/test_metrics.py
git commit -m "feat: backtest metrics (R stats, drawdown, sharpe, cagr)"
```

---

### Task 8: Data loaders (MT5 + CSV) and fetch script

**Files:**
- Create: `rsi_fvg/data/__init__.py` (empty), `rsi_fvg/data/mt5_loader.py`, `rsi_fvg/data/csv_loader.py`, `scripts/fetch_data.py`, `tests/test_csv_loader.py`, `tests/test_mt5_loader.py`

**Interfaces:**
- Consumes: `SymbolSpec`, `load_config`.
- Produces:
  - `RATE_COLUMNS = ["time", "open", "high", "low", "close", "tick_volume", "spread"]`; every loader returns a DataFrame with these columns (CSV may lack `tick_volume`/`spread` → filled with 0), `time` = int64 epoch seconds, sorted, unique.
  - `mt5_loader.Mt5Session()` context manager (initialize/shutdown, raises `RuntimeError` on failure).
  - `mt5_loader.tf_constant(tf: str) -> int`
  - `mt5_loader.fetch_symbol_spec(symbol: str) -> SymbolSpec` (requires open session)
  - `mt5_loader.fetch_rates(symbol: str, tf: str, start: datetime | None = None, chunk: int = 50_000) -> pd.DataFrame` (requires open session)
  - `mt5_loader.cache_paths(data_dir: Path, symbol: str, tf: str) -> tuple[Path, Path]` → `(parquet, spec_json)`
  - `mt5_loader.load_or_fetch(symbol, tf, data_dir: Path, refresh=False, start=None, fallback_spec: SymbolSpec | None = None) -> tuple[pd.DataFrame, SymbolSpec]`
  - `csv_loader.load_csv(path) -> pd.DataFrame`

- [ ] **Step 1: Write failing tests**

`tests/test_csv_loader.py`:
```python
import pandas as pd

from rsi_fvg.data.csv_loader import load_csv
from rsi_fvg.data.mt5_loader import RATE_COLUMNS


def test_load_csv_datetime_strings(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("time,open,high,low,close\n2025-01-01 00:05:00,1,2,0,1.5\n2025-01-01 00:00:00,1,2,0,1.5\n")
    df = load_csv(p)
    assert list(df.columns) == RATE_COLUMNS
    assert df["time"].dtype == "int64"
    assert list(df["time"]) == sorted(df["time"])            # sorted ascending
    assert df["time"].iloc[0] == int(pd.Timestamp("2025-01-01 00:00:00", tz="UTC").timestamp())
    assert (df["spread"] == 0).all() and (df["tick_volume"] == 0).all()


def test_load_csv_epoch_and_dedupe(tmp_path):
    p = tmp_path / "y.csv"
    p.write_text("time,open,high,low,close,spread\n300,1,2,0,1.5,20\n300,1,2,0,1.5,20\n600,1,2,0,1.5,21\n")
    df = load_csv(p)
    assert list(df["time"]) == [300, 600] and df["spread"].iloc[1] == 21
```

`tests/test_mt5_loader.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_csv_loader.py tests/test_mt5_loader.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.data'`.

- [ ] **Step 3: Write rsi_fvg/data/__init__.py (empty), rsi_fvg/data/csv_loader.py**

```python
"""CSV fallback loader. Accepts epoch seconds or datetime strings in `time`."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .mt5_loader import RATE_COLUMNS


def load_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    t = df["time"]
    if np.issubdtype(t.dtype, np.number):
        time = t.astype("int64")
    else:
        time = (pd.to_datetime(t, utc=True).astype("int64") // 1_000_000_000).astype("int64")
    out = pd.DataFrame({"time": time})
    for c in ("open", "high", "low", "close"):
        out[c] = df[c].astype(float)
    out["tick_volume"] = df["tick_volume"].astype("int64") if "tick_volume" in df else 0
    out["spread"] = df["spread"].astype("int64") if "spread" in df else 0
    out = out.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return out[RATE_COLUMNS]
```

- [ ] **Step 4: Write rsi_fvg/data/mt5_loader.py**

```python
"""Pull OHLC history from the running MT5 terminal; cache parquet + symbol-spec sidecar (spec §3.7)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from ..params import SymbolSpec

log = logging.getLogger(__name__)

RATE_COLUMNS = ["time", "open", "high", "low", "close", "tick_volume", "spread"]
_TF_ATTR = {"M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15", "M30": "TIMEFRAME_M30",
            "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4", "D1": "TIMEFRAME_D1"}


def _mt5():
    import MetaTrader5 as mt5  # lazy: importing this module must not require MT5

    return mt5


def tf_constant(tf: str) -> int:
    return getattr(_mt5(), _TF_ATTR[tf.upper()])


class Mt5Session:
    def __enter__(self):
        mt5 = _mt5()
        if not mt5.initialize():
            raise RuntimeError(f"mt5.initialize() failed: {mt5.last_error()}")
        return mt5

    def __exit__(self, *exc):
        _mt5().shutdown()
        return False


def fetch_symbol_spec(symbol: str) -> SymbolSpec:
    mt5 = _mt5()
    mt5.symbol_select(symbol, True)
    si = mt5.symbol_info(symbol)
    if si is None:
        raise RuntimeError(f"symbol_info({symbol!r}) is None: {mt5.last_error()}")
    return SymbolSpec(name=symbol, point=float(si.point), digits=int(si.digits),
                      contract_size=float(si.trade_contract_size), min_lot=float(si.volume_min),
                      max_lot=float(si.volume_max), lot_step=float(si.volume_step),
                      stops_level_points=int(si.trade_stops_level))


def fetch_rates(symbol: str, tf: str, start: datetime | None = None, chunk: int = 50_000) -> pd.DataFrame:
    mt5 = _mt5()
    tfc = tf_constant(tf)
    date_to = datetime.now(timezone.utc) + timedelta(days=1)
    frames: list[pd.DataFrame] = []
    suspect_cap = False
    while True:
        rates = mt5.copy_rates_from(symbol, tfc, date_to, chunk)
        if rates is None or len(rates) == 0:
            suspect_cap = bool(frames) and len(frames[-1]) == chunk
            break
        df = pd.DataFrame(rates)[RATE_COLUMNS]
        frames.append(df)
        oldest = int(df["time"].iloc[0])
        if len(rates) < chunk:
            break
        if start is not None and oldest <= int(start.timestamp()):
            break
        date_to = datetime.fromtimestamp(oldest, tz=timezone.utc) - timedelta(seconds=1)
    if not frames:
        raise RuntimeError(f"no rates for {symbol} {tf}: {mt5.last_error()}")
    out = pd.concat(frames, ignore_index=True).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    if start is not None:
        out = out[out["time"] >= int(start.timestamp())].reset_index(drop=True)
    out["time"] = out["time"].astype("int64")
    if suspect_cap:
        log.warning("%s %s: history ended exactly on a full chunk (%d bars) — may be capped by the terminal's "
                    "'Max bars in chart' setting (Tools > Options > Charts).", symbol, tf, chunk)
    return out


def cache_paths(data_dir: Path, symbol: str, tf: str) -> tuple[Path, Path]:
    data_dir = Path(data_dir)
    return data_dir / f"{symbol}_{tf}.parquet", data_dir / f"{symbol}_{tf}.spec.json"


def load_or_fetch(symbol: str, tf: str, data_dir: Path, refresh: bool = False, start: datetime | None = None,
                  fallback_spec: SymbolSpec | None = None) -> tuple[pd.DataFrame, SymbolSpec]:
    pq, sj = cache_paths(data_dir, symbol, tf)
    if pq.exists() and not refresh:
        df = pd.read_parquet(pq)
        if sj.exists():
            spec = SymbolSpec.from_dict(json.loads(sj.read_text(encoding="utf-8")))
        else:
            spec = fallback_spec or SymbolSpec(name=symbol)
            log.warning("%s: spec sidecar missing, using fallback %s", pq.name, spec)
        return df, spec
    with Mt5Session():
        spec = fetch_symbol_spec(symbol)
        df = fetch_rates(symbol, tf, start=start)
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    df.to_parquet(pq, index=False)
    sj.write_text(json.dumps(spec.to_dict(), indent=2), encoding="utf-8")
    log.info("%s %s: %d bars cached to %s", symbol, tf, len(df), pq)
    return df, spec
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_csv_loader.py tests/test_mt5_loader.py -q`
Expected: `7 passed` (MT5 terminal is open on this machine; if it is closed, the 2 `@needs_mt5` tests skip — that is acceptable but note it in the task report).

- [ ] **Step 6: Write scripts/fetch_data.py**

```python
"""Fetch/cache OHLC history from MT5 for the configured symbol/timeframes.

Usage: python scripts/fetch_data.py [--tf M5 M15 H1] [--refresh] [--start 2023-01-01]
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.params import load_config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    ap.add_argument("--symbol")
    ap.add_argument("--tf", nargs="*")
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--start", help="YYYY-MM-DD (UTC); default = as far back as the broker allows")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = load_config(a.config)
    symbol = a.symbol or cfg.symbol
    tfs = a.tf or cfg.timeframes
    start = datetime.strptime(a.start, "%Y-%m-%d").replace(tzinfo=timezone.utc) if a.start else None
    for tf in tfs:
        df, spec = load_or_fetch(symbol, tf, Path(a.data_dir), refresh=a.refresh, start=start,
                                 fallback_spec=cfg.spec_fallback)
        t0 = datetime.fromtimestamp(int(df["time"].iloc[0]), tz=timezone.utc)
        t1 = datetime.fromtimestamp(int(df["time"].iloc[-1]), tz=timezone.utc)
        print(f"{symbol} {tf:>3}: {len(df):>8,d} bars  {t0:%Y-%m-%d} -> {t1:%Y-%m-%d %H:%M}  "
              f"point={spec.point} contract={spec.contract_size} lot_step={spec.lot_step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Fetch the real data (MT5 terminal must be open)**

Run: `python scripts/fetch_data.py`
Expected: three lines like `XAUUSDc  M5:  xxx,xxx bars  2024-xx-xx -> 2026-09-08 ...` and files `data/XAUUSDc_M5.parquet`, `data/XAUUSDc_M5.spec.json` (and M15/H1). Record the bar counts and date ranges in the task report — they determine how many years of backtest we have per TF. If a WARNING about 'Max bars in chart' appears, tell the user how to raise the setting in MT5 (Tools → Options → Charts → Max bars in chart → Unlimited) and rerun with `--refresh`.

- [ ] **Step 8: Commit**

```bash
git add rsi_fvg/data scripts/fetch_data.py tests/test_csv_loader.py tests/test_mt5_loader.py
git commit -m "feat: MT5 history loader with parquet cache, CSV fallback, fetch script"
```

---

### Task 9: Grid runner, report, CLI, README, full run

**Files:**
- Create: `rsi_fvg/backtest/runner.py`, `rsi_fvg/backtest/report.py`, `scripts/run_backtest.py`, `tests/test_runner_report.py`, `README.md`

**Interfaces:**
- Consumes: `Bars`, `Config`, `StrategyParams`, `SymbolSpec`, `run_strategy`, `run_backtest`, `BacktestResult`, `compute_metrics`, `equity_from_trades`, `load_or_fetch`, `load_csv`.
- Produces:
  - `runner.split_time(bars: Bars, oos_frac: float) -> pd.Timestamp`
  - `runner.run_grid(bars_by_tf: dict[str, Bars], spec_by_tf: dict[str, SymbolSpec], cfg: Config, variants: list[str] | None = None, tps: list[float] | None = None, concurrency: str | None = None, max_wait_bars: int | None = None) -> tuple[pd.DataFrame, dict[tuple[str, str, float], BacktestResult]]` — summary has columns `tf, variant, tp_r, n_signals` + every key of `compute_metrics` + `is_<k>` / `oos_<k>` for `k in ("n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct", "net_pnl")`.
  - `report.write_report(out_dir: Path, summary: pd.DataFrame, results: dict, cfg: Config, meta: dict) -> None` — writes `summary.csv`, `summary.md`, `trades_<tf>_<v>_<R>R.csv`, `skipped_<tf>_<v>_<R>R.csv` (when non-empty), `equity_<tf>_<v>.png`, `heatmap_<tf>.png`.

- [ ] **Step 1: Write failing tests**

`tests/test_runner_report.py`:
```python
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from rsi_fvg.backtest.report import write_report
from rsi_fvg.backtest.runner import run_grid, split_time
from rsi_fvg.bars import Bars
from rsi_fvg.params import SymbolSpec, load_config

ROOT = Path(__file__).resolve().parents[1]


def _random_bars(n=4000, seed=7):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    return Bars(time=1_700_000_000 + np.arange(n, dtype=np.int64) * 300, open=open_, high=high, low=low, close=close)


def test_split_time_is_80_20():
    bars = _random_bars(1000)
    st = split_time(bars, 0.2)
    assert st == bars.datetimes()[800]


def test_run_grid_shape_and_columns():
    cfg = load_config(ROOT / "config" / "default.yaml")
    bars = _random_bars()
    spec = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0)
    summary, results = run_grid({"M5": bars, "M15": bars}, {"M5": spec, "M15": spec}, cfg,
                                variants=["A", "B"], tps=[1.0, 3.0])
    assert len(summary) == 2 * 2 * 2 and set(results) == {(tf, v, tp) for tf in ("M5", "M15") for v in "AB" for tp in (1.0, 3.0)}
    for col in ("tf", "variant", "tp_r", "n_signals", "n_trades", "avg_r", "profit_factor", "max_dd_pct",
                "is_n_trades", "oos_n_trades", "oos_avg_r", "n_buy", "n_sell", "n_blocked"):
        assert col in summary.columns
    assert (summary["is_n_trades"] + summary["oos_n_trades"] == summary["n_trades"]).all()
    # signals are computed once per (tf, variant): same n_signals across tp levels
    assert summary.groupby(["tf", "variant"])["n_signals"].nunique().eq(1).all()


def test_run_grid_max_wait_override_changes_params():
    cfg = load_config(ROOT / "config" / "default.yaml")
    bars = _random_bars()
    spec = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0)
    s0, _ = run_grid({"M5": bars}, {"M5": spec}, cfg, variants=["B"], tps=[3.0])
    s1, _ = run_grid({"M5": bars}, {"M5": spec}, cfg, variants=["B"], tps=[3.0], max_wait_bars=3)
    assert s1["n_signals"].iloc[0] <= s0["n_signals"].iloc[0]


def test_write_report_creates_files(tmp_path):
    cfg = load_config(ROOT / "config" / "default.yaml")
    bars = _random_bars()
    spec = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0)
    summary, results = run_grid({"M5": bars}, {"M5": spec}, cfg, variants=["A", "B"], tps=[1.0, 3.0])
    out = tmp_path / "run"
    write_report(out, summary, results, cfg, meta={"symbol": "T", "data_range": {"M5": ("2023-01-01", "2023-02-01")}})
    names = {p.name for p in out.iterdir()}
    assert {"summary.csv", "summary.md", "equity_M5_A.png", "equity_M5_B.png", "heatmap_M5.png"} <= names
    assert "trades_M5_A_1R.csv" in names and "trades_M5_B_3R.csv" in names
    md = (out / "summary.md").read_text(encoding="utf-8")
    assert "Top" in md and "M5" in md
    back = pd.read_csv(out / "summary.csv")
    assert len(back) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_runner_report.py -q`
Expected: `ModuleNotFoundError: No module named 'rsi_fvg.backtest.runner'`.

- [ ] **Step 3: Write rsi_fvg/backtest/runner.py**

```python
"""Grid runner: TF x variant x TP, with IS/OOS split by time (spec §3.6)."""
from __future__ import annotations

from dataclasses import replace

import pandas as pd

from ..bars import Bars
from ..params import Config, SymbolSpec
from ..strategy import run_strategy
from .engine import BacktestResult, run_backtest
from .metrics import compute_metrics, equity_from_trades

SPLIT_KEYS = ("n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct", "net_pnl")


def split_time(bars: Bars, oos_frac: float) -> pd.Timestamp:
    idx = int(len(bars) * (1.0 - oos_frac))
    idx = min(max(idx, 0), len(bars) - 1)
    return bars.datetimes()[idx]


def run_grid(bars_by_tf: dict[str, Bars], spec_by_tf: dict[str, SymbolSpec], cfg: Config,
             variants: list[str] | None = None, tps: list[float] | None = None,
             concurrency: str | None = None, max_wait_bars: int | None = None,
             ) -> tuple[pd.DataFrame, dict[tuple[str, str, float], BacktestResult]]:
    variants = variants or cfg.variants
    tps = [float(x) for x in (tps or cfg.tp_r)]
    concurrency = concurrency or cfg.concurrency
    params = cfg.strategy if max_wait_bars is None else replace(cfg.strategy, max_wait_bars=max_wait_bars)
    init_eq = cfg.sizing.initial_equity

    rows: list[dict] = []
    results: dict[tuple[str, str, float], BacktestResult] = {}
    for tf, bars in bars_by_tf.items():
        split = split_time(bars, cfg.oos_frac)
        spec = spec_by_tf[tf]
        for v in variants:
            signals = run_strategy(bars, params, v)
            for tp in tps:
                res = run_backtest(bars, signals, tp, spec, cfg.costs, cfg.sizing, concurrency)
                results[(tf, v, tp)] = res
                n_blocked = int((res.skipped["reason"] == "blocked").sum()) if len(res.skipped) else 0
                full = compute_metrics(res.trades, res.equity, init_eq, n_blocked=n_blocked)
                is_tr = res.trades[res.trades["entry_time"] < split]
                oos_tr = res.trades[res.trades["entry_time"] >= split]
                is_m = compute_metrics(is_tr, equity_from_trades(is_tr, init_eq), init_eq)
                oos_m = compute_metrics(oos_tr, equity_from_trades(oos_tr, init_eq), init_eq)
                row = {"tf": tf, "variant": v, "tp_r": tp, "n_signals": len(signals), "split_time": split}
                row.update(full)
                row.update({f"is_{k}": is_m[k] for k in SPLIT_KEYS})
                row.update({f"oos_{k}": oos_m[k] for k in SPLIT_KEYS})
                rows.append(row)
    return pd.DataFrame(rows), results
```

- [ ] **Step 4: Load the `dataviz` skill, then write rsi_fvg/backtest/report.py**

Invoke the `dataviz` skill (Skill tool) before writing plotting code and apply its guidance on palette/axes/labels to the two chart functions below (keep the file names and signatures fixed).

```python
"""Write summary.csv / summary.md / trade CSVs / equity + heatmap PNGs (spec §3.6)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ..params import Config  # noqa: E402
from .engine import BacktestResult  # noqa: E402

MIN_TRADES = 30
TOP_N = 10


def _fmt_r(tp: float) -> str:
    return f"{tp:g}R"


def _plot_equity(out_dir: Path, tf: str, variant: str, per_tp: dict[float, BacktestResult]) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for tp in sorted(per_tp):
        res = per_tp[tp]
        ax.plot(res.equity.index, res.equity.values, label=f"TP {_fmt_r(tp)}", linewidth=1.2)
    ax.set_title(f"Equity — {tf} — Variant {variant}")
    ax.set_ylabel("Equity (USD)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", frameon=False)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_dir / f"equity_{tf}_{variant}.png", dpi=120)
    plt.close(fig)


def _plot_heatmap(out_dir: Path, tf: str, summary_tf: pd.DataFrame) -> None:
    piv = summary_tf.pivot(index="variant", columns="tp_r", values="avg_r").sort_index()
    ntr = summary_tf.pivot(index="variant", columns="tp_r", values="n_trades").reindex_like(piv)
    fig, ax = plt.subplots(figsize=(1.6 * piv.shape[1] + 2, 1.0 * piv.shape[0] + 1.5))
    vmax = max(float(np.nanmax(np.abs(piv.values))) if piv.size else 1.0, 1e-9)
    im = ax.imshow(piv.values, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(piv.shape[1]), [_fmt_r(c) for c in piv.columns])
    ax.set_yticks(range(piv.shape[0]), list(piv.index))
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            ax.text(j, i, f"{piv.values[i, j]:+.2f}\n(n={int(ntr.values[i, j])})", ha="center", va="center", fontsize=9)
    ax.set_title(f"Avg R per trade — {tf} (variant × TP)")
    fig.colorbar(im, ax=ax, fraction=0.03, label="avg R")
    fig.tight_layout()
    fig.savefig(out_dir / f"heatmap_{tf}.png", dpi=120)
    plt.close(fig)


def _md_table(df: pd.DataFrame, cols: list[str]) -> str:
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    body = ""
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(f"{v:.3f}" if isinstance(v, float) and not float(v).is_integer() else str(v))
        body += "| " + " | ".join(cells) + " |\n"
    return head + body


def _summary_md(summary: pd.DataFrame, cfg: Config, meta: dict) -> str:
    s = summary.copy()
    s["flag"] = np.where(s["n_trades"] < MIN_TRADES, "⚠ n<30", "")
    top = s.sort_values(["oos_avg_r", "avg_r"], ascending=False).head(TOP_N)
    cols = ["tf", "variant", "tp_r", "n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct",
            "is_avg_r", "oos_avg_r", "oos_n_trades", "n_buy", "n_sell", "flag"]
    lines = [f"# RSI-FVG backtest — {meta.get('symbol', cfg.symbol)}", ""]
    lines.append(f"Concurrency: `{cfg.concurrency}` · risk {cfg.sizing.risk_pct}% · spread {cfg.costs.spread_points} pts · "
                 f"commission {cfg.costs.commission_per_lot_rt}/lot · slippage {cfg.costs.slippage_points} pts · "
                 f"max_wait_bars {cfg.strategy.max_wait_bars} · OOS = last {int(cfg.oos_frac * 100)}%")
    for tf, (a, b) in meta.get("data_range", {}).items():
        lines.append(f"- {tf}: {a} → {b}")
    lines += ["", f"## Top {TOP_N} by OOS avg R", "", _md_table(top, cols)]
    for tf, g in s.groupby("tf", sort=False):
        lines += ["", f"## {tf}", "", _md_table(g.sort_values(["variant", "tp_r"]), cols)]
    warns = []
    for _, r in s.iterrows():
        key = f"{r.tf}/{r.variant}/{_fmt_r(r.tp_r)}"
        if r.n_trades < MIN_TRADES:
            warns.append(f"- {key}: only {int(r.n_trades)} trades — not statistically meaningful")
        if r.n_buy and r.n_sell and max(r.n_buy, r.n_sell) / max(1, min(r.n_buy, r.n_sell)) > 2:
            warns.append(f"- {key}: BUY/SELL imbalance {int(r.n_buy)}/{int(r.n_sell)}")
        if r.is_avg_r > 0 and r.oos_avg_r < 0:
            warns.append(f"- {key}: positive IS ({r.is_avg_r:+.2f}R) but negative OOS ({r.oos_avg_r:+.2f}R) — possible overfit")
    lines += ["", "## Warnings", ""] + (warns or ["- none"])
    return "\n".join(lines) + "\n"


def write_report(out_dir: Path, summary: pd.DataFrame, results: dict, cfg: Config, meta: dict) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_dir / "summary.csv", index=False)
    for (tf, v, tp), res in results.items():
        res.trades.to_csv(out_dir / f"trades_{tf}_{v}_{_fmt_r(tp)}.csv", index=False)
        if len(res.skipped):
            res.skipped.to_csv(out_dir / f"skipped_{tf}_{v}_{_fmt_r(tp)}.csv", index=False)
    for tf in summary["tf"].unique():
        for v in summary.loc[summary["tf"] == tf, "variant"].unique():
            per_tp = {tp: r for (t, vv, tp), r in results.items() if t == tf and vv == v}
            _plot_equity(out_dir, tf, v, per_tp)
        _plot_heatmap(out_dir, tf, summary[summary["tf"] == tf])
    (out_dir / "summary.md").write_text(_summary_md(summary, cfg, meta), encoding="utf-8")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_runner_report.py -q`
Expected: `4 passed`.

- [ ] **Step 6: Write scripts/run_backtest.py**

```python
"""Run the TF x variant x TP grid on cached data and write results/<timestamp>/.

Usage:
  python scripts/run_backtest.py                       # everything from config/default.yaml
  python scripts/run_backtest.py --tf M15 H1 --variant A C --tp 2 3 --concurrency single
  python scripts/run_backtest.py --max-wait-bars 40    # try the optional flag expiry
  python scripts/run_backtest.py --csv data/my_M5.csv --tf M5   # CSV instead of MT5 cache
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from rsi_fvg.backtest.report import write_report  # noqa: E402
from rsi_fvg.backtest.runner import run_grid  # noqa: E402
from rsi_fvg.bars import Bars  # noqa: E402
from rsi_fvg.data.csv_loader import load_csv  # noqa: E402
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.params import load_config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    ap.add_argument("--symbol")
    ap.add_argument("--tf", nargs="*")
    ap.add_argument("--variant", nargs="*")
    ap.add_argument("--tp", nargs="*", type=float)
    ap.add_argument("--concurrency", choices=["hedge", "single"])
    ap.add_argument("--max-wait-bars", type=int)
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--csv", help="single CSV file; use with exactly one --tf")
    ap.add_argument("--out", default=str(ROOT / "results"))
    a = ap.parse_args()

    cfg = load_config(a.config)
    symbol = a.symbol or cfg.symbol
    tfs = a.tf or cfg.timeframes
    bars_by_tf, spec_by_tf, ranges = {}, {}, {}
    for tf in tfs:
        if a.csv:
            df, spec = load_csv(a.csv), cfg.spec_fallback
        else:
            df, spec = load_or_fetch(symbol, tf, Path(a.data_dir), fallback_spec=cfg.spec_fallback)
        bars = Bars.from_dataframe(df)
        bars_by_tf[tf], spec_by_tf[tf] = bars, spec
        dt = bars.datetimes()
        ranges[tf] = (f"{dt[0]:%Y-%m-%d}", f"{dt[-1]:%Y-%m-%d}")
        print(f"{tf}: {len(bars):,d} bars {ranges[tf][0]} -> {ranges[tf][1]}  spec={spec}")

    summary, results = run_grid(bars_by_tf, spec_by_tf, cfg, variants=a.variant, tps=a.tp,
                                concurrency=a.concurrency, max_wait_bars=a.max_wait_bars)
    out_dir = Path(a.out) / datetime.now().strftime("%Y%m%d_%H%M%S")
    write_report(out_dir, summary, results, cfg, meta={"symbol": symbol, "data_range": ranges})

    pd.set_option("display.width", 200)
    cols = ["tf", "variant", "tp_r", "n_trades", "win_rate", "avg_r", "profit_factor", "max_dd_pct", "oos_avg_r", "oos_n_trades"]
    print(summary.sort_values(["oos_avg_r", "avg_r"], ascending=False)[cols].head(10).to_string(index=False))
    print(f"\nwritten: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run the full grid on real data**

Run: `python scripts/run_backtest.py`
Expected: prints 3 data lines, then a top-10 table, then `written: .../results/<ts>`. Directory contains `summary.csv` (45 rows), `summary.md`, 45 `trades_*.csv`, 9 `equity_*.png`, 3 `heatmap_*.png`. Wall time should be under ~3 minutes on M5 (~150k+ bars). Open `summary.md` and copy the Top-10 table plus the Warnings section into the task report for the user — **do not editorialise about whether the strategy "works"; report the numbers and the warnings.**

Also run once with `--concurrency single` and once with `--max-wait-bars 40` so the user has the comparison folders; list the three result paths in the report.

- [ ] **Step 8: Write README.md**

```markdown
# RSI-FVG Pullback Strategy

RSI(14) overbought/oversold → pullback to mid band → entry confirmation (FVG / RSI reclaim / pivot break).
Spec: `docs/superpowers/specs/2026-09-08-rsi-fvg-pullback-strategy-design.md`.

## Setup (Windows, Python 3.13)

    pip install -r requirements.txt

MT5 terminal must be open and logged in for data fetching. **Use a demo account for anything that trades.**

## Data

    python scripts/fetch_data.py                 # XAUUSDc M5/M15/H1 -> data/*.parquet + *.spec.json
    python scripts/fetch_data.py --refresh       # re-download
    python scripts/fetch_data.py --start 2023-01-01

If you see a "Max bars in chart" warning: MT5 → Tools → Options → Charts → Max bars in chart → Unlimited, restart terminal, rerun with `--refresh`.

## Backtest

    python scripts/run_backtest.py                                  # full grid 3 TF x 3 variants x 5 TP
    python scripts/run_backtest.py --tf M15 --variant A --tp 3
    python scripts/run_backtest.py --concurrency single             # Pine-comparable (no hedge)
    python scripts/run_backtest.py --max-wait-bars 40               # optional flag expiry

Output: `results/<timestamp>/summary.csv`, `summary.md`, `trades_<tf>_<variant>_<R>R.csv`, `equity_*.png`, `heatmap_*.png`.

## Layout

- `rsi_fvg/strategy.py` — the single source of truth for signal logic (state machine). Live bot and MQL5/Pine ports follow this file.
- `rsi_fvg/backtest/` — engine, metrics, grid runner, report.
- `rsi_fvg/data/` — MT5 loader (parquet cache + spec sidecar), CSV fallback.
- `config/default.yaml` — all parameters.

## Tests

    python -m pytest -q

MT5 integration tests skip automatically when the terminal is not running.

## Known limits (Phase 1)

- Fixed spread model (`costs.spread_points`); real spread per bar is stored in the parquet but not used yet.
- No session filter, trailing stop, or partial TP (by design — see spec §2.9).
- Live bot, MQL5 EA, Pine Script and cross-platform parity checks are Phase 2.
```

- [ ] **Step 9: Run the whole suite one last time**

Run: `python -m pytest -q`
Expected: all passed (≈ 60 tests), 0 failed; MT5 tests either pass or skip.

- [ ] **Step 10: Commit**

```bash
git add rsi_fvg/backtest/runner.py rsi_fvg/backtest/report.py scripts/run_backtest.py tests/test_runner_report.py README.md
git commit -m "feat: grid runner with IS/OOS split, report writer, backtest CLI, README"
```

---

## Phase 2 roadmap (separate plan, written after Phase 1 ships)

Not part of this plan; listed so nobody thinks they were forgotten. Each will get its own plan document once `strategy.py` is final.

1. **Python live bot** — `rsi_fvg/live/mt5_broker.py`, `rsi_fvg/live/bot.py`, `config/live.yaml`, `scripts/run_live.py` (spec §4.1–4.2). Replay-per-bar over `lookback_bars`; `--dry-run`; hedging-mode check; TP re-set from real fill. **Requires the user to log into a demo account first** — current terminal is on a real cent account.
2. **MQL5 EA** — `mql5/RsiFvgEA.mq5` (spec §4.3), line-by-line port of `strategy.py` with manual Wilder ATR and strict-pivot loop; `ExportDebug` CSV; `scripts/compare_mt5.py` parity (RSI/ATR `< 1e-6`, signal bars 100%).
3. **Pine Script v6** — `pine/rsi_fvg_strategy.pine` (spec §5), `Block opposite while in trade`, exact-R exit re-arm, FVG boxes, alerts.
4. **Parity + README additions** — spec §6.3, known-divergence table (hedge, spread, tick model).

---

## Plan self-review (done at authoring time)

- **Spec coverage:** §2.1 → Task 2; §2.2 → Task 3; §2.3–2.6 → Task 4 (SL, priority order, `t > wait_start`, replay-safe statelessness); §2.7 → Tasks 5 & 6 (`oversized`, commission, slippage); §2.8 → Task 6 (`hedge|single`); §3.1–3.2 → file structure + module boundaries; §3.3–3.4 → Task 6; §3.5 → Task 7; §3.6 → Task 9; §3.7 → Task 8 (spec sidecar, cap warning); §3.8 → Task 1; §6.1 → tests in every task. §2.6 `rejected_stops_level` is a live-only rule → Phase 2. §4, §5, §6.2 (broker test), §6.3 → Phase 2 by design.
- **Type consistency:** `Signal` fields used in engine (`direction, variant, signal_bar, anchor_bar, sl_price, bars_in_wait`) match Task 4. `SymbolSpec` field names (`point, contract_size, min_lot, max_lot, lot_step`) match across Tasks 1/5/6/8. `TRADE_COLUMNS` includes `risk_usd` and `oversized`, used by metrics/report. `compute_metrics` keys used in `SPLIT_KEYS` and `_summary_md` all exist in Task 7's dict.
- **Placeholders:** none — every step has code or an exact command with expected output.
