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
