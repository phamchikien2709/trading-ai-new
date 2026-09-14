"""Phép đo "nến H4 bị kill hai đầu".

Spec: docs/superpowers/specs/2026-09-09-h4-kill-both-ends-study-design.md §4, §5.

Module này biết về GIÁ; `h4_grid.py` biết về THỜI GIAN. Mọi đại lượng là hàm
thuần của bảng dòng mà `scan_kills` trả về, nên bộ chạy null so lưới thật với
lưới null một cách đồng nhất mà không cần biết đại lượng đó đo gì — cùng giao ước
với `quarter_stats.STATS`.
"""
from __future__ import annotations

from functools import partial

import numpy as np
import pandas as pd

from .bars import Bars
from .h4_grid import N_SLOTS, H4Labels, aggregate_days, label_h4

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


def _std_prep(rows: pd.DataFrame, bar_seconds: int, horizon_min: int,
              n_deciles: int) -> pd.DataFrame | None:
    """Phần chung của ③: lọc theo horizon, gắn cờ `killed`, chia decile GỘP.

    Tồn tại như một hàm riêng vì HAI phía đọc cùng phép chia decile này: khoá
    `min_cell_n_s{k}` mà cổng §10 đọc, và bảng 60 ô mà `summary.md` in. Chia
    decile hai lần bằng hai đường code (dù cùng tham số) là cách để bảng và cổng
    trôi lệch nhau âm thầm — người đọc thấy ô dày trong khi cổng đọc ô mỏng.

    Trả `None` khi không còn dòng nào dùng được, để hai caller tự quyết định ca
    suy biến của mình.
    """
    if rows.empty:
        return None
    hb = horizon_min * 60 // bar_seconds
    r = rows[(rows["h_avail"] >= hb) & np.isfinite(rows["rel_range"])].copy()
    if r.empty:
        return None
    r["killed"] = ((r["t_up"].to_numpy(dtype="float64") <= hb)
                   & (r["t_dn"].to_numpy(dtype="float64") <= hb))
    r["dec"] = pd.qcut(r["rel_range"], n_deciles, labels=False, duplicates="drop")
    return r


def decile_cell_table(rows: pd.DataFrame, bar_seconds: int,
                      horizon_min: int = STD_HORIZON_MIN,
                      n_deciles: int = 10) -> pd.DataFrame:
    """Bảng (slot × decile) với `n` từng ô — spec §4.3 ③ bước 2: "để ô thưa lộ ra".

    Thuộc về BÁO CÁO, không thuộc `dict[str, float]` của bộ chạy null (60 ô ×
    200 lưới null là nhiễu, không phải thông tin). Nhưng nó không phải trang trí:
    `deciles_used_s{k} == 10` đọc như "chuẩn hoá đầy đủ" trong khi một ô trong
    mười có thể chỉ có một quan sát và vẫn mang trọng số gộp đầy đủ. Bảng này là
    thứ duy nhất cho người đọc thấy điều đó ở mọi ô, chứ không chỉ ô nhỏ nhất.

    Một dòng mỗi slot — CẢ SÁU, kể cả slot không có quan sát nào, vì "slot vắng
    mặt" là một kết quả và một bảng chỉ có bốn dòng đọc ra như thể chỉ có bốn
    slot tồn tại. Ô trống là 0, không phải NaN: đếm được thì không có NaN.
    """
    r = _std_prep(rows, bar_seconds, horizon_min, n_deciles)
    if r is None:
        return pd.DataFrame()
    cells = (r.groupby(["slot", "dec"]).size().unstack("dec", fill_value=0)
             .reindex(index=range(N_SLOTS), fill_value=0))
    cells.columns = [f"dec{int(c)}" for c in cells.columns]
    cells.index.name = "slot"
    return cells.astype("int64")


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
    out: dict[str, float] = {}
    r = _std_prep(rows, bar_seconds, horizon_min, n_deciles)
    if r is None:
        for s in range(N_SLOTS):
            out[f"std_s{s}"] = out[f"raw_s{s}"] = float("nan")
            out[f"deciles_used_s{s}"] = out[f"n_s{s}"] = 0.0
            out[f"min_cell_n_s{s}"] = 0.0
        return out

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
        # cell_n rỗng khi `rel_range` gộp là hằng số: `pd.qcut(..., duplicates=
        # "drop")` trả NaN cho MỌI dòng (không phải một bin duy nhất như trực
        # giác), rồi `groupby` mặc định bỏ nhóm NaN. Nhánh này không đi qua
        # `rs.empty` ở trên, nên nếu không chặn ở đây thì `min()` trả NaN —
        # và cổng §10 đọc khoá này bằng `< ngưỡng` sẽ im lặng không kích hoạt,
        # đúng vào ca thưa nhất có thể (0 decile dùng được).
        out[f"min_cell_n_s{s}"] = float(cell_n.min()) if len(cell_n) else 0.0
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


PCTS = (50, 75, 90, 95)


def _pct_block(x, prefix: str, out: dict[str, float]) -> None:
    """Phân vị + max + n cho một dãy. `max` là ĐÚNG MỘT điểm dữ liệu và báo cáo
    phải nói vậy mỗi lần in nó (spec §4.4)."""
    x = np.asarray(x, dtype="float64")
    x = x[np.isfinite(x)]
    for p in PCTS:
        out[f"{prefix}_p{p}"] = float(np.percentile(x, p)) if x.size else float("nan")
    out[f"{prefix}_max"] = float(x.max()) if x.size else float("nan")
    out[f"{prefix}_n"] = float(x.size)


def stat_kill_order(rows: pd.DataFrame) -> dict[str, float]:
    """④ Trong nhóm bị kill cả hai đầu: đầu nào trước, hay cùng một bar.

    Ô `same_bar` là phần KHÔNG xác định được ở độ phân giải đang dùng, và nó
    được báo ra chứ không gán về một phía. Trên H1 ô này sẽ lớn tới mức ④ vô
    dụng (spec §11 mục 3).
    """
    out: dict[str, float] = {}
    for s in range(N_SLOTS):
        r = rows[(rows["slot"] == s) & rows["k_up"] & rows["k_dn"]]
        tu = r["t_up"].to_numpy(dtype="float64")
        td = r["t_dn"].to_numpy(dtype="float64")
        out[f"up_first_s{s}"] = _mean_or_nan(tu < td)
        out[f"dn_first_s{s}"] = _mean_or_nan(td < tu)
        out[f"same_bar_s{s}"] = _mean_or_nan(tu == td)
        out[f"n_s{s}"] = float(len(r))
    return out


def stat_excursion_atr(rows: pd.DataFrame) -> dict[str, float]:
    """⑤ "Max range kill" nghĩa thứ nhất: giá đi tiếp bao xa QUÁ mốc.

    Chia `day_atr` nên không đơn vị và so được xuyên 9 năm — bắt buộc, vì range
    median của vàng gấp 13 lần từ 2017 tới 2026 (spec §2.3b). Dạng USD tách theo
    năm nằm ở `excursion_usd_by_year`, không vào null.
    """
    out: dict[str, float] = {}
    for s in range(N_SLOTS):
        r = rows[rows["slot"] == s]
        up = r[r["k_up"]]
        dn = r[r["k_dn"]]
        _pct_block(up["exc_up"] / up["day_atr"], f"exc_up_atr_s{s}", out)
        _pct_block(dn["exc_dn"] / dn["day_atr"], f"exc_dn_atr_s{s}", out)
    return out


def stat_killed_range_atr(rows: pd.DataFrame) -> dict[str, float]:
    """⑥ "Max range kill" nghĩa thứ hai: range của cây bị quét CẢ HAI đầu."""
    out: dict[str, float] = {}
    for s in range(N_SLOTS):
        r = rows[(rows["slot"] == s) & rows["k_up"] & rows["k_dn"]]
        _pct_block(r["rel_range"], f"killed_rel_range_s{s}", out)
    return out


def _by_year(rows: pd.DataFrame, specs) -> pd.DataFrame:
    """Bảng BÁO CÁO một dòng mỗi (năm, slot). Không vào null: dạng USD tách theo
    năm sinh hàng nghìn khoá và không có ý nghĩa khi so với lưới lệch mốc neo,
    vì lưới null cũng chạy trên cùng thị trường vàng."""
    recs = []
    if rows.empty:
        return pd.DataFrame(recs)
    for (y, s), r in rows.groupby(["year", "slot"], sort=True):
        rec: dict[str, float] = {"year": int(y), "slot": int(s), "n_rows": float(len(r))}
        for prefix, mask, col in specs:
            _pct_block(r.loc[mask(r), col], prefix, rec)
        recs.append(rec)
    return pd.DataFrame(recs)


def excursion_usd_by_year(rows: pd.DataFrame) -> pd.DataFrame:
    return _by_year(rows, [
        ("exc_up", lambda r: r["k_up"], "exc_up"),
        ("exc_dn", lambda r: r["k_dn"], "exc_dn"),
    ])


def killed_range_usd_by_year(rows: pd.DataFrame) -> pd.DataFrame:
    return _by_year(rows, [
        ("range_usd", lambda r: r["k_up"] & r["k_dn"], "range_usd"),
    ])


def build_stats(bar_seconds: int) -> dict:
    """Bảng đại lượng cho một khung thời gian.

    `horizon` và `standardized` cần `bar_seconds`; bind sẵn ở đây để bộ chạy
    null gọi mọi stat với đúng một tham số — cùng giao ước với
    `quarter_stats.STATS`, nên hai nghiên cứu đọc được cạnh nhau.

    Trả về dict MỚI mỗi lần gọi: default khả biến là footgun, một caller mutate
    nó sẽ đọc sang mọi caller khác (bài học đã ghi trong `quarter_stats.run_grid`).
    """
    return {
        "window": stat_kill_rate_window,
        "horizon": partial(stat_kill_rate_horizon, bar_seconds=bar_seconds),
        "standardized": partial(stat_kill_rate_standardized, bar_seconds=bar_seconds),
        "order": stat_kill_order,
        "excursion_atr": stat_excursion_atr,
        "killed_range_atr": stat_killed_range_atr,
        "context": stat_context,
    }


def run_grid(bars: Bars, bar_seconds: int, anchor_offset: int = 0,
             stats: dict | None = None, **agg_kw) -> tuple[dict, pd.DataFrame]:
    """Chạy một bộ đại lượng trên một lưới. Khoá dạng "<stat>.<đại lượng>".

    Trả cả bảng dòng vì đường thật cần nó cho `rows.csv` và cho hai bảng theo
    năm; đường null bỏ nó đi.

    `agg_kw` đi thẳng vào `aggregate_days`, nên luật loại là CÙNG MỘT hàm với
    cùng tham số ở cả hai đường — chỉ áp một bên thì cỡ mẫu lệch và phép so vô
    nghĩa (spec §3.3.3).
    """
    labels = label_h4(bars.time, anchor_offset)
    days = aggregate_days(bars, labels, bar_seconds, **agg_kw)
    rows = scan_kills(bars, labels, days, bar_seconds)
    table = build_stats(bar_seconds) if stats is None else stats
    out: dict[str, float] = {}
    for name, fn in table.items():
        for key, value in fn(rows).items():
            out[f"{name}.{key}"] = value
    return out, rows


def run_null(bars: Bars, bar_seconds: int, offsets: np.ndarray,
             stats: dict | None = None, **agg_kw) -> pd.DataFrame:
    """Một dòng mỗi lưới null. Offset sinh bằng
    `quarter_stats.make_offsets(..., cycle_seconds=h4_grid.DAY_SECONDS)`."""
    recs = []
    for off in np.asarray(offsets, dtype="int64"):
        rec: dict[str, float] = {"anchor_offset": int(off)}
        rec.update(run_grid(bars, bar_seconds, int(off), stats, **agg_kw)[0])
        recs.append(rec)
    return pd.DataFrame(recs)


# --------------------------------------------------------------------------
# Luật kết luận §10
#
# Nằm ở ĐÂY chứ không trong `scripts/study_h4_kill.py` vì đây là cổng kết luận
# của cả nghiên cứu, nên nó phải có test gọi hàm trực tiếp — mà mọi test script
# của repo chạy bằng `subprocess` và không gọi được hàm bên trong script. Script
# import bốn hằng số này và `verdict`; nó không định nghĩa lại cái nào.
# --------------------------------------------------------------------------

# Hai slot mà người dùng hỏi, và bốn slot đối chứng.
TARGET_SLOTS = (0, 5)
CONTROL_SLOTS = (1, 2, 3, 4)
VERDICT_PERCENTILE = 95.0
SLOT_NY = {0: "17:00-21:00 NY", 1: "21:00-01:00", 2: "01:00-05:00",
           3: "05:00-09:00", 4: "09:00-13:00", 5: "13:00-17:00 NY"}

VERDICT_KEY = "standardized.std_s{s}"
MIN_CELL_KEY = "standardized.min_cell_n_s{s}"

# Ô (slot × decile) mỏng hơn ngần này thì con số chuẩn hoá của slot đó không
# được dùng để mở cổng Phase 2. Lý do bằng số: mỗi ô mang trọng số gộp ~10%, và
# tỉ lệ kill ước lượng trên n quan sát có sai số chuẩn <= 0,5/sqrt(n). Với n=10
# đó là <= 16 điểm phần trăm × 10% = 1,6 điểm phần trăm đóng góp vào con số
# chuẩn hoá — đã cùng cỡ với khoảng cách giữa các slot mà cổng (a) đang so. Dưới
# đó thì một ô đơn lẻ tự quyết định phán quyết. Trên dữ liệu thật mỗi ô có ~230
# quan sát, nên ngưỡng này không cắt vào ca bình thường; nó chỉ chặn ca suy biến.
MIN_CELL_N = 10


def verdict(real: dict, stats: pd.DataFrame) -> tuple[bool, str]:
    """Luật §10, tính bằng máy — không để người đọc tự kết luận.

    HAI cổng, không phải ba: cổng Null B đã bị người dùng loại khỏi phạm vi
    (spec §5.3), và hệ quả của việc thiếu nó được in ngay trong phán quyết chứ
    không nhét vào cuối báo cáo.

    Chỉ xét slot 0 và slot 5. Một slot đối chứng vượt cả hai cổng cũng không mở
    gì: nghiên cứu hỏi về hai cây của người dùng, và để slot khác mở cổng là đổi
    câu hỏi sau khi đã thấy số.

    Cổng (a) đọc CẢ `min_cell_n_s{k}` (spec §4.3 ③ bước 2): một slot chuẩn hoá
    trên 10/10 decile trong đó một ô chỉ có một quan sát vẫn gán trọng số gộp
    đầy đủ cho ô đó, nên con số chuẩn hoá của nó có thể do một dòng duy nhất
    quyết định. Thiếu hẳn khoá đó thì cổng ĐÓNG: không đo được độ thưa nghĩa là
    chưa ai kiểm, và mặc định của một cổng chưa kiểm phải là chặn.

    Ngưỡng chỉ áp cho slot ĐƯỢC HỎI, không cho slot đối chứng: cổng (a) lấy MAX
    của bốn đối chứng, nên một đối chứng thưa mà lệch cao chỉ làm cổng khó qua
    hơn (bảo thủ), còn lệch thấp thì gần như chắc chắn không phải cái đang giữ
    max. `min_cell_n` của đối chứng vẫn được in ra để người đọc tự thấy.
    """
    pct = dict(zip(stats["quantity"], stats["real_percentile"]))

    def _get(fmt: str, s: int) -> float:
        return float(real.get(fmt.format(s=s), float("nan")))

    control = [_get(VERDICT_KEY, s) for s in CONTROL_SLOTS]
    finite = [(s, v) for s, v in zip(CONTROL_SLOTS, control) if np.isfinite(v)]
    if finite:
        top_slot, best_control = max(finite, key=lambda kv: kv[1])
        top_txt = (f"{best_control:.4f} (slot {top_slot}, "
                   f"min_cell_n={_get(MIN_CELL_KEY, top_slot):.0f})")
    else:
        best_control, top_txt = float("nan"), "nan (khong slot doi chung nao do duoc)"

    lines = ["## Phan quyet section 10", "",
             f"- nguong percentile: {VERDICT_PERCENTILE}"
             f"  - horizon chuan hoa: {STD_HORIZON_MIN} phut"
             f"  - nguong o thua min_cell_n: {MIN_CELL_N}",
             f"- slot doi chung cao nhat (std): {top_txt}", ""]
    passed = False
    for s in TARGET_SLOTS:
        std = _get(VERDICT_KEY, s)
        cell = _get(MIN_CELL_KEY, s)
        p = float(pct.get(VERDICT_KEY.format(s=s), float("nan")))
        dense = bool(np.isfinite(cell) and cell >= MIN_CELL_N)
        gate_a = bool(np.isfinite(std) and np.isfinite(best_control)
                      and std > best_control and dense)
        gate_b = bool(np.isfinite(p) and p > VERDICT_PERCENTILE)
        hit = gate_a and gate_b
        passed = passed or hit
        lines.append(
            f"- **slot {s}** ({SLOT_NY[s]}): std={std:.4f}, percentile={p:.1f}, "
            f"min_cell_n={cell:.0f} (nguong {MIN_CELL_N})"
            f" -> cong (a) cao hon doi chung VA o du day: "
            f"{'DAT' if gate_a else 'khong'}"
            f"{'' if dense else ' [chan vi o thua]'}; "
            f"cong (b) vuot null: {'DAT' if gate_b else 'khong'} "
            f"-> {'DAC BIET' if hit else 'khong dac biet'}")

    lines += ["", (
        "**Phase 2 DUOC phep viet spec.** Slot 0 hoac slot 5 dat ca hai cong."
        if passed else
        "**Phase 2 KHONG duoc phep viet spec.** Khong slot nao trong hai slot "
        "duoc hoi dat ca hai cong. Hien tuong giai thich duoc bang do rong cay "
        "cong do dai cua so."
    ), "", (
        "**Cong thu ba khong ton tai: Null B da bi loai khoi pham vi (spec 5.3).** "
        "Ke ca khi hai cong DAT, ket luan dung la 'luoi 17:00 NY khac luoi bat ky, "
        "sau khi kiem soat do rong', KHONG phai 'moc H4 phien A bi nham'. Cau sau "
        "can Null B (dao ghep duong gia ngay gan nhau), va spec Phase 2 neu duoc "
        "viet phai mo dau bang viec chay Null B."
    ), "", (
        "Luu y da ghi trong spec section 10: luat nay chay 2 slot x 2 cong o muc "
        "95% nen sai so toan ho rong hon 5%. Nguong de nay duoc chon co y thuc va "
        "khong duoc siet hay noi sau khi thay so. Rieng dai luong 1 (ti le kill "
        "tho) KHONG BAO GIO la can cu ket luan: spec 4.2 cho thay no khong so "
        "duoc giua cac slot."
    )]
    return passed, "\n".join(lines)
