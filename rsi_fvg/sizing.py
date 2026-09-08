"""Risk-based lot sizing (spec §2.7)."""
from __future__ import annotations

import math

from .params import SymbolSpec


def lots_for_risk(equity: float, risk_pct: float, sl_dist: float,
                  spec: SymbolSpec) -> tuple[float, bool, bool]:
    """Lots that risk `risk_pct` of `equity` over `sl_dist`, floored to the lot step.

    Returns ``(lots, oversized, capped)``:
    - ``oversized`` — the raw size was below ``min_lot`` and was raised to it, so the trade
      risks MORE than `risk_pct`.
    - ``capped`` — the raw size exceeded ``max_lot`` and was clamped down, so the trade
      risks LESS than `risk_pct`. Both flags travel with the trade log; a run where many
      trades are capped is not the strategy the risk settings describe.
    """
    if sl_dist <= 0:
        raise ValueError(f"sl_dist must be > 0, got {sl_dist}")
    risk_usd = equity * risk_pct / 100.0
    raw = risk_usd / (sl_dist * spec.contract_size)
    steps = math.floor(raw / spec.lot_step + 1e-9)
    lots = steps * spec.lot_step
    oversized = False
    if lots < spec.min_lot:
        lots, oversized = spec.min_lot, True
    capped = lots > spec.max_lot
    if capped:
        lots = spec.max_lot
    return round(lots, 8), oversized, capped
