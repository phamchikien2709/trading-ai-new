import numpy as np
import pandas as pd

from rsi_fvg.bars import Bars


def test_from_dataframe_with_epoch_seconds():
    df = pd.DataFrame({"time": [0, 300, 600], "open": [1, 2, 3.0], "high": [2, 3, 4.0],
                       "low": [0, 1, 2.0], "close": [1.5, 2.5, 3.5], "spread": [10, 11, 12]})
    b = Bars.from_dataframe(df)
    assert len(b) == 3
    assert b.time.dtype == np.int64 and b.time[1] == 300
    assert b.close.dtype == np.float64
    assert b.spread is not None and b.spread[2] == 12


def test_from_dataframe_with_datetime():
    df = pd.DataFrame({"time": pd.to_datetime([0, 300], unit="s", utc=True),
                       "open": [1, 2.0], "high": [2, 3.0], "low": [0, 1.0], "close": [1, 2.0]})
    b = Bars.from_dataframe(df)
    assert list(b.time) == [0, 300]
    assert b.spread is None


def test_slice(mk_closes):
    b = mk_closes([1, 2, 3, 4, 5])
    s = b.slice(1, 3)
    assert len(s) == 2 and list(s.close) == [2.0, 3.0]
