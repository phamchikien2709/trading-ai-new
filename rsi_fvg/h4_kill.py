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
#
# Tên cột thôi CHƯA ĐỦ: `pd.DataFrame([], columns=COLUMNS)` cho đủ 22 cột nhưng
# MỌI cột đều dtype `object` khi rỗng, khác hẳn dtype thật của nhánh có dữ liệu.
# `np.isfinite()` trên cột `object` ném `TypeError`; lọc boolean kiểu
# `rows[~rows["crosses_weekend"]]` trên cột `object` không ném lỗi mà lặng lẽ
# trả về frame KHÔNG CỘT NÀO — tái diễn đúng KeyError mà COLUMNS được lập ra để
# chặn, một bước xử lý sau đó. Nên dtype phải được khai báo cùng với tên cột,
# và cả hai nhánh (rỗng/không rỗng) phải ép qua CÙNG một `DTYPES` để không thể
# trôi lệch nhau — đây là điều khiến tuyên bố "hai đường code không thể trôi
# lệch nhau" ở trên đúng thật (tên cột LẪN dtype), chứ không chỉ đúng cho tên.
COLUMNS = (
    "day_num", "date", "year", "slot", "cand_high", "cand_low", "range_usd",
    "day_atr", "rel_range", "w_from", "w_to", "w_bars", "w_hours", "gap_days",
    "crosses_weekend", "h_avail", "t_up", "t_dn", "k_up", "k_dn", "exc_up", "exc_dn",
)

# int64: đếm được, không NaN. bool: cờ. float64: mang NaN được (t_up/t_dn/exc_up/
# exc_dn khi không kill; rel_range/day_atr khi ATR chưa đủ dữ liệu khởi động).
# datetime64[ns]: ngày lịch của `date`.
DTYPES = {
    "day_num": "int64", "date": "datetime64[ns]", "year": "int64", "slot": "int64",
    "cand_high": "float64", "cand_low": "float64", "range_usd": "float64",
    "day_atr": "float64", "rel_range": "float64",
    "w_from": "int64", "w_to": "int64", "w_bars": "int64", "w_hours": "float64",
    "gap_days": "int64", "crosses_weekend": "bool", "h_avail": "int64",
    "t_up": "float64", "t_dn": "float64", "k_up": "bool", "k_dn": "bool",
    "exc_up": "float64", "exc_dn": "float64",
}


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

    Trả về đủ bộ cột `COLUMNS`, đúng dtype khai báo ở `DTYPES`, NGAY CẢ KHI
    không dòng nào sống sót (xem docstring của `COLUMNS`/`DTYPES`).
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
    # Một đường return DUY NHẤT cho cả hai nhánh (rỗng/không rỗng): ép dtype
    # qua DTYPES vô điều kiện, nên tên cột LẪN dtype không thể trôi lệch giữa
    # hai nhánh — xem ghi chú ở khai báo COLUMNS/DTYPES phía trên.
    return pd.DataFrame(recs, columns=list(COLUMNS)).astype(DTYPES)


def _mean_or_nan(x: np.ndarray) -> float:
    x = np.asarray(x)
    return float(np.mean(x)) if x.size else float("nan")


def _median_or_nan(s: pd.Series) -> float:
    return float(s.median()) if len(s) else float("nan")


def stat_kill_rate_window(rows: pd.DataFrame) -> dict[str, float]:
    """① Tỉ lệ kill trong cửa sổ ① — đúng đề bài của người dùng.

    `w_hours_s*` được trả ra cùng chỗ và KHÔNG phải trang trí: spec §4.2 cho
    thấy sáu slot nhận sáu độ dài cửa sổ khác nhau (4h đến 24h), nên một tỉ lệ
    kill in trần không so được giữa các slot. Ai đọc bảng này phải thấy ngay
    cửa sổ dài bao nhiêu.
    """
    out: dict[str, float] = {}
    for s in range(N_SLOTS):
        r = rows[rows["slot"] == s]
        ku = r["k_up"].to_numpy(dtype=bool)
        kd = r["k_dn"].to_numpy(dtype=bool)
        out[f"both_s{s}"] = _mean_or_nan(ku & kd)
        out[f"up_only_s{s}"] = _mean_or_nan(ku & ~kd)
        out[f"dn_only_s{s}"] = _mean_or_nan(~ku & kd)
        out[f"none_s{s}"] = _mean_or_nan(~ku & ~kd)
        out[f"n_s{s}"] = float(len(r))
        out[f"w_hours_s{s}"] = _median_or_nan(r["w_hours"])
    r5 = rows[(rows["slot"] == N_SLOTS - 1) & (~rows["crosses_weekend"])]
    out["both_s5_no_gap"] = _mean_or_nan(r5["k_up"].to_numpy(dtype=bool)
                                         & r5["k_dn"].to_numpy(dtype=bool))
    out["n_s5_no_gap"] = float(len(r5))
    return out


def stat_kill_rate_horizon(rows: pd.DataFrame, bar_seconds: int,
                           horizons_min=HORIZONS_MIN) -> dict[str, float]:
    """② Tỉ lệ kill tại horizon CHUNG — nhóm đối chứng công bằng.

    Ở một horizon cố định, độ dài cửa sổ không còn là biến gây nhiễu; chỉ còn độ
    rộng cây, và ③ xử lý phần đó.

    Dòng không đủ bar để trả lời một horizon bị loại KHỎI horizon đó (không tính
    là "không kill"): tính nó là không-kill là look-ahead ngược và sẽ dìm tỉ lệ
    ở cuối mẫu. So sánh với NaN cho False nên `t_up` NaN không bao giờ thành kill.
    """
    out: dict[str, float] = {}
    for h in horizons_min:
        hb = h * 60 // bar_seconds
        for s in range(N_SLOTS):
            r = rows[(rows["slot"] == s) & (rows["h_avail"] >= hb)]
            tu = r["t_up"].to_numpy(dtype="float64")
            td = r["t_dn"].to_numpy(dtype="float64")
            out[f"both_s{s}_h{h}"] = _mean_or_nan((tu <= hb) & (td <= hb))
            out[f"n_s{s}_h{h}"] = float(len(r))
    return out


def stat_kill_rate_standardized(rows: pd.DataFrame, bar_seconds: int,
                                horizon_min: int = STD_HORIZON_MIN,
                                n_deciles: int = 10) -> dict[str, float]:
    """③ Tỉ lệ kill CHUẨN HOÁ theo độ rộng — đại lượng mà luật §10 dùng.

    Tồn tại vì hai cây mà nghiên cứu hỏi là hai cây HẸP NHẤT trong sáu (spec
    §2.3a: range median 4,76 và 6,22 USD so với 13,20 của slot 4). Xác suất bị
    quét cả hai đầu là hàm giảm theo độ rộng, nên so sánh thô giữa các slot chủ
    yếu đang đo độ rộng, không đo hành vi.

    Chuẩn hoá trực tiếp: mỗi slot ra một số = trung bình tỉ lệ kill trong từng
    decile, lấy trọng số theo phân phối decile GỘP. Đọc là "nếu slot này có cùng
    phân phối độ rộng như trung bình sáu slot, tỉ lệ kill của nó là bao nhiêu".

    `deciles_used_s*` KHÔNG phải trang trí: một slot chuẩn hoá trên 4/10 decile
    thì con số của nó không so được với slot chuẩn hoá trên 10/10.

    `min_cell_n_s*` là tín hiệu ô thưa (spec §4.3 ③ bước 2: "báo bảng slot ×
    decile với n từng ô, để ô thưa lộ ra") ở dạng máy đọc được: n nhỏ nhất
    trong số các ô (decile) mà slot đó thực sự dùng. Không có nó,
    `deciles_used_s{k} == n_deciles` đọc như "chuẩn hoá đầy đủ", nhưng một ô
    trong số đó có thể chỉ có một quan sát và vẫn được gán trọng số gộp đầy đủ
    — đúng lỗ hổng mà bảng slot × decile của spec tồn tại để lộ ra. Bảng đầy đủ
    (60 ô) không thuộc `dict[str, float]` này; nó thuộc `summary.md` (task
    khác) — hàm này chỉ mang phần tối thiểu bộ chạy null cần: giá trị nhỏ nhất.

    Tính tại horizon CHUNG (mặc định 720 phút), không tại cửa sổ ①, vì ① có độ
    dài khác nhau giữa các slot nên không so được (spec §4.2).
    """
    hb = horizon_min * 60 // bar_seconds
    out: dict[str, float] = {}
    if rows.empty:
        for s in range(N_SLOTS):
            out[f"std_s{s}"] = out[f"raw_s{s}"] = float("nan")
            out[f"deciles_used_s{s}"] = out[f"n_s{s}"] = 0.0
            out[f"min_cell_n_s{s}"] = 0.0
        return out

    r = rows[(rows["h_avail"] >= hb) & np.isfinite(rows["rel_range"])].copy()
    if r.empty:
        for s in range(N_SLOTS):
            out[f"std_s{s}"] = out[f"raw_s{s}"] = float("nan")
            out[f"deciles_used_s{s}"] = out[f"n_s{s}"] = 0.0
            out[f"min_cell_n_s{s}"] = 0.0
        return out

    r["killed"] = ((r["t_up"].to_numpy(dtype="float64") <= hb)
                   & (r["t_dn"].to_numpy(dtype="float64") <= hb))
    r["dec"] = pd.qcut(r["rel_range"], n_deciles, labels=False, duplicates="drop")
    weights = r["dec"].value_counts(normalize=True)      # phân phối GỘP

    for s in range(N_SLOTS):
        rs = r[r["slot"] == s]
        out[f"raw_s{s}"] = _mean_or_nan(rs["killed"].to_numpy(dtype=bool))
        out[f"n_s{s}"] = float(len(rs))
        if rs.empty:
            out[f"std_s{s}"] = float("nan")
            out[f"deciles_used_s{s}"] = 0.0
            out[f"min_cell_n_s{s}"] = 0.0
            continue
        cell_n = rs.groupby("dec").size()
        by_dec = rs.groupby("dec")["killed"].mean()
        w = weights.reindex(by_dec.index)
        total = float(w.sum())
        out[f"std_s{s}"] = float((by_dec * w).sum() / total) if total > 0 else float("nan")
        out[f"deciles_used_s{s}"] = float(len(by_dec))
        out[f"min_cell_n_s{s}"] = float(cell_n.min())
    return out


def stat_context(rows: pd.DataFrame) -> dict[str, float]:
    """⑦ Bối cảnh. Không phải phát hiện, nhưng ③ và ⑤ không đọc được nếu thiếu."""
    out: dict[str, float] = {}
    for s in range(N_SLOTS):
        r = rows[rows["slot"] == s]
        out[f"range_usd_s{s}"] = _median_or_nan(r["range_usd"])
        out[f"rel_range_s{s}"] = _median_or_nan(r["rel_range"])
        out[f"day_atr_s{s}"] = _median_or_nan(r["day_atr"])
        out[f"n_s{s}"] = float(len(r))
    return out
