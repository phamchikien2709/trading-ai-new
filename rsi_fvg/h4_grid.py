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

from .bars import Bars
from .indicators import atr_wilder
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


MIN_BAR_FRACTION = 0.6
ATR_PERIOD = 14
_FIELDS = ("open", "high", "low", "close", "n")


def expected_bars(slot: int, bar_seconds: int) -> float:
    """Số bar kỳ vọng của một slot. Slot 0 chỉ có 3 giờ vì khe nghỉ."""
    return SLOT_HOURS[slot] * 3600.0 / bar_seconds


def aggregate_days(bars: Bars, labels: H4Labels, bar_seconds: int,
                   min_fraction: float = MIN_BAR_FRACTION,
                   atr_period: int = ATR_PERIOD) -> pd.DataFrame:
    """Gộp bar thành một dòng mỗi ngày giao dịch với OHLC của cả sáu slot.

    Ba luật loại của spec §3.3, thi hành trong ĐÚNG hàm này để đường thật và
    đường null không thể lệch nhau:

      1. Loại cả ngày nếu bất kỳ slot nào có ít hơn `min_fraction` số bar kỳ
         vọng. Theo tỉ lệ chứ không theo số tuyệt đối vì slot 0 chỉ có 3 giờ.
         Cần thiết vì dữ liệu thật cho p05 của slot 0 = 1 bar, và một cây H4
         dựng từ một bar có high == low, làm "kill hai đầu" thành vô nghĩa.
      2. Loại ngày chuyển DST — nhận diện bằng offset UTC->NY đổi trong ngày.
         Ngày đó có một slot dài 3 hoặc 5 giờ nên range không so được.
      3. Luật 1 và 2 áp y nguyên cho mọi `anchor_offset`.

    `day_atr` tính SAU khi loại, trên chuỗi ngày còn sống: một ngày bị loại có
    high/low không đáng tin và sẽ đầu độc ATR của 14 ngày kế tiếp.

    `first`/`last` cho open/close là đúng vì `bars` theo thứ tự thời gian và
    groupby giữ thứ tự trong nhóm.
    """
    df = pd.DataFrame({
        "day": labels.day_num, "slot": labels.slot,
        "open": bars.open, "high": bars.high,
        "low": bars.low, "close": bars.close,
        "off": labels.utc_offset,
    })
    agg = df.groupby(["day", "slot"], sort=True).agg(
        open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last"), n=("close", "size"),
    )
    wide = agg.unstack("slot")
    wide.columns = [f"s{int(s)}_{field}" for field, s in wide.columns]
    wide = wide.reindex(columns=[f"s{s}_{f}" for s in range(N_SLOTS) for f in _FIELDS])

    keep = np.ones(len(wide), dtype=bool)
    for s in range(N_SLOTS):
        n = wide[f"s{s}_n"].to_numpy(dtype="float64")
        keep &= np.isfinite(n) & (n >= min_fraction * expected_bars(s, bar_seconds))

    n_off = df.groupby("day")["off"].nunique().reindex(wide.index).to_numpy()
    keep &= (n_off == 1)

    out = wide.loc[keep].copy()
    out["day_high"] = out[[f"s{s}_high" for s in range(N_SLOTS)]].max(axis=1)
    out["day_low"] = out[[f"s{s}_low" for s in range(N_SLOTS)]].min(axis=1)
    out["day_close"] = out["s5_close"]
    out["day_atr"] = atr_wilder(out["day_high"].to_numpy(),
                                out["day_low"].to_numpy(),
                                out["day_close"].to_numpy(), atr_period)
    out["date"] = pd.to_datetime(out.index.to_numpy() * NS_PER_DAY)
    return out
