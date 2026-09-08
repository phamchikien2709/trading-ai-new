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
