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


QUARTERS = (1, 2, 3, 4)


def _mean_or_nan(x: np.ndarray) -> float:
    return float(np.mean(x)) if x.size else float("nan")


def stat_sweep(w: pd.DataFrame) -> dict[str, float]:
    """① Tỷ lệ chu kỳ mà Q2 vượt ra ngoài range của Q1 (Defining Range).

    So sánh là > và <, không phải >= và <=: chạm đúng biên không phải sweep.
    """
    up = w["q2_high"].to_numpy() > w["q1_high"].to_numpy()
    dn = w["q2_low"].to_numpy() < w["q1_low"].to_numpy()
    return {"sweep_rate": _mean_or_nan(up | dn), "n": float(len(w))}


def stat_range_by_index(w: pd.DataFrame) -> dict[str, float]:
    """② Range trung bình theo chỉ số quarter. Lý thuyết nói Q1 nhỏ nhất."""
    out: dict[str, float] = {}
    for q in QUARTERS:
        r = (w[f"q{q}_high"] - w[f"q{q}_low"]).to_numpy()
        out[f"range_q{q}"] = _mean_or_nan(r)
    mean_all = float(np.mean([out[f"range_q{q}"] for q in QUARTERS]))
    out["range_q1_ratio"] = (out["range_q1"] / mean_all
                             if mean_all and np.isfinite(mean_all) else float("nan"))
    out["n"] = float(len(w))
    return out


def stat_displacement_by_index(w: pd.DataFrame) -> dict[str, float]:
    """③ |close - open| trung bình theo chỉ số quarter. Lý thuyết nói Q3 lớn nhất."""
    out: dict[str, float] = {}
    for q in QUARTERS:
        d = np.abs((w[f"q{q}_close"] - w[f"q{q}_open"]).to_numpy())
        out[f"disp_q{q}"] = _mean_or_nan(d)
    mean_all = float(np.mean([out[f"disp_q{q}"] for q in QUARTERS]))
    out["disp_q3_ratio"] = (out["disp_q3"] / mean_all
                            if mean_all and np.isfinite(mean_all) else float("nan"))
    out["n"] = float(len(w))
    return out
