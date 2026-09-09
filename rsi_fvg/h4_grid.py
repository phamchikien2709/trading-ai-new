"""Lưới H4 neo 17:00 New York — gán nhãn và gộp.

Spec: docs/superpowers/specs/2026-09-09-h4-kill-both-ends-study-design.md §3.

Mốc neo LÀ một giờ treo tường New York, nên `Bars.time` phải được convert đúng;
lệch một giờ là đo một lưới khác. Xem docstring `rsi_fvg/quarters.py` về việc tại
sao `Bars.time` là instant UTC thật chứ không phải đồng hồ server.

Module này KHÔNG dùng `label_quarters` của `quarters.py`: hàm đó giả định bốn
quarter một chu kỳ và neo 18:00 NY (`(hour + 6) % 24`). Lưới ở đây có SÁU slot và
neo 17:00. Nhồi vào sẽ phá cả hai study Quarterly Theory đang dùng nó.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .quarters import server_to_ny

ANCHOR_HOUR = 17                      # 17:00 New York — đóng ngày, và khe nghỉ
N_SLOTS = 6
SLOT_SECONDS = 4 * 3600
DAY_SECONDS = 24 * 3600
NS_PER_DAY = 24 * 3600 * 1_000_000_000

# Slot 0 chỉ có 3 giờ giao dịch: khe nghỉ hằng ngày ăn 17:00-18:00 NY.
SLOT_HOURS = (3, 4, 4, 4, 4, 4)


@dataclass(frozen=True)
class H4Labels:
    ny: pd.DatetimeIndex           # tz-aware, giờ New York (đã trừ anchor_offset)
    trading_day: pd.DatetimeIndex  # naive, nửa đêm NY của ngày mở 17:00
    slot: np.ndarray               # int64 0..5
    day_num: np.ndarray            # int64, một giá trị mỗi ngày giao dịch
    utc_offset: np.ndarray         # int64 giây; -18000 (EST) hoặc -14400 (EDT)


def label_h4(time: np.ndarray, anchor_offset: int = 0) -> H4Labels:
    """Gán nhãn (ngày giao dịch, slot) cho từng bar.

    `anchor_offset` (giây) dịch cả lưới và tồn tại CHỈ để mô hình null dùng
    (spec §5.1). Đây là lý do hàm nhận tham số thay vì hardcode mốc neo.

    `trading_day` tính bằng số học LỊCH trên giờ treo tường naive, không bằng số
    giây tích luỹ: trừ một ngày trên timestamp tz-aware là trừ 24 giờ tuyệt đối,
    và qua biên DST New York điều đó cho ra 23:00 hoặc 01:00 thay vì nửa đêm.

    `utc_offset` được trả ra vì luật loại §3.3.2 cần nó: một ngày giao dịch mà
    offset đổi giữa ngày chính là ngày chuyển DST, và ngày đó có một slot dài 3
    hoặc 5 giờ nên range của nó không so được với ngày thường.
    """
    t = np.asarray(time, dtype="int64")
    ny = server_to_ny(t)
    if anchor_offset:
        ny = ny - pd.Timedelta(seconds=int(anchor_offset))

    naive = ny.tz_localize(None)
    hour = naive.hour.to_numpy()
    slot = (((hour + (24 - ANCHOR_HOUR)) % 24) // 4).astype("int64")

    back_a_day = pd.to_timedelta((hour < ANCHOR_HOUR).astype("int64"), unit="D")
    trading_day = naive.normalize() - back_a_day
    day_num = (trading_day.asi8 // NS_PER_DAY).astype("int64")

    utc_naive = pd.to_datetime(t - int(anchor_offset), unit="s")
    utc_offset = ((naive.asi8 - utc_naive.asi8) // 1_000_000_000).astype("int64")

    return H4Labels(ny=ny, trading_day=trading_day, slot=slot,
                    day_num=day_num, utc_offset=utc_offset)
