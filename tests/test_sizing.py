import math

import pytest

from rsi_fvg.params import SymbolSpec
from rsi_fvg.sizing import lots_for_risk

SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0, min_lot=0.01, max_lot=200.0, lot_step=0.01)


def test_basic_floor_to_step():
    lots, oversized, capped = lots_for_risk(10_000, 1.0, 10.2, SPEC)   # 100 / 10.2 = 9.8039
    assert lots == pytest.approx(9.80) and not oversized and not capped


def test_contract_size_scales():
    spec = SymbolSpec(name="X", point=0.01, digits=2, contract_size=100.0, min_lot=0.01, max_lot=100.0, lot_step=0.01)
    lots, _, _ = lots_for_risk(10_000, 1.0, 5.0, spec)   # 100 / (5*100) = 0.2
    assert lots == pytest.approx(0.20)


def test_min_lot_oversized_flag():
    lots, oversized, capped = lots_for_risk(100, 1.0, 500.0, SPEC)   # 1 / 500 = 0.002 -> below min
    assert lots == 0.01 and oversized and not capped


def test_max_lot_clamp_sets_capped_flag():
    lots, oversized, capped = lots_for_risk(10_000_000, 1.0, 1.0, SPEC)   # 100000 lots -> clamp
    assert lots == 200.0 and not oversized and capped


def test_exactly_max_lot_is_not_capped():
    lots, oversized, capped = lots_for_risk(20_000, 1.0, 1.0, SPEC)   # 200 lots exactly
    assert lots == 200.0 and not oversized and not capped


def test_invalid_sl_dist_raises():
    with pytest.raises(ValueError):
        lots_for_risk(10_000, 1.0, 0.0, SPEC)


def test_floor_epsilon_does_not_lose_a_step():
    # Regression test for floating-point floor edge case (plan requirement).
    # The epsilon (1e-9) in sizing.py:14 prevents loss of a step when raw/lot_step
    # lands just below an integer due to float representation.
    # Example: raw=9.7999999999902, raw/0.01=979.99999999902 (just below 980).
    # Without epsilon: floor(979.99999...) = 979 (WRONG, loses one lot).
    # With epsilon: floor(979.99999... + 1e-9) = floor(980) = 980 (CORRECT).
    # This test verifies the epsilon closes the gap for such floating-point edge cases.

    # Construct inputs to produce raw just below a step boundary.
    # Using equity=9800, risk_pct=0.1, contract_size=1.0 gives risk_usd=9.8.
    # Set sl_dist = 1/(1-1e-12) ≈ 1.000000000001 to nudge raw just below 9.8.
    # Result: raw ≈ 9.7999999999902, so raw/lot_step ≈ 979.99999999902 < 980.
    equity = 9800.0
    risk_pct = 0.1
    sl_dist = 1.0 / (1.0 - 1e-12)
    contract_size = 1.0

    # Verify the computation produces the edge case: floor without epsilon loses a step.
    risk_usd = equity * risk_pct / 100.0
    raw = risk_usd / (sl_dist * contract_size)
    assert math.floor(raw / SPEC.lot_step) == 979, "Edge case not constructed (floor should be 979)"

    # Verify the epsilon in sizing.py lifts it to 980.
    assert math.floor(raw / SPEC.lot_step + 1e-9) == 980, "Epsilon should lift 979.9999... to 980"

    # Now verify the function handles it correctly by returning 9.80 lots.
    lots, oversized, capped = lots_for_risk(equity, risk_pct, sl_dist, SPEC)
    assert lots == pytest.approx(9.80), f"Expected 9.80, got {lots}"
    assert not oversized, f"Expected not oversized, got {oversized}"
    assert not capped
