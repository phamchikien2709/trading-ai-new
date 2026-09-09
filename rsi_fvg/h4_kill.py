"""Phép đo "nến H4 bị kill hai đầu".

Spec: docs/superpowers/specs/2026-09-09-h4-kill-both-ends-study-design.md §4, §5.

Module này biết về GIÁ; `h4_grid.py` biết về THỜI GIAN. Mọi đại lượng là hàm
thuần của bảng dòng mà `scan_kills` trả về, nên bộ chạy null so lưới thật với
lưới null một cách đồng nhất mà không cần biết đại lượng đó đo gì — cùng giao ước
với `quarter_stats.STATS`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .bars import Bars
from .h4_grid import N_SLOTS, H4Labels

H_MAX_MIN = 1440
HORIZONS_MIN = (60, 120, 240, 480, 720, 1200, 1440)
STD_HORIZON_MIN = 720
MAX_GAP_DAYS = 4

# Bộ cột đầy đủ mà `scan_kills` cam kết trả về — khai báo MỘT LẦN và dùng cho
# cả việc dựng từng dòng lẫn frame rỗng, để hai thứ không thể trôi lệch nhau.
# Task 4/6 đọc `rows[rows["slot"] == s]` trên kết quả này; nếu `recs` rỗng thì
# `pd.DataFrame(recs)` trần trụi cho ra frame KHÔNG CỘT NÀO CẢ và những dòng đó
# sẽ KeyError. Task 7 chạy 200 lưới null dịch offset, và một offset bệnh lý có
# thể xoá hết ngày — nên trường hợp rỗng này chắc chắn sẽ xảy ra, không phải
# giả thuyết suông.
COLUMNS = (
    "day_num", "date", "year", "slot", "cand_high", "cand_low", "range_usd",
    "day_atr", "rel_range", "w_from", "w_to", "w_bars", "w_hours", "gap_days",
    "crosses_weekend", "h_avail", "t_up", "t_dn", "k_up", "k_dn", "exc_up", "exc_dn",
)


def scan_kills(bars: Bars, labels: H4Labels, days: pd.DataFrame,
               bar_seconds: int, h_max_min: int = H_MAX_MIN,
               max_gap_days: int = MAX_GAP_DAYS) -> pd.DataFrame:
    """Một dòng mỗi (ngày giao dịch, slot) với bốn nguyên thuỷ của spec §4.1.

    `t_up`/`t_dn` tính bằng BAR chứ không bằng phút: trên M1 hai cái trùng nhau,
    trên M5/H1 thì không, và lưu bằng bar thì hàm chạy đúng trên mọi khung.
    Đếm bar cũng chính là "phút thị trường mở" mà spec §4.2 đòi — cuối tuần và
    khe nghỉ tự động bị nhảy qua, nên sáu slot so được với nhau.

    Cửa sổ ① mô tả bằng `w_from`/`w_to` (bù bar so với bar cuối của nến), không
    bằng `w_bars` một mình: 163 bar Thứ Bảy lạc (spec §11 mục 10) nằm GIỮA thứ
    Sáu và ngày giao dịch thật kế tiếp, nên với những dòng đó cửa sổ không bắt
    đầu ngay tại `end + 1`. Luật: `killed ⇔ w_from <= t <= w_to`.

    Dòng có cửa sổ ① bị cắt ở mép dữ liệu bị LOẠI, không báo là "không bị kill"
    (spec §8 mục 9) — đó là look-ahead ngược và nó dìm tỉ lệ kill ở cuối mẫu.
    Dòng có cửa sổ ① đủ nhưng quét horizon bị cắt thì GIỮ, và `h_avail` ghi số
    bar thực có để đại lượng theo horizon tự lọc.

    Trả về đủ bộ cột `COLUMNS` NGAY CẢ KHI không dòng nào sống sót (xem docstring
    của `COLUMNS`).
    """
    n = len(bars)
    h_max = int(h_max_min * 60 // bar_seconds)
    hi_all, lo_all = bars.high, bars.low

    key = labels.day_num * N_SLOTS + labels.slot
    if not np.all(np.diff(key) >= 0):
        raise ValueError("nhãn (ngày, slot) phải không giảm theo thời gian; "
                         "bars chưa sort theo time?")

    pos = np.arange(n)
    by_key = pd.DataFrame({"k": key, "i": pos}).groupby("k")["i"].agg(["min", "max"])
    by_day = pd.DataFrame({"d": labels.day_num, "i": pos}).groupby("d")["i"].agg(["min", "max"])

    kept = days.index.to_numpy()
    recs = []
    for p, d in enumerate(kept):
        d = int(d)
        for s in range(N_SLOTS):
            k = d * N_SLOTS + s
            if k not in by_key.index:
                continue
            end = int(by_key.at[k, "max"])

            if s < N_SLOTS - 1:
                w_from, w_to = 1, int(by_day.at[d, "max"]) - end
                gap_days = 0
            else:
                if p + 1 >= len(kept):
                    continue
                d2 = int(kept[p + 1])
                gap_days = d2 - d
                if gap_days > max_gap_days:
                    continue
                w_from = int(by_day.at[d2, "min"]) - end
                w_to = int(by_day.at[d2, "max"]) - end
            if w_to < w_from or end + w_to >= n:
                continue                      # cửa sổ ① rỗng hoặc bị cắt -> LOẠI

            ch = float(days.at[d, f"s{s}_high"])
            cl = float(days.at[d, f"s{s}_low"])
            scan = max(h_max, w_to)
            seg_hi = hi_all[end + 1: end + 1 + scan]
            seg_lo = lo_all[end + 1: end + 1 + scan]
            up = np.flatnonzero(seg_hi > ch)
            dn = np.flatnonzero(seg_lo < cl)
            t_up = float(up[0] + 1) if up.size else float("nan")
            t_dn = float(dn[0] + 1) if dn.size else float("nan")

            k_up = bool(w_from <= t_up <= w_to)   # NaN so sánh -> False
            k_dn = bool(w_from <= t_dn <= w_to)
            win_hi = hi_all[end + w_from: end + w_to + 1]
            win_lo = lo_all[end + w_from: end + w_to + 1]
            atr = float(days.at[d, "day_atr"])
            rng = ch - cl
            rec = {
                "day_num": d, "date": days.at[d, "date"],
                "year": int(pd.Timestamp(days.at[d, "date"]).year), "slot": s,
                "cand_high": ch, "cand_low": cl, "range_usd": rng,
                "day_atr": atr, "rel_range": rng / atr if atr > 0 else float("nan"),
                "w_from": w_from, "w_to": w_to, "w_bars": w_to - w_from + 1,
                "w_hours": (w_to - w_from + 1) * bar_seconds / 3600.0,
                "gap_days": gap_days, "crosses_weekend": gap_days > 1,
                "h_avail": min(h_max, n - 1 - end),
                "t_up": t_up, "t_dn": t_dn, "k_up": k_up, "k_dn": k_dn,
                "exc_up": float(win_hi.max() - ch) if k_up else float("nan"),
                "exc_dn": float(cl - win_lo.min()) if k_dn else float("nan"),
            }
            recs.append(rec)
    return pd.DataFrame(recs, columns=list(COLUMNS))
