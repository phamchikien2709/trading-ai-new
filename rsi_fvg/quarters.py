"""Gán nhãn quarter của Quarterly Theory theo giờ New York.

Spec: docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md §3.

Mọi biên quarter LÀ một mốc giờ treo tường New York, nên `Bars.time` phải được
convert đúng sang giờ NY; lệch một giờ là đo một lý thuyết khác.

`Bars.time` là instant **UTC thật**. Điều này TRÁI với ghi chú "Timestamps" của
README, vốn nói `time` là đồng hồ server của broker được gán nhãn UTC mà không
convert. Ghi chú đó sai, và đã được bác bỏ bằng dữ liệu:

  Khe nghỉ hằng ngày của XAUUSDc (một mốc CỐ ĐỊNH của broker) xuất hiện ở hai
  giờ thô khác nhau: 22:00 (1276 lần) và 23:00 (642 lần). Đó đúng là cặp giá trị
  mà mốc 01:00 EET/EEST sinh ra khi đọc như UTC — 01:00 EEST = 22:00 UTC vào hè,
  01:00 EET = 23:00 UTC vào đông. Đọc epoch là UTC rồi convert sang NY thì hai
  giá trị đó GỘP thành một: 18:00 NY, 1893 lần (1276 + 642 = 1918 ~ 1893 + 25).
  Đọc epoch là giờ treo tường Athens thì chúng CHIA ĐÔI thành 15:00 và 16:00.
  Một mốc cố định của broker chỉ gộp được khi phép convert đúng.

Vì epoch là UTC, phần DST duy nhất còn lại là phía New York: offset UTC->NY chỉ
nhận 5 giờ (EST) hoặc 4 giờ (EDT).

Ghi chú cho spec §8.2: khe nghỉ hằng ngày kết thúc đúng 18:00 NY, TRÙNG KHÍT mốc
neo chu kỳ ngày của lý thuyết. Confound này giờ đã được xác nhận bằng dữ liệu
thật, không còn là suy đoán.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SOURCE_TZ = "UTC"                # Bars.time la instant UTC that, xem docstring
NY_TZ = "America/New_York"
WEEK_GAP_SECONDS = 86400


def server_to_ny(epoch: np.ndarray) -> pd.DatetimeIndex:
    """epoch seconds (UTC thật) -> DatetimeIndex tz-aware giờ New York.

    Không cần chính sách cho giờ ambiguous hay nonexistent: UTC không có DST nên
    `tz_localize("UTC")` không bao giờ nhập nhằng, và `tz_convert` từ một instant
    tuyệt đối sang New York luôn xác định. Phiên bản trước của hàm này localize
    vào Europe/Athens và phải xử lý giờ lặp/giờ mất của DST châu Âu — cả vấn đề
    đó biến mất cùng với giả định sai.
    """
    naive = pd.to_datetime(np.asarray(epoch, dtype="int64"), unit="s")
    return naive.tz_localize(SOURCE_TZ).tz_convert(NY_TZ)


# Nhãn thứ trong tuần tự viết, KHÔNG dùng strftime("%a"): %a phụ thuộc locale của
# máy và repo này chạy trên Windows tiếng Việt.
DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# Vàng/forex mở Chủ nhật 17:00-18:00 NY; khe nghỉ hằng ngày của Exness kết thúc
# trong cùng cửa sổ đó tính theo giờ NY.
#
# Kiểm theo (thứ, GIỜ) chứ không theo chuỗi khớp chính xác: bar đầu tiên sau khe
# thường lệch vài phút (dữ liệu thật cho "Sun 18:05" nhiều hơn "Sun 18:00", vì
# nến đúng mốc 18:00 không luôn tồn tại). Khớp chuỗi sẽ fail vì phút lẻ, một lý
# do không liên quan gì tới timezone.
WEEKLY_OPEN_OK_DOW = 6           # Chủ nhật (Mon=0)
WEEKLY_OPEN_OK_HOURS = (17, 18)
DAILY_GAP_END_OK_HOURS = (17, 18)


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
    """Kiểm bằng dữ liệu rằng cách đọc `time` đang đúng, không tin vào tài liệu.

    Ghi chú README từng mô tả sai ngữ nghĩa `time` (xem docstring module), nên
    hàm này tồn tại để nếu một lần fetch sau này đổi ngữ nghĩa đó thì nghiên cứu
    DỪNG thay vì âm thầm đo sai.

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
        """Đếm theo nhãn có phút — chỉ để BÁO CÁO, không để quyết định."""
        if idx.size == 0:
            return {}
        sub = ny[idx]
        out: list[str] = []
        for dw, hh, mm in zip(sub.dayofweek, sub.hour, sub.minute):
            stamp = f"{hh:02d}:{mm:02d}"
            out.append(f"{DOW[dw]} {stamp}" if with_dow else stamp)
        vc = pd.Series(out).value_counts()
        return {str(k): int(v) for k, v in vc.items()}

    def modal_dow_hour(idx: np.ndarray) -> tuple[int, int] | None:
        """Mode theo (thứ, giờ) — bất biến với phút. Đây là cái để QUYẾT ĐỊNH."""
        if idx.size == 0:
            return None
        sub = ny[idx]
        pairs = list(zip(sub.dayofweek.tolist(), sub.hour.tolist()))
        return pd.Series(pairs).value_counts().index[0]

    w_counts = labels(weekly_idx, True)
    d_counts = labels(daily_idx, False)
    w_mode = next(iter(w_counts), "")
    d_mode = next(iter(d_counts), "")

    w_pair = modal_dow_hour(weekly_idx)
    d_pair = modal_dow_hour(daily_idx)
    weekly_ok = (w_pair is not None and w_pair[0] == WEEKLY_OPEN_OK_DOW
                 and w_pair[1] in WEEKLY_OPEN_OK_HOURS)
    daily_ok = (d_pair is None) or (d_pair[1] in DAILY_GAP_END_OK_HOURS)
    if not weekly_ok:
        notes.append(f"mo dau tuan mode={w_mode!r}, can Chu nhat gio "
                     f"{WEEKLY_OPEN_OK_HOURS}")
    if d_pair is None:
        notes.append("khong co khe trong ngay: kiem dinh 2 pass rong")
    elif not daily_ok:
        notes.append(f"ket khe hang ngay mode={d_mode!r}, can gio "
                     f"{DAILY_GAP_END_OK_HOURS}")
    return TzCheck(w_mode, w_counts, d_mode, d_counts,
                   weekly_ok, daily_ok, weekly_ok and daily_ok, tuple(notes))


TIERS: dict[str, int] = {"session": 21600, "q90": 5400}
NS_PER_DAY = 24 * 3600 * 1_000_000_000


@dataclass(frozen=True)
class QuarterLabels:
    ny: pd.DatetimeIndex           # tz-aware, giờ New York
    trading_day: pd.DatetimeIndex  # naive, nửa đêm NY của ngày mở 18:00
    i_sess: np.ndarray             # 0..3 — Asia / London / NY-AM / NY-PM
    i_q90: np.ndarray              # 0..3 — block 90 phút trong session
    cycle_id: np.ndarray           # int64, một giá trị mỗi chu kỳ của tier
    q_index: np.ndarray            # int64 0..3 — quarter của tier (Q1 lý thuyết = 0)


def label_quarters(time: np.ndarray, tier: str,
                   anchor_offset: int = 0) -> QuarterLabels:
    """Gán nhãn quarter theo giờ New York. Cùng số học với indicator Pine.

    Xem pine/quarterly_theory_ict.pine: hShift = (hour + 6) % 24 dịch 18:00 NY về 0,
    nên chu kỳ ngày chạy 18:00 -> 18:00.

    `anchor_offset` (giây) dịch cả lưới và tồn tại CHỈ để mô hình null dùng
    (spec §4.1). Đây là lý do hàm nhận tham số thay vì hardcode mốc neo.

    `trading_day` tính bằng số học LỊCH trên giờ treo tường naive, không bằng số
    giây tích luỹ: trừ một ngày trên timestamp tz-aware là trừ 24 giờ tuyệt đối,
    và qua biên DST của New York điều đó cho ra 23:00 hoặc 01:00 thay vì nửa đêm.
    """
    if tier not in TIERS:
        raise ValueError(f"tier phai la mot trong {sorted(TIERS)}, nhan {tier!r}")

    ny = server_to_ny(time)
    if anchor_offset:
        ny = ny - pd.Timedelta(seconds=int(anchor_offset))

    naive = ny.tz_localize(None)
    hour = naive.hour.to_numpy()
    h_shift = (hour + 6) % 24
    i_sess = (h_shift // 6).astype("int64")
    sec_in_sess = ((h_shift % 6) * 3600
                   + naive.minute.to_numpy() * 60
                   + naive.second.to_numpy())
    i_q90 = (sec_in_sess // 5400).astype("int64")

    back_a_day = pd.to_timedelta((hour < 18).astype("int64"), unit="D")
    trading_day = naive.normalize() - back_a_day
    day_num = (trading_day.asi8 // NS_PER_DAY).astype("int64")

    if tier == "session":
        cycle_id, q_index = day_num, i_sess
    else:
        cycle_id, q_index = day_num * 4 + i_sess, i_q90

    return QuarterLabels(ny=ny, trading_day=trading_day, i_sess=i_sess,
                         i_q90=i_q90, cycle_id=cycle_id.astype("int64"),
                         q_index=q_index.astype("int64"))
