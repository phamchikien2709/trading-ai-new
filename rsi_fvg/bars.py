from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Bars:
    """OHLC arrays. Prices are BID. time = epoch seconds (int64)."""

    time: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    spread: np.ndarray | None = None

    def __len__(self) -> int:
        return int(self.close.shape[0])

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "Bars":
        t = df["time"]
        if pd.api.types.is_datetime64_any_dtype(t):
            time = (t.astype("int64") // 1_000_000_000).to_numpy(dtype=np.int64)
        else:
            time = t.to_numpy(dtype=np.int64)
        spread = df["spread"].to_numpy(dtype=np.int64) if "spread" in df.columns else None
        return cls(
            time=time,
            open=df["open"].to_numpy(dtype=np.float64),
            high=df["high"].to_numpy(dtype=np.float64),
            low=df["low"].to_numpy(dtype=np.float64),
            close=df["close"].to_numpy(dtype=np.float64),
            spread=spread,
        )

    def slice(self, start: int, stop: int) -> "Bars":
        return Bars(
            time=self.time[start:stop],
            open=self.open[start:stop],
            high=self.high[start:stop],
            low=self.low[start:stop],
            close=self.close[start:stop],
            spread=None if self.spread is None else self.spread[start:stop],
        )

    def datetimes(self) -> pd.DatetimeIndex:
        return pd.to_datetime(self.time, unit="s", utc=True)
