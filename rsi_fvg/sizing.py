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
