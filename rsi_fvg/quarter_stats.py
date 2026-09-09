"""Sáu phép đo tiền đề của Quarterly Theory, cộng bộ máy permutation.

Spec: docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md §4.

Mọi thống kê nhận vào BẢNG CHU KỲ (một dòng mỗi chu kỳ, cột q1_*..q4_*) và trả
về dict tên->số, để bộ chạy permutation so lưới thật với lưới null một cách đồng
nhất mà không cần biết thống kê đó đo gì.

Đánh số: cột `q1_` là Q1 CỦA LÝ THUYẾT, tức `q_index` 0. Nếu đặt `q0_` thì mọi
công thức sẽ đọc lệch một bậc so với spec.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .bars import Bars
from .quarters import QuarterLabels

MIN_BARS_PER_QUARTER = 3
_FIELDS = ("open", "high", "low", "close", "n")


def aggregate_cycles(bars: Bars, labels: QuarterLabels,
                     min_bars: int = MIN_BARS_PER_QUARTER) -> pd.DataFrame:
    """Gộp bar thành một dòng mỗi chu kỳ với OHLC của cả bốn quarter.

    Loại CẢ chu kỳ nếu bất kỳ quarter nào thiếu hoặc có ít hơn `min_bars` bar
    (spec §4.2). Luật này phải áp y nguyên cho lưới thật và mọi lưới null — chỉ
    áp một bên thì cỡ mẫu lệch và phép so sánh vô nghĩa.

    `first`/`last` cho open/close là đúng vì `bars` theo thứ tự thời gian và
    groupby giữ thứ tự trong nhóm.
    """
    df = pd.DataFrame({
        "cycle_id": labels.cycle_id,
        "q": labels.q_index,
        "open": bars.open, "high": bars.high,
        "low": bars.low, "close": bars.close,
    })
    agg = df.groupby(["cycle_id", "q"], sort=True).agg(
        open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last"), n=("close", "size"),
    )
    wide = agg.unstack("q")
    wide.columns = [f"q{int(q) + 1}_{field}" for field, q in wide.columns]
    wide = wide.reindex(columns=[f"q{q}_{f}" for q in (1, 2, 3, 4) for f in _FIELDS])

    keep = np.ones(len(wide), dtype=bool)
    for q in (1, 2, 3, 4):
        n = wide[f"q{q}_n"].to_numpy(dtype="float64")
        keep &= np.isfinite(n) & (n >= min_bars)
    return wide.loc[keep]
