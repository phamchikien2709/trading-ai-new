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
