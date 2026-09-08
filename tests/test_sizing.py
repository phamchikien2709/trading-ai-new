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
