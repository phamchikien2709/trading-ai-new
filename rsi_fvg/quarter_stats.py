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
from .quarters import TIERS, QuarterLabels, label_quarters

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


def stat_q1_predicts_q2(w: pd.DataFrame) -> dict[str, float]:
    """④ Spearman(range Q1, range Q2). Lý thuyết dự đoán ÂM.

    "Q1 dictates the quarters which follow": Q1 hẹp báo Q2 giãn, Q1 đã giãn báo
    Q2 co. Dùng Spearman chứ không Pearson vì range có đuôi dày và ta chỉ quan
    tâm quan hệ đơn điệu. `pandas.Series.corr` có sẵn method này, không cần scipy.
    """
    if len(w) < 2:
        return {"spearman_r1_r2": float("nan"), "n": float(len(w))}
    r1 = w["q1_high"] - w["q1_low"]
    r2 = w["q2_high"] - w["q2_low"]
    rho = r1.corr(r2, method="spearman")
    return {"spearman_r1_r2": float(rho), "n": float(len(w))}


def stat_true_open(w: pd.DataFrame) -> dict[str, float]:
    """⑤ True Open = open của bar đầu Q2 (spec §2.4 của spec indicator).

    Đo P(cuối chu kỳ cùng phía True Open với lúc bắt đầu Q3). Trên 0.5 là dấu
    hiệu bền hướng, dưới 0.5 là hồi quy về trung bình — lệch khỏi 0.5 theo hướng
    nào cũng là thông tin.

    Hoà (giá bằng đúng True Open) bị LOẠI, không gán về một phía (spec §4.2).
    np.sign(0) là 0 nên nếu không loại thì hoà sẽ rơi vào nhánh "khác phía" một
    cách tuỳ ý.
    """
    to = w["q2_open"].to_numpy()
    a = w["q3_open"].to_numpy() - to
    b = w["q4_close"].to_numpy() - to
    keep = (a != 0) & (b != 0)
    same = np.sign(a[keep]) == np.sign(b[keep])
    return {"true_open_persistence": _mean_or_nan(same),
            "n": float(keep.sum()), "ties": float((~keep).sum())}


def stat_reclaim_q3(w: pd.DataFrame) -> dict[str, float]:
    """⑥ Sau khi Q2 sweep biên Q1 rồi ĐÓNG LẠI bên trong, Q3 có đi ngược không.

    Đây là thesis sẽ thành luật vào lệnh ở Phase 2, và `reclaim_pooled_against`
    là con số duy nhất mà luật kết luận §7 dùng.

      Sweep lên  + reclaim: q2_high > q1_high VÀ q2_close < q1_high -> P(Q3 giảm)
      Sweep xuống + reclaim: q2_low  < q1_low  VÀ q2_close > q1_low  -> P(Q3 tăng)
      Pooled: gộp hai tập, P(Q3 đi NGƯỢC hướng sweep)

    Hai luật loại, cả hai đều có ý:
      - Hoà bị loại (spec §4.2): q2_close bằng đúng biên, hoặc Q3 đóng bằng mở.
        Dùng < và > thay cho <= và >= là cách loại hoà ở biên.
      - Chu kỳ sweep CẢ HAI phía bị loại khỏi cả ba con số. Spec không nói tới
        trường hợp này; lý thuyết không đưa ra kỳ vọng hướng nào cho nó, và đưa
        vào pooled sẽ đếm một chu kỳ hai lần với hai kỳ vọng trái nhau.
    """
    q1h = w["q1_high"].to_numpy()
    q1l = w["q1_low"].to_numpy()
    q2h = w["q2_high"].to_numpy()
    q2l = w["q2_low"].to_numpy()
    q2c = w["q2_close"].to_numpy()
    q3_dir = np.sign(w["q3_close"].to_numpy() - w["q3_open"].to_numpy())

    swept_up = (q2h > q1h) & (q2c < q1h)
    swept_dn = (q2l < q1l) & (q2c > q1l)
    both = swept_up & swept_dn
    live = q3_dir != 0                       # Q3 phẳng là hoà, loại
    up = swept_up & ~both & live
    dn = swept_dn & ~both & live

    against_up = q3_dir[up] < 0
    against_dn = q3_dir[dn] > 0
    pooled = np.concatenate([against_up, against_dn])
    return {
        "reclaim_up_p_q3_down": _mean_or_nan(against_up), "n_up": float(up.sum()),
        "reclaim_dn_p_q3_up": _mean_or_nan(against_dn), "n_dn": float(dn.sum()),
        "reclaim_pooled_against": _mean_or_nan(pooled), "n_pooled": float(pooled.size),
        "n_both_sides": float(both.sum()),
    }


OFFSET_EXCLUDE = 600

STATS = {
    "sweep": stat_sweep,
    "range_by_index": stat_range_by_index,
    "displacement_by_index": stat_displacement_by_index,
    "q1_predicts_q2": stat_q1_predicts_q2,
    "true_open": stat_true_open,
    "reclaim_q3": stat_reclaim_q3,
}


def make_offsets(tier: str, bar_seconds: int, shifts: int, seed: int) -> np.ndarray:
    """Offset neo cho mô hình null (spec §4.1).

    Ba quyết định, cả ba đều có lý do:

    1. SNAP về bội số `bar_seconds`. Lưới thật có biên trùng bar chính xác
       (18:00, 19:30 đều là bội của 5 phút). Nếu lưới giả rơi giữa nến thì nó bị
       handicap về hình học, và lưới thật trông tốt hơn CHỈ VÌ nó căn lề — một
       bias nghiêng về phía lý thuyết.
    2. Lấy từ [0, 4L) tức TRỌN chu kỳ, không phải [0, L). Dịch đúng L không đổi
       biên mà chỉ ĐỔI TÊN quarter, và ①②③⑥ đều phụ thuộc chỉ số quarter nên
       phép đổi tên đó là thông tin.
    3. Loại lân cận 0 để lưới giả không trùng lưới thật.

    Số offset khả dụng là (4L / bar_seconds) trừ lân cận 0, nên tầng q90 chỉ có
    69 lưới null dù xin bao nhiêu. Hàm trả về ít hơn `shifts` khi hết mốc — KHÔNG
    lặp lại mốc, vì mốc trùng sẽ làm phân phối null hẹp giả tạo.
    """
    cycle = 4 * TIERS[tier]
    grid = np.arange(0, cycle, bar_seconds, dtype="int64")
    ok = (grid >= OFFSET_EXCLUDE) & (grid <= cycle - OFFSET_EXCLUDE)
    candidates = grid[ok]
    if candidates.size <= shifts:
        return candidates
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(candidates, size=shifts, replace=False))


def run_grid(bars: Bars, tier: str, anchor_offset: int = 0,
             min_bars: int = MIN_BARS_PER_QUARTER) -> dict[str, float]:
    """Chạy cả sáu thống kê trên một lưới. Khoá dạng "<stat>.<đại lượng>"."""
    labels = label_quarters(bars.time, tier, anchor_offset)
    w = aggregate_cycles(bars, labels, min_bars)
    out: dict[str, float] = {}
    for name, fn in STATS.items():
        for key, value in fn(w).items():
            out[f"{name}.{key}"] = value
    return out


def run_null(bars: Bars, tier: str, offsets: np.ndarray,
             min_bars: int = MIN_BARS_PER_QUARTER) -> pd.DataFrame:
    """Một dòng mỗi lưới null."""
    rows = []
    for off in np.asarray(offsets, dtype="int64"):
        row = {"anchor_offset": int(off)}
        row.update(run_grid(bars, tier, int(off), min_bars))
        rows.append(row)
    return pd.DataFrame(rows)


def percentile_of(real: float, null: np.ndarray) -> float:
    """Phần trăm lưới null có giá trị NHỎ HƠN lưới thật.

    100 nghĩa là lưới thật cao hơn mọi lưới null. NaN của null bị bỏ (một lưới
    null có thể loại hết chu kỳ và cho NaN); NaN của `real` cho NaN.
    """
    null = np.asarray(null, dtype="float64")
    null = null[np.isfinite(null)]
    if null.size == 0 or not np.isfinite(real):
        return float("nan")
    return 100.0 * float(np.mean(null < real))
