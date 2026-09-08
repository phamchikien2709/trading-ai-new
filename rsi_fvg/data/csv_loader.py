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
