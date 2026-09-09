import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rsi_fvg.bars import Bars  # noqa: E402


def make_bars(o, h, l, c, start=1_700_000_000, step=300, spread=None):
    """Build Bars from python lists. step = seconds per bar (300 = M5)."""

    n = len(c)
    assert len(o) == len(h) == len(l) == n
    time = np.arange(start, start + step * n, step, dtype=np.int64)
    return Bars(
        time=time,
        open=np.asarray(o, dtype=np.float64),
        high=np.asarray(h, dtype=np.float64),
        low=np.asarray(l, dtype=np.float64),
        close=np.asarray(c, dtype=np.float64),
        spread=None if spread is None else np.asarray(spread, dtype=np.int64),
    )


def bars_from_closes(closes, wick=0.5, start=1_700_000_000, step=300):
    """Bars where open = previous close, high/low = body ± wick."""
    closes = list(map(float, closes))
    opens = [closes[0]] + closes[:-1]
    highs = [max(o, c) + wick for o, c in zip(opens, closes)]
    lows = [min(o, c) - wick for o, c in zip(opens, closes)]
    return make_bars(opens, highs, lows, closes, start=start, step=step)


def epoch_for_ny(y, m, d, hh, mm=0, ss=0):
    """Epoch seconds mà server_to_ny sẽ đọc thành đúng giờ New York này.

    `Bars.time` là instant UTC thật — đã kiểm bằng dữ liệu, xem
    rsi_fvg/quarters.py và spec §2. Nên đường đi ngược chỉ là: giờ NY -> UTC.
    """
    ny = pd.Timestamp(year=y, month=m, day=d, hour=hh, minute=mm, second=ss,
                      tz="America/New_York")
    return int(ny.timestamp())


@pytest.fixture
def mk_bars():
    return make_bars


@pytest.fixture
def mk_closes():
    return bars_from_closes


@pytest.fixture
def mk_epoch_ny():
    return epoch_for_ny
