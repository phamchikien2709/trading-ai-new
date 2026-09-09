"""Gán nhãn quarter của Quarterly Theory theo giờ New York.

Spec: docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md §3.

Bars.time là đồng hồ server của broker được gán nhãn UTC mà KHÔNG convert
(README, mục "Timestamps"). Exness chạy EET/EEST. Với RSI2 và RSI-FVG việc gán
nhãn sai này vô hại vì không có gì trong backtest phụ thuộc giờ treo tường; với
Quarterly Theory thì mọi biên quarter LÀ một mốc giờ New York, nên lệch một giờ
là đo một lý thuyết khác.

Offset server->NY chỉ nhận hai giá trị: 7 giờ (bình thường) và 6 giờ (~28 ngày
mỗi năm, khi Mỹ đã vào DST mà EU chưa, hoặc EU đã ra mà Mỹ chưa). Không tồn tại
8 giờ — giai đoạn DST của EU nằm hoàn toàn bên trong giai đoạn của Mỹ.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SERVER_TZ = "Europe/Athens"      # EET/EEST, khớp ghi chú README về đồng hồ Exness
NY_TZ = "America/New_York"
WEEK_GAP_SECONDS = 86400


def server_to_ny(epoch: np.ndarray) -> pd.DatetimeIndex:
    """epoch seconds (giờ server gán nhãn UTC) -> DatetimeIndex tz-aware giờ NY.

    ambiguous="raise" và nonexistent="raise" là CÓ Ý, không phải mặc định bỏ quên:
    DST của EU đổi lúc 03:00 Chủ nhật, giữa lúc thị trường đóng, nên lẽ ra không
    bar nào rơi vào giờ lặp hay giờ mất. Nếu nó raise thật thì đó là phát hiện về
    dữ liệu cần điều tra, không phải lỗi cần bọc try — bọc lại sẽ che đúng thứ
    đáng biết.
    """
    naive = pd.to_datetime(np.asarray(epoch, dtype="int64"), unit="s")
    return naive.tz_localize(SERVER_TZ, ambiguous="raise",
                             nonexistent="raise").tz_convert(NY_TZ)


# Nhãn thứ trong tuần tự viết, KHÔNG dùng strftime("%a"): %a phụ thuộc locale của
# máy và repo này chạy trên Windows tiếng Việt.
DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# Vàng/forex mở Chủ nhật 17:00-18:00 NY; khe nghỉ hằng ngày của Exness
# (00:00-01:00 EET) kết thúc trong cùng cửa sổ đó tính theo giờ NY.
WEEKLY_OPEN_OK = ("Sun 17:00", "Sun 17:30", "Sun 18:00")
DAILY_GAP_END_OK = ("17:00", "17:30", "18:00")


@dataclass(frozen=True)
class TzCheck:
    weekly_open_mode: str
    weekly_open_counts: dict[str, int]
    daily_gap_end_mode: str
    daily_gap_end_counts: dict[str, int]
    weekly_ok: bool
    daily_ok: bool
    ok: bool
    notes: tuple[str, ...]


def verify_server_tz(time: np.ndarray, bar_seconds: int) -> TzCheck:
    """Kiểm giả định "đồng hồ server = EET" bằng dữ liệu, không bằng niềm tin.

    Kiểm định 1 (CHẶN): giờ NY của bar đầu tiên sau mỗi khe cuối tuần. Thị trường
    mở Chủ nhật 17:00-18:00 NY, nên mode phải nằm trong cửa sổ đó.

    Kiểm định 2 (BỔ TRỢ): giờ NY của bar đầu tiên sau mỗi khe trong ngày. Khe nghỉ
    hằng ngày của Exness kết thúc 01:00 EET = 18:00 NY. Kiểm định này KHÔNG chặn
    một mình khi không có khe nào — tài khoản có thể không có phiên nghỉ, và chặn
    oan sẽ khoá cả nghiên cứu vì một thứ chỉ mang tính xác nhận.

    Ghi chú cho spec §8.2: khe nghỉ kết thúc đúng 18:00 NY, trùng mốc neo chu kỳ
    ngày. Vừa là kiểm định tốt, vừa là confound.
    """
    t = np.asarray(time, dtype="int64")
    notes: list[str] = []
    if t.size < 2:
        return TzCheck("", {}, "", {}, False, False, False, ("chuoi qua ngan",))

    ny = server_to_ny(t)
    d = np.diff(t)
    after = np.flatnonzero(d > bar_seconds) + 1        # bar ngay SAU mỗi khe
    if after.size == 0:
        return TzCheck("", {}, "", {}, False, False, False,
                       ("khong tim thay khe nao trong chuoi",))

    gap = d[after - 1]
    weekly_idx = after[gap > WEEK_GAP_SECONDS]
    daily_idx = after[gap <= WEEK_GAP_SECONDS]

    def labels(idx: np.ndarray, with_dow: bool) -> dict[str, int]:
        if idx.size == 0:
            return {}
        sub = ny[idx]
        out: list[str] = []
        for dw, hh, mm in zip(sub.dayofweek, sub.hour, sub.minute):
            stamp = f"{hh:02d}:{mm:02d}"
            out.append(f"{DOW[dw]} {stamp}" if with_dow else stamp)
        vc = pd.Series(out).value_counts()
        return {str(k): int(v) for k, v in vc.items()}

    w_counts = labels(weekly_idx, True)
    d_counts = labels(daily_idx, False)
    w_mode = next(iter(w_counts), "")
    d_mode = next(iter(d_counts), "")

    weekly_ok = w_mode in WEEKLY_OPEN_OK
    daily_ok = (d_mode == "") or (d_mode in DAILY_GAP_END_OK)
    if not weekly_ok:
        notes.append(f"mo dau tuan mode={w_mode!r}, ngoai cua so {WEEKLY_OPEN_OK}")
    if d_mode == "":
        notes.append("khong co khe trong ngay: kiem dinh 2 pass rong")
    elif not daily_ok:
        notes.append(f"ket khe hang ngay mode={d_mode!r}, ngoai cua so {DAILY_GAP_END_OK}")
    return TzCheck(w_mode, w_counts, d_mode, d_counts,
                   weekly_ok, daily_ok, weekly_ok and daily_ok, tuple(notes))
