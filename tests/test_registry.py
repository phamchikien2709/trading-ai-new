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
