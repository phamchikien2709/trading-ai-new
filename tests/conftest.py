import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rsi_fvg.bars import Bars  # noqa: E402


def make_bars(open_, high, low, close, start=1_700_000_000, step=300, spread=None):
    """Build Bars from python lists. step = seconds per bar (300 = M5)."""
    n = len(close)
    assert len(open_) == len(high) == len(low) == n
    time = np.arange(start, start + step * n, step, dtype=np.int64)
    return Bars(
        time=time,
        open=np.asarray(open_, dtype=np.float64),
        high=np.asarray(high, dtype=np.float64),
        low=np.asarray(low, dtype=np.float64),
        close=np.asarray(close, dtype=np.float64),
        spread=None if spread is None else np.asarray(spread, dtype=np.int64),
    )


def bars_from_closes(closes, wick=0.5, start=1_700_000_000, step=300):
    """Bars where open = previous close, high/low = body ± wick."""
    closes = list(map(float, closes))
    opens = [closes[0]] + closes[:-1]
    highs = [max(o, c) + wick for o, c in zip(opens, closes)]
    lows = [min(o, c) - wick for o, c in zip(opens, closes)]
    return make_bars(opens, highs, lows, closes, start=start, step=step)


@pytest.fixture
def mk_bars():
    return make_bars


@pytest.fixture
def mk_closes():
    return bars_from_closes
