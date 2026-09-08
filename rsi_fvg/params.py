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
