# H4 Kill Both Ends Study — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đo tỉ lệ nến H4 (lưới neo 17:00 New York) bị quét cả hai đầu trong ngày, đọc trong nhóm đối chứng cả sáu slot và so với null lệch mốc neo, cộng hai đại lượng "max range kill".

**Architecture:** Hai module thuần hàm — `h4_grid.py` biết về **thời gian** (gán nhãn lưới, gộp thành bảng ngày × 6 slot, ba luật loại), `h4_kill.py` biết về **giá** (bốn nguyên thuỷ, bảy đại lượng, bộ chạy null). Một cổng chặn riêng dò timezone của nguồn. Một script CLI ghép lại và in phán quyết bằng máy. Mọi đại lượng là hàm thuần của một bảng dòng, nên test dựng bảng bằng tay được và bộ chạy null không cần biết đại lượng đo gì.

**Tech Stack:** Python 3.13, numpy ≥ 2.0, pandas ≥ 2.2, pytest ≥ 8.0. **Không thêm dependency nào** (không scipy, không tabulate).

**Spec:** `docs/superpowers/specs/2026-09-09-h4-kill-both-ends-study-design.md`

## Global Constraints

- Branch: `feat/h4-kill-study`. HEAD khi lập plan: `cd9e729`.
- Chạy test: `python -m pytest -q` từ gốc repo. **304 test hiện có phải xanh sau mỗi task.**
- **KHÔNG BAO GIỜ** `git add -A`. Stage từng file một. `data/`, `results/`, `.superpowers/` chứa artifact thật.
- **KHÔNG BAO GIỜ** regenerate `tests/data/golden_rsi2_swing_grid.csv` để một refactor pass.
- Terminal MT5 trên máy này là **tài khoản Exness REAL**. Chỉ được gọi hàm MT5 read-only. **Không hàm order/trade nào**, không ngoại lệ.
- TDD cho mọi thay đổi hành vi: test fail trước, rồi mới code.
- Docstring và comment viết tiếng Việt có dấu (theo `rsi_fvg/quarters.py`). **Commit message không dấu** (theo lịch sử repo).
- Không thêm dependency. Không dùng `DataFrame.to_markdown` (cần `tabulate`, không có trong `requirements.txt`).
- Giá là **BID** (`Bars` docstring). So sánh kill là **ngặt**: `>` và `<`, chạm đúng mốc không tính.
- `Bars.time` là **instant UTC thật**, không phải giờ server. Xem docstring `rsi_fvg/quarters.py`.

## Deviation from spec §7 — ghi rõ, không âm thầm

Spec §7 liệt kê **hai** module mới. Plan này tách cổng dò timezone thành module thứ ba `rsi_fvg/data/tz_detect.py` thay vì nhét vào `h4_grid.py`. Lý do: cổng đó nói về **nguồn dữ liệu** (một CSV export có timezone gì), không nói về lưới H4; gộp vào sẽ làm `h4_grid.py` làm hai việc. Đây là thay đổi về vị trí file, không thay đổi hành vi nào mà spec quy định.

## File Structure

| file | trách nhiệm |
|---|---|
| `rsi_fvg/h4_grid.py` | **mới.** Gán nhãn lưới H4 neo 17:00 NY, gộp thành bảng ngày × 6 slot, ba luật loại, ATR ngày. Biết về thời gian, không biết về phép đo. |
| `rsi_fvg/h4_kill.py` | **mới.** Bốn nguyên thuỷ (`scan_kills`), bảy đại lượng thuần hàm, `run_grid`/`run_null`. Biết về giá, không biết về thời gian. |
| `rsi_fvg/data/tz_detect.py` | **mới.** Cổng chặn dò timezone của nguồn bằng khe nghỉ hằng ngày. |
| `rsi_fvg/data/csv_loader.py` | **sửa, thuần thêm.** Dialect FXCM (`BidOpen…AskClose`, `DateTime`). |
| `rsi_fvg/quarter_stats.py` | **sửa, thuần thêm.** `make_offsets(..., cycle_seconds=None)`. |
| `scripts/study_h4_kill.py` | **mới.** CLI, cổng chặn, bảng thật vs null, phán quyết §10 tính bằng máy. |
| `tests/test_h4_grid.py` | **mới.** Task 1–2. |
| `tests/test_h4_kill.py` | **mới.** Task 3–7. |
| `tests/test_tz_detect.py` | **mới.** Task 8. |
| `tests/test_csv_loader.py` | **sửa.** Thêm test dialect FXCM. |
| `tests/test_quarter_stats.py` | **sửa.** Thêm test `cycle_seconds` không đổi hành vi cũ. |

Đọc trước khi sửa, đọc **cả file**: `rsi_fvg/quarters.py`, `rsi_fvg/quarter_stats.py`, `rsi_fvg/bars.py`, `rsi_fvg/indicators.py`, `rsi_fvg/data/csv_loader.py`, `rsi_fvg/data/mt5_loader.py`, `scripts/study_quarters.py`, `tests/conftest.py`, và spec.

---

## Task 1: `label_h4` — gán nhãn lưới H4 neo 17:00 New York

**Files:**
- Create: `rsi_fvg/h4_grid.py`
- Test: `tests/test_h4_grid.py`

**Interfaces:**
- Consumes: `rsi_fvg.quarters.server_to_ny(epoch: np.ndarray) -> pd.DatetimeIndex` (tz-aware NY); `tests.conftest.epoch_for_ny(y, m, d, hh, mm=0, ss=0) -> int`.
- Produces: hằng số `ANCHOR_HOUR = 17`, `N_SLOTS = 6`, `SLOT_SECONDS = 14400`, `DAY_SECONDS = 86400`, `SLOT_HOURS = (3, 4, 4, 4, 4, 4)`, `NS_PER_DAY`; dataclass `H4Labels(ny, trading_day, slot, day_num, utc_offset)`; `label_h4(time, anchor_offset: int = 0) -> H4Labels`.

- [ ] **Step 1: Viết test fail**

Tạo `tests/test_h4_grid.py`:

```python
import numpy as np
import pandas as pd
import pytest

from conftest import epoch_for_ny
from rsi_fvg.h4_grid import ANCHOR_HOUR, N_SLOTS, SLOT_SECONDS, label_h4


def _one(y, m, d, hh, mm=0, anchor_offset=0):
    t = np.array([epoch_for_ny(y, m, d, hh, mm)], dtype="int64")
    lab = label_h4(t, anchor_offset=anchor_offset)
    return int(lab.slot[0]), lab.trading_day[0], int(lab.utc_offset[0])


@pytest.mark.parametrize("hh,want_slot", [
    (17, 0), (20, 0), (21, 1), (23, 1), (0, 1), (1, 2), (4, 2),
    (5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (16, 5),
])
def test_slot_from_ny_hour(hh, want_slot):
    """Sáu slot 4 giờ, slot 0 bắt đầu 17:00 NY. Giờ 0..16 thuộc ngày giao dịch
    trước, nên chúng phải cho slot 1..5 chứ không phải slot 0."""
    day = 16 if hh < ANCHOR_HOUR else 15
    got, _, _ = _one(2026, 1, day, hh)
    assert got == want_slot


def test_trading_day_rolls_at_17_ny():
    s_before, d_before, _ = _one(2026, 1, 15, 16, 59)
    s_after, d_after, _ = _one(2026, 1, 15, 17, 0)
    assert (s_before, s_after) == (5, 0)
    assert d_before == pd.Timestamp("2026-01-14")
    assert d_after == pd.Timestamp("2026-01-15")


def test_grid_follows_ny_dst_not_fixed_utc():
    """Mốc neo là 17:00 giờ treo tường NY. Mùa hè nó là một instant UTC khác
    mùa đông, và lưới phải đi theo giờ treo tường — đó là cái người dùng duyệt."""
    s_win, d_win, off_win = _one(2026, 1, 15, 17)
    s_sum, d_sum, off_sum = _one(2026, 7, 1, 17)
    assert (s_win, s_sum) == (0, 0)
    assert d_win == pd.Timestamp("2026-01-15") and d_sum == pd.Timestamp("2026-07-01")
    assert (off_win, off_sum) == (-5 * 3600, -4 * 3600)


def test_trading_day_is_ny_midnight_across_dst_boundary():
    """Trừ một ngày trên timestamp tz-aware là trừ 24 giờ tuyệt đối, và qua biên
    DST điều đó cho ra 23:00 hoặc 01:00. Phải là nửa đêm NY."""
    t = np.array([epoch_for_ny(2026, 3, 8, 10), epoch_for_ny(2026, 11, 1, 10)],
                 dtype="int64")
    lab = label_h4(t)
    assert list(lab.trading_day) == [pd.Timestamp("2026-03-07"),
                                     pd.Timestamp("2026-10-31")]
    assert (lab.trading_day.hour == 0).all()
    assert (lab.trading_day.minute == 0).all()


def test_anchor_offset_shifts_whole_grid():
    """anchor_offset tồn tại CHỈ để mô hình null dùng: dịch lưới đi thì nhãn
    của cùng một bar phải đổi."""
    assert _one(2026, 1, 15, 18)[0] == 0
    assert _one(2026, 1, 15, 18, anchor_offset=3600)[0] == 0      # đọc như 17:00
    assert _one(2026, 1, 15, 18, anchor_offset=2 * 3600)[0] == 5  # đọc như 16:00
    assert _one(2026, 1, 15, 18, anchor_offset=2 * 3600)[1] == pd.Timestamp("2026-01-14")


def test_slot_covers_every_hour_exactly_once():
    """Không giờ nào rơi ngoài lưới và không giờ nào bị hai slot nhận."""
    t = np.array([epoch_for_ny(2026, 6, 10, h) for h in range(24)], dtype="int64")
    lab = label_h4(t)
    counts = np.bincount(lab.slot, minlength=N_SLOTS)
    assert list(counts) == [4] * N_SLOTS
    assert SLOT_SECONDS == 4 * 3600
```

- [ ] **Step 2: Chạy test để chắc nó fail**

Run: `python -m pytest tests/test_h4_grid.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'rsi_fvg.h4_grid'`

- [ ] **Step 3: Viết implementation tối thiểu**

Tạo `rsi_fvg/h4_grid.py`:

```python
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
```

- [ ] **Step 4: Chạy test để chắc nó pass**

Run: `python -m pytest tests/test_h4_grid.py -q`
Expected: PASS (19 test)

Rồi chạy cả suite: `python -m pytest -q` → 304 + 19 = **323 passed**.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/h4_grid.py tests/test_h4_grid.py
git commit -m "feat(h4_grid): label_h4 - luoi H4 neo 17:00 New York"
```

---

## Task 2: `aggregate_days` — bảng ngày × 6 slot, ba luật loại, ATR ngày

**Files:**
- Modify: `rsi_fvg/h4_grid.py` (thêm vào cuối)
- Test: `tests/test_h4_grid.py` (thêm vào cuối)

**Interfaces:**
- Consumes: `label_h4`, `H4Labels`, `SLOT_HOURS`, `N_SLOTS`, `NS_PER_DAY` từ Task 1; `rsi_fvg.bars.Bars`; `rsi_fvg.indicators.atr_wilder(high, low, close, period) -> np.ndarray`.
- Produces: `MIN_BAR_FRACTION = 0.6`, `ATR_PERIOD = 14`, `expected_bars(slot: int, bar_seconds: int) -> float`, `aggregate_days(bars, labels, bar_seconds, min_fraction=MIN_BAR_FRACTION, atr_period=ATR_PERIOD) -> pd.DataFrame`. Frame index là `day_num` (int64, tên `day`), cột `s0_open…s5_n` (`n` là số bar), `day_high`, `day_low`, `day_close`, `day_atr`, `date` (datetime64 naive).

**Ruling cần biết trước khi code:** `day_atr` tính **SAU** khi loại, trên chuỗi ngày còn sống. Spec §3.2 nói "chuỗi nến ngày dựng theo chính lưới này" mà không nói trước hay sau. Chọn sau, vì một ngày bị loại (slot 0 có 1 bar, hoặc ngày chuyển DST) có high/low không đáng tin và sẽ đầu độc ATR của 14 ngày kế tiếp. Hệ quả: `day_atr` của 13 ngày còn sống đầu tiên là `NaN` theo đúng ngữ nghĩa Wilder.

- [ ] **Step 1: Viết test fail**

Thêm vào `tests/test_h4_grid.py` (cộng import `Bars`, `aggregate_days`, `expected_bars`, `MIN_BAR_FRACTION`, `atr_wilder`):

```python
# Giờ NY của 23 bar H1 trong một ngày giao dịch. Khe nghỉ 17:00-18:00 NY bị bỏ,
# nên slot 0 chỉ có 3 bar (18,19,20) còn slot 1-5 có 4 bar.
NY_HOURS = (18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4,
            5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)


def h1_days(start_date, n_days, drop=(), wide_days=(), base=2000.0):
    """Bars H1 cho n_days ngày giao dịch bắt đầu `start_date` 18:00 NY.

    `drop` là tập (chỉ số ngày, giờ NY) cần bỏ bar — để test luật loại.
    `wide_days` là tập chỉ số ngày cần cho range cực lớn — để test ATR.
    Giờ không tồn tại (spring-forward) bị bỏ, đúng như dữ liệu thật.
    """
    d0 = pd.Timestamp(start_date)
    times, o, h, l, c = [], [], [], [], []
    k = 0
    for i in range(n_days):
        for hh in NY_HOURS:
            if (i, hh) in drop:
                continue
            day = d0 + pd.Timedelta(days=i + (0 if hh >= 17 else 1))
            try:
                e = epoch_for_ny(day.year, day.month, day.day, hh)
            except Exception:      # giờ không tồn tại vào ngày spring-forward
                continue
            k += 1
            mid = base + k * 0.5
            wick = 50.0 if i in wide_days else 1.0
            times.append(e)
            o.append(mid); c.append(mid)
            h.append(mid + wick); l.append(mid - wick)
    return Bars(time=np.asarray(times, dtype="int64"),
                open=np.asarray(o, dtype="float64"),
                high=np.asarray(h, dtype="float64"),
                low=np.asarray(l, dtype="float64"),
                close=np.asarray(c, dtype="float64"))


def _days(bars, anchor_offset=0, **kw):
    lab = label_h4(bars.time, anchor_offset=anchor_offset)
    return aggregate_days(bars, lab, 3600, **kw)


def _dates(days):
    return set(days["date"].dt.strftime("%Y-%m-%d"))


def test_expected_bars_is_per_slot():
    """Slot 0 chỉ có 3 giờ. Một ngưỡng tuyệt đối chung sẽ hoặc loại oan slot 0
    hoặc quá lỏng với năm slot kia."""
    assert expected_bars(0, 3600) == 3.0
    assert expected_bars(1, 3600) == 4.0
    assert expected_bars(0, 60) == 180.0
    assert expected_bars(4, 60) == 240.0


def test_aggregate_shape_and_ohlc():
    days = _days(h1_days("2026-01-05", 20), atr_period=2)
    assert len(days) == 20
    assert days["s0_n"].eq(3).all() and days["s3_n"].eq(4).all()
    assert (days["s0_high"] > days["s0_close"]).all()
    assert days["day_close"].equals(days["s5_close"])
    assert days["day_high"].equals(days[[f"s{s}_high" for s in range(N_SLOTS)]].max(axis=1))
    assert days["day_low"].equals(days[[f"s{s}_low" for s in range(N_SLOTS)]].min(axis=1))


def test_starved_slot_drops_whole_day():
    """Bỏ 2 trong 4 bar của slot 3 ở ngày thứ 5 -> 2 < 0.6*4 -> loại cả ngày."""
    bars = h1_days("2026-01-05", 20, drop={(5, 5), (5, 6)})
    kept = _dates(_days(bars, atr_period=2))
    assert "2026-01-10" not in kept
    assert "2026-01-09" in kept and "2026-01-11" in kept


def test_slot0_survives_two_of_three_bars():
    """Luật theo TỈ LỆ: slot 0 với 2/3 bar sống (2 >= 1.8), nhưng slot 1 với
    2/4 bar thì chết (2 < 2.4). Một ngưỡng tuyệt đối không phân biệt được."""
    ok = h1_days("2026-01-05", 20, drop={(5, 18)})
    assert "2026-01-10" in _dates(_days(ok, atr_period=2))
    bad = h1_days("2026-01-05", 20, drop={(5, 21), (5, 22)})
    assert "2026-01-10" not in _dates(_days(bad, atr_period=2))


def test_dst_transition_day_is_dropped():
    """DST spring-forward 2026-03-08 02:00 NY nằm TRONG ngày giao dịch 03-07
    (ngày đó chạy 03-07 17:00 -> 03-08 17:00), nên chính 03-07 bị loại."""
    kept = _dates(_days(h1_days("2026-03-04", 8), atr_period=2))
    assert "2026-03-07" not in kept
    assert "2026-03-06" in kept and "2026-03-08" in kept


def test_exclusion_applies_to_shifted_grid_too():
    """Luật loại phải áp y nguyên cho lưới thật và mọi lưới null. Chỉ áp một bên
    thì cỡ mẫu lệch và phép so vô nghĩa (bài học của aggregate_cycles)."""
    bars = h1_days("2026-01-05", 20, drop={(5, 5), (5, 6)})
    for off in (0, 3600, SLOT_SECONDS, 2 * SLOT_SECONDS):
        days = _days(bars, anchor_offset=off, atr_period=2)
        for s in range(N_SLOTS):
            n = days[f"s{s}_n"].to_numpy(dtype="float64")
            assert np.isfinite(n).all()
            assert (n >= MIN_BAR_FRACTION * expected_bars(s, 3600)).all()


def test_day_atr_computed_after_exclusion():
    """Ngày bị loại có range 100 USD. ATR của các ngày sau KHÔNG được phản ánh
    nó — nếu ATR tính trước khi loại thì nó sẽ phản ánh."""
    bars = h1_days("2026-01-05", 20, drop={(5, 5), (5, 6)}, wide_days={5})
    days = _days(bars, atr_period=3)
    want = atr_wilder(days["day_high"].to_numpy(), days["day_low"].to_numpy(),
                      days["day_close"].to_numpy(), 3)
    np.testing.assert_allclose(days["day_atr"].to_numpy(), want, equal_nan=True)
    assert days["day_atr"].max() < 50.0


def test_day_atr_nan_during_warmup():
    days = _days(h1_days("2026-01-05", 20))
    assert days["day_atr"].iloc[:13].isna().all()
    assert days["day_atr"].iloc[13:].notna().all()
```

- [ ] **Step 2: Chạy test để chắc nó fail**

Run: `python -m pytest tests/test_h4_grid.py -q`
Expected: FAIL — `ImportError: cannot import name 'aggregate_days' from 'rsi_fvg.h4_grid'`

- [ ] **Step 3: Viết implementation tối thiểu**

Thêm vào `rsi_fvg/h4_grid.py` (import `Bars` và `atr_wilder` ở đầu file):

```python
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
```

- [ ] **Step 4: Chạy test để chắc nó pass**

Run: `python -m pytest tests/test_h4_grid.py -q` → PASS
Rồi cả suite: `python -m pytest -q` → **332 passed**.

Kiểm bằng tay trên dữ liệu thật (không phải test — chỉ xác nhận số khớp spec §2.2):

```bash
python -c "import pandas as pd; from rsi_fvg.bars import Bars; from rsi_fvg.h4_grid import label_h4, aggregate_days; d=pd.read_parquet('data/XAUUSDc_M1.parquet'); b=Bars.from_dataframe(d); days=aggregate_days(b,label_h4(b.time),60); print('ngay con song:',len(days)); print(days[[f's{s}_n' for s in range(6)]].median().to_string())"
```
Expected: `ngay con song: 2303`, median bar = 179 / 240 / 240 / 240 / 240 / 238. **Nếu hai con số này lệch, DỪNG và báo.**

Lưu ý 2303 chứ không phải 2385: spec §2.2 nói 2385 ngày **có mặt cả sáu slot**, còn đây là số ngày **sống sót cả ba luật loại** — luật 1 (mỗi slot ≥ 60% bar kỳ vọng) loại thêm 82 ngày nửa phiên và ngày lễ.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/h4_grid.py tests/test_h4_grid.py
git commit -m "feat(h4_grid): aggregate_days - bang ngay x 6 slot, ba luat loai, ATR ngay"
```

---

## Task 3: `scan_kills` — bốn nguyên thuỷ

**Files:**
- Create: `rsi_fvg/h4_kill.py`
- Test: `tests/test_h4_kill.py`

**Interfaces:**
- Consumes: `rsi_fvg.h4_grid.{label_h4, aggregate_days, H4Labels, N_SLOTS}`; `rsi_fvg.bars.Bars`.
- Produces: `H_MAX_MIN = 1440`, `HORIZONS_MIN = (60, 120, 240, 480, 720, 1200, 1440)`, `STD_HORIZON_MIN = 720`, `MAX_GAP_DAYS = 4`; `scan_kills(bars, labels, days, bar_seconds, h_max_min=H_MAX_MIN, max_gap_days=MAX_GAP_DAYS) -> pd.DataFrame` với các cột: `day_num, date, year, slot, cand_high, cand_low, range_usd, day_atr, rel_range, w_from, w_to, w_bars, w_hours, gap_days, crosses_weekend, h_avail, t_up, t_dn, k_up, k_dn, exc_up, exc_dn`.

**Bốn ruling của task này. Đọc hết trước khi code — ba trong bốn cái này không suy ra được từ spec.**

**(1) `t_up`/`t_dn` tính bằng BAR, không bằng phút.** Spec §4.1 nói "phút thị trường mở"; trên M1 bar = phút nên hai cái trùng nhau, nhưng trên M5/H1 thì không. Lưu bằng bar, quy đổi horizon phút → bar bằng `h * 60 // bar_seconds`. Cách này chạy đúng trên mọi khung.

**(2) Cửa sổ ① mô tả bằng `w_from`/`w_to` (bù bar so với bar cuối của nến), không bằng `w_bars` một mình.** Vì spec §11 mục 10: 163 bar Thứ Bảy lạc nằm **giữa** thứ Sáu và ngày giao dịch thật kế tiếp. Nếu giả định cửa sổ bắt đầu ngay tại `end + 1` thì với những dòng đó cửa sổ lệch đi 1–2 bar. `killed ⇔ w_from <= t <= w_to`. Với slot 0–4 thì `w_from = 1`.

**(3) "Ngày kế tiếp" của slot 5 là ngày giao dịch CÒN SỐNG kế tiếp, và dòng bị loại nếu `gap_days > 4`.** Spec §4.2 nói "ngày giao dịch kế tiếp có trong dữ liệu" và §11 mục 10 giải thích tại sao không được dùng ngày lịch kế tiếp: mỗi bar Thứ Bảy lạc sinh ra một "ngày giao dịch" bị luật loại xoá, và nếu coi nó là ngày kế tiếp thì 163 dòng slot 5 của thứ Sáu trong 2018–2021 bị xoá oan — một phép xoá thiên lệch theo thời gian. Ngưỡng 4 ngày: thứ Sáu → thứ Hai là 3 ngày, thứ Sáu → thứ Ba (lễ) là 4; lớn hơn thế thì mốc đã nằm im quá lâu để gọi là "trong một ngày".

**(4) Dòng có cửa sổ ① bị cắt ở mép dữ liệu bị LOẠI, không báo là "không bị kill".** Spec §8 mục 9. Đây là look-ahead ngược và nó sẽ dìm tỉ lệ kill ở cuối mẫu — chính đoạn 2025–2026. Ngược lại, dòng có cửa sổ ① đủ nhưng quét horizon bị cắt thì **giữ**, và `h_avail` ghi số bar thực có; đại lượng theo horizon chỉ đếm dòng có `h_avail >= h_bars`.

- [ ] **Step 1: Viết test fail**

Tạo `tests/test_h4_kill.py`:

```python
import numpy as np
import pandas as pd

from conftest import epoch_for_ny
from rsi_fvg.bars import Bars
from rsi_fvg.h4_grid import N_SLOTS, aggregate_days, label_h4
from rsi_fvg.h4_kill import scan_kills

NY_HOURS = (18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4,
            5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)


def build(days_spec, base=2000.0):
    """Bars H1 từ đặc tả tay: days_spec là list các (ngày lịch, {giờ NY: (h, l)}).

    Giờ không có trong dict thì dùng (base+0.5, base-0.5) — một nến phẳng ở
    giữa dải, không kill được gì. Cho phép đặt chính xác high/low từng bar.
    """
    times, o, h, l, c = [], [], [], [], []
    for date_str, over in days_spec:
        d0 = pd.Timestamp(date_str)
        for hh in NY_HOURS:
            day = d0 + pd.Timedelta(days=0 if hh >= 17 else 1)
            times.append(epoch_for_ny(day.year, day.month, day.day, hh))
            hi, lo = over.get(hh, (base + 0.5, base - 0.5))
            h.append(hi); l.append(lo)
            o.append(base); c.append(base)
    return Bars(time=np.asarray(times, dtype="int64"),
                open=np.asarray(o, dtype="float64"),
                high=np.asarray(h, dtype="float64"),
                low=np.asarray(l, dtype="float64"),
                close=np.asarray(c, dtype="float64"))


def rows_for(bars, **kw):
    lab = label_h4(bars.time)
    days = aggregate_days(bars, lab, 3600, atr_period=2)
    return scan_kills(bars, lab, days, 3600, **kw)


def pick(rows, date_str, slot):
    r = rows[(rows["date"] == pd.Timestamp(date_str)) & (rows["slot"] == slot)]
    assert len(r) == 1, f"can dung 1 dong cho {date_str} slot {slot}, co {len(r)}"
    return r.iloc[0]


CALM = {}


def test_t_up_counts_bars_after_close():
    """Slot 0 của ngày 1 có high 2010. Bar thứ 3 sau khi nó đóng (giờ NY 23)
    vượt lên 2011 -> t_up = 3. Đếm BAR, không đếm đồng hồ."""
    day1 = {18: (2010.0, 1990.0), 23: (2011.0, 1999.5)}
    bars = build([("2026-01-05", day1), ("2026-01-06", CALM),
                  ("2026-01-07", CALM), ("2026-01-08", CALM)])
    r = pick(rows_for(bars), "2026-01-05", 0)
    assert r["cand_high"] == 2010.0 and r["cand_low"] == 1990.0
    assert r["t_up"] == 3.0
    assert np.isnan(r["t_dn"])
    assert bool(r["k_up"]) is True and bool(r["k_dn"]) is False
    assert r["exc_up"] == 1.0


def test_strict_comparison_touch_is_not_a_kill():
    """Chạm đúng mốc không tính là kill (spec §4.1, quy ước của stat_sweep)."""
    touch = {18: (2010.0, 1990.0), 23: (2010.0, 1990.0)}
    over = {18: (2010.0, 1990.0), 23: (2010.01, 1989.99)}
    for spec_day, want in ((touch, False), (over, True)):
        bars = build([("2026-01-05", spec_day), ("2026-01-06", CALM),
                      ("2026-01-07", CALM), ("2026-01-08", CALM)])
        r = pick(rows_for(bars), "2026-01-05", 0)
        assert bool(r["k_up"]) is want and bool(r["k_dn"]) is want


def test_both_ends_and_order():
    """Đầu dưới bị lấy ở bar 1, đầu trên ở bar 4 -> t_dn < t_up."""
    day1 = {18: (2010.0, 1990.0), 21: (2000.5, 1989.0), 0: (2011.0, 1999.5)}
    bars = build([("2026-01-05", day1), ("2026-01-06", CALM),
                  ("2026-01-07", CALM), ("2026-01-08", CALM)])
    r = pick(rows_for(bars), "2026-01-05", 0)
    assert (r["t_dn"], r["t_up"]) == (1.0, 4.0)
    assert bool(r["k_up"]) and bool(r["k_dn"])
    assert r["exc_dn"] == 1.0 and r["exc_up"] == 1.0


def test_window_lengths_per_slot():
    """Cửa sổ ① = tới hết ngày giao dịch. Slot 0 được 20 bar (5 slot còn lại
    trên H1), slot 4 được 4 bar. Đây chính là bất đối xứng của spec §4.2."""
    bars = build([("2026-01-05", CALM), ("2026-01-06", CALM),
                  ("2026-01-07", CALM), ("2026-01-08", CALM)])
    rows = rows_for(bars)
    got = {int(s): int(pick(rows, "2026-01-06", s)["w_bars"]) for s in range(5)}
    assert got == {0: 20, 1: 16, 2: 12, 3: 8, 4: 4}
    assert (rows.loc[rows["slot"] < 5, "w_from"] == 1).all()


def test_slot5_window_is_next_surviving_day():
    """Slot 5 đóng đúng lúc ngày kết thúc nên cửa sổ ① của nó là TRỌN ngày
    giao dịch còn sống kế tiếp — 23 bar trên H1."""
    bars = build([("2026-01-05", CALM), ("2026-01-06", CALM),
                  ("2026-01-07", CALM), ("2026-01-08", CALM)])
    r = pick(rows_for(bars), "2026-01-05", 5)
    assert (int(r["w_from"]), int(r["w_to"]), int(r["w_bars"])) == (1, 23, 23)
    assert int(r["gap_days"]) == 1 and bool(r["crosses_weekend"]) is False


def test_slot5_crosses_weekend_flag():
    """Thứ Sáu 2026-01-09 -> ngày giao dịch kế tiếp là 2026-01-11 (Chủ nhật
    18:00 NY = phiên thứ Hai): gap 2 ngày, cờ phải bật."""
    bars = build([("2026-01-08", CALM), ("2026-01-09", CALM),
                  ("2026-01-11", CALM), ("2026-01-12", CALM)])
    r = pick(rows_for(bars), "2026-01-09", 5)
    assert int(r["gap_days"]) == 2 and bool(r["crosses_weekend"]) is True


def test_slot5_dropped_when_gap_too_large():
    """gap_days > max_gap_days -> loại dòng. Mốc nằm im một tuần thì không còn
    là 'trong một ngày'."""
    bars = build([("2026-01-05", CALM), ("2026-01-06", CALM),
                  ("2026-01-20", CALM), ("2026-01-21", CALM)])
    rows = rows_for(bars)
    assert len(rows[(rows["date"] == pd.Timestamp("2026-01-06")) & (rows["slot"] == 5)]) == 0
    assert len(rows[(rows["date"] == pd.Timestamp("2026-01-06")) & (rows["slot"] == 0)]) == 1


def test_truncated_window_rows_are_dropped_not_reported_unkilled():
    """Ngày CUỐI không có ngày kế tiếp -> slot 5 của nó bị loại. Và slot 0..4
    của nó vẫn còn vì cửa sổ ① của chúng nằm trong chính ngày đó."""
    bars = build([("2026-01-05", CALM), ("2026-01-06", CALM),
                  ("2026-01-07", CALM), ("2026-01-08", CALM)])
    rows = rows_for(bars)
    last = rows[rows["date"] == pd.Timestamp("2026-01-08")]
    assert set(last["slot"]) == {0, 1, 2, 3, 4}


def test_h_avail_records_available_bars():
    bars = build([("2026-01-05", CALM), ("2026-01-06", CALM),
                  ("2026-01-07", CALM), ("2026-01-08", CALM)])
    rows = rows_for(bars, h_max_min=1440)     # 24 bar trên H1
    r = pick(rows, "2026-01-08", 4)
    assert r["h_avail"] == 4.0                # chỉ còn slot 5 của ngày cuối
    assert r["h_avail"] <= 24


def test_rel_range_and_year_columns():
    bars = build([("2026-01-05", CALM), ("2026-01-06", CALM),
                  ("2026-01-07", CALM), ("2026-01-08", CALM)])
    rows = rows_for(bars)
    ok = rows[np.isfinite(rows["day_atr"])]
    np.testing.assert_allclose(ok["rel_range"], ok["range_usd"] / ok["day_atr"])
    assert set(rows["year"]) == {2026}
    np.testing.assert_allclose(rows["range_usd"], rows["cand_high"] - rows["cand_low"])
    np.testing.assert_allclose(rows["w_hours"], rows["w_bars"] * 1.0)


def test_prefix_invariance_no_lookahead():
    """scan_kills trên tiền tố phải khớp trên toàn chuỗi ở mọi dòng có mặt cả
    hai bên. Nếu không khớp thì có look-ahead."""
    spec = [(f"2026-01-{d:02d}", CALM) for d in range(5, 25)]
    bars = build(spec)
    full = rows_for(bars, h_max_min=300)              # 5 bar trên H1
    cut = 23 * 15
    part = rows_for(bars.slice(0, cut), h_max_min=300)
    key = ["day_num", "slot"]
    common = sorted(set(map(tuple, part[key].to_numpy()))
                    & set(map(tuple, full[key].to_numpy())))
    assert len(common) > 60
    a = part.set_index(key).loc[common]
    b = full.set_index(key).loc[common]
    for col in ("w_from", "w_to", "w_bars", "k_up", "k_dn", "exc_up", "exc_dn"):
        pd.testing.assert_series_equal(a[col], b[col], check_names=False)
```

- [ ] **Step 2: Chạy test để chắc nó fail**

Run: `python -m pytest tests/test_h4_kill.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'rsi_fvg.h4_kill'`

- [ ] **Step 3: Viết implementation tối thiểu**

Tạo `rsi_fvg/h4_kill.py`:

```python
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
            recs.append({
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
            })
    return pd.DataFrame(recs)
```

- [ ] **Step 4: Chạy test để chắc nó pass**

Run: `python -m pytest tests/test_h4_kill.py -q` → PASS
Rồi cả suite: `python -m pytest -q` → **344 passed**.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/h4_kill.py tests/test_h4_kill.py
git commit -m "feat(h4_kill): scan_kills - bon nguyen thuy, cua so ① bang w_from/w_to"
```

---

## Task 4: Đại lượng ① ② ⑦ — tỉ lệ kill theo cửa sổ, theo horizon, và bối cảnh

**Files:**
- Modify: `rsi_fvg/h4_kill.py` (thêm vào cuối)
- Test: `tests/test_h4_kill.py` (thêm vào cuối)

**Interfaces:**
- Consumes: bảng dòng của `scan_kills` (Task 3); `N_SLOTS`, `HORIZONS_MIN`.
- Produces: `stat_kill_rate_window(rows) -> dict[str, float]`, `stat_kill_rate_horizon(rows, bar_seconds, horizons_min=HORIZONS_MIN) -> dict[str, float]`, `stat_context(rows) -> dict[str, float]`, và helper `_mean_or_nan(x) -> float`.

Từ đây trở đi mọi đại lượng là **hàm thuần của bảng dòng**, nên test dựng bảng bằng tay — không cần đi qua `Bars`. Đó là lý do bảng dòng là một `DataFrame` phẳng chứ không phải một object.

Khoá của dict theo mẫu `<đại lượng>_s<slot>`, và `run_grid` sẽ thêm tiền tố `<tên stat>.` — giống `quarter_stats.run_grid`.

- [ ] **Step 1: Viết test fail**

Thêm vào `tests/test_h4_kill.py`:

```python
from rsi_fvg.h4_kill import (stat_context, stat_kill_rate_horizon,
                             stat_kill_rate_window)


def mk_rows(recs):
    """Bảng dòng dựng tay. Mỗi rec chỉ cần các cột mà đại lượng đang test đọc;
    phần còn lại điền mặc định vô hại."""
    base = dict(day_num=0, date=pd.Timestamp("2026-01-05"), year=2026, slot=0,
                cand_high=2010.0, cand_low=1990.0, range_usd=20.0, day_atr=10.0,
                rel_range=2.0, w_from=1, w_to=20, w_bars=20, w_hours=20.0,
                gap_days=1, crosses_weekend=False, h_avail=1440,
                t_up=np.nan, t_dn=np.nan, k_up=False, k_dn=False,
                exc_up=np.nan, exc_dn=np.nan)
    return pd.DataFrame([{**base, **r} for r in recs])


def test_window_rates_split_four_ways():
    rows = mk_rows([
        {"slot": 0, "k_up": True, "k_dn": True},
        {"slot": 0, "k_up": True, "k_dn": False},
        {"slot": 0, "k_up": False, "k_dn": True},
        {"slot": 0, "k_up": False, "k_dn": False},
        {"slot": 4, "k_up": True, "k_dn": True, "w_bars": 4, "w_hours": 4.0},
    ])
    got = stat_kill_rate_window(rows)
    assert got["both_s0"] == 0.25 and got["up_only_s0"] == 0.25
    assert got["dn_only_s0"] == 0.25 and got["none_s0"] == 0.25
    assert got["n_s0"] == 4.0
    assert got["both_s4"] == 1.0 and got["n_s4"] == 1.0
    # Bốn nhóm phải khớp thành 1 — không dòng nào rơi ra ngoài
    assert got["both_s0"] + got["up_only_s0"] + got["dn_only_s0"] + got["none_s0"] == 1.0


def test_window_hours_reported_next_to_rate():
    """Spec §4.2: mọi bảng in ① phải in độ dài cửa sổ ngay cạnh, vì hai cây
    được hỏi nhận hai cửa sổ dài nhất."""
    rows = mk_rows([{"slot": 0, "w_hours": 20.0}, {"slot": 4, "w_hours": 4.0}])
    got = stat_kill_rate_window(rows)
    assert got["w_hours_s0"] == 20.0 and got["w_hours_s4"] == 4.0


def test_slot5_reported_twice_with_and_without_weekend_gap():
    rows = mk_rows([
        {"slot": 5, "k_up": True, "k_dn": True, "crosses_weekend": False},
        {"slot": 5, "k_up": False, "k_dn": False, "crosses_weekend": True},
    ])
    got = stat_kill_rate_window(rows)
    assert got["both_s5"] == 0.5
    assert got["both_s5_no_gap"] == 1.0 and got["n_s5_no_gap"] == 1.0


def test_horizon_uses_t_columns_and_filters_by_availability():
    """Kill trong horizon h ⇔ cả t_up và t_dn <= h_bars. Dòng không đủ bar để
    trả lời horizon đó bị loại KHỎI horizon đó, không tính là 'không kill'."""
    rows = mk_rows([
        {"slot": 0, "t_up": 2.0, "t_dn": 3.0, "h_avail": 100},   # kill trong 4 bar
        {"slot": 0, "t_up": 2.0, "t_dn": 90.0, "h_avail": 100},  # chỉ kill ở horizon dài
        {"slot": 0, "t_up": 1.0, "t_dn": 1.0, "h_avail": 2},     # không đủ bar
    ])
    got = stat_kill_rate_horizon(rows, bar_seconds=60, horizons_min=(4, 120))
    assert got["n_s0_h4"] == 2.0 and got["both_s0_h4"] == 0.5
    assert got["n_s0_h120"] == 2.0 and got["both_s0_h120"] == 1.0


def test_horizon_nan_never_counts_as_killed():
    rows = mk_rows([{"slot": 0, "t_up": np.nan, "t_dn": 1.0, "h_avail": 100}])
    got = stat_kill_rate_horizon(rows, bar_seconds=60, horizons_min=(60,))
    assert got["both_s0_h60"] == 0.0


def test_context_medians():
    rows = mk_rows([
        {"slot": 0, "range_usd": 4.0, "rel_range": 0.4, "day_atr": 10.0},
        {"slot": 0, "range_usd": 6.0, "rel_range": 0.6, "day_atr": 10.0},
    ])
    got = stat_context(rows)
    assert got["range_usd_s0"] == 5.0 and got["rel_range_s0"] == 0.5
    assert got["day_atr_s0"] == 10.0 and got["n_s0"] == 2.0


def test_empty_slot_gives_nan_not_zero():
    """Slot rỗng phải cho NaN, không cho 0 — 0 đọc thành 'không bao giờ kill'."""
    rows = mk_rows([{"slot": 0, "k_up": True, "k_dn": True}])
    got = stat_kill_rate_window(rows)
    assert np.isnan(got["both_s3"]) and got["n_s3"] == 0.0
```

- [ ] **Step 2: Chạy test để chắc nó fail**

Run: `python -m pytest tests/test_h4_kill.py -q`
Expected: FAIL — `ImportError: cannot import name 'stat_kill_rate_window'`

- [ ] **Step 3: Viết implementation tối thiểu**

Thêm vào `rsi_fvg/h4_kill.py`:

```python
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
```

- [ ] **Step 4: Chạy test để chắc nó pass**

Run: `python -m pytest tests/test_h4_kill.py -q` → PASS
Cả suite: `python -m pytest -q` → **351 passed**.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/h4_kill.py tests/test_h4_kill.py
git commit -m "feat(h4_kill): dai luong 1, 2, 7 - ti le kill theo cua so, theo horizon, boi canh"
```

---

## Task 5: Đại lượng ③ — tỉ lệ kill chuẩn hoá theo độ rộng

**Files:**
- Modify: `rsi_fvg/h4_kill.py` (thêm vào cuối)
- Test: `tests/test_h4_kill.py` (thêm vào cuối)

**Interfaces:**
- Consumes: bảng dòng; `STD_HORIZON_MIN = 720`; `_mean_or_nan`.
- Produces: `stat_kill_rate_standardized(rows, bar_seconds, horizon_min=STD_HORIZON_MIN, n_deciles=10) -> dict[str, float]` với khoá `std_s{k}`, `raw_s{k}`, `deciles_used_s{k}`, `n_s{k}`.

**Đây là task quan trọng nhất của cả plan.** `std_s0` và `std_s5` là hai con số duy nhất mà luật kết luận §10 dùng. Test ở Step 1 là **bằng chứng** rằng đại lượng này thật sự kiểm soát được cái nó nói là kiểm soát; nếu test đó không pass thì mọi kết luận của nghiên cứu vô giá trị.

Ba bước của spec §4.3 ③: (1) `rel_range = range / day_atr`; (2) chia decile **gộp cả sáu slot**; (3) chuẩn hoá trực tiếp — mỗi slot ra một số bằng trung bình có trọng số của tỉ lệ kill trong từng decile, trọng số là phân phối decile **gộp**.

`deciles_used_s{k}` bắt buộc phải có: một slot chuẩn hoá trên 4/10 decile thì con số của nó không so được với slot chuẩn hoá trên 10/10, và người đọc phải thấy điều đó.

- [ ] **Step 1: Viết test fail**

Thêm vào `tests/test_h4_kill.py`:

```python
from rsi_fvg.h4_kill import stat_kill_rate_standardized


def _width_confounded_rows():
    """Hai slot có phân phối độ rộng LỆCH NHAU nhưng tỉ lệ kill TRONG TỪNG
    decile BẰNG NHAU.

    slot 0: 80 cây hẹp + 20 cây rộng      slot 4: 20 hẹp + 80 rộng
    hẹp: kill 80%      rộng: kill 20%     (giống nhau ở cả hai slot)

    thô:  s0 = .8*.8 + .2*.2 = 0.68       s4 = .2*.8 + .8*.2 = 0.32
    trọng số gộp: hẹp 0.5, rộng 0.5
    chuẩn hoá: cả hai = .5*.8 + .5*.2 = 0.50
    """
    recs = []
    for slot, n_narrow, n_wide in ((0, 80, 20), (4, 20, 80)):
        for rel, n in ((1.0, n_narrow), (5.0, n_wide)):
            killed = int(round(n * (0.8 if rel == 1.0 else 0.2)))
            for i in range(n):
                t = 1.0 if i < killed else np.nan
                recs.append({"slot": slot, "rel_range": rel, "h_avail": 10_000,
                             "t_up": t, "t_dn": t})
    return mk_rows(recs)


def test_standardization_removes_the_width_confound():
    """Bằng chứng rằng ③ kiểm soát được độ rộng. Nếu test này fail thì mọi kết
    luận của nghiên cứu vô giá trị (spec §8 mục 6)."""
    got = stat_kill_rate_standardized(_width_confounded_rows(), bar_seconds=60,
                                      horizon_min=720, n_deciles=2)
    assert abs(got["raw_s0"] - 0.68) < 1e-9
    assert abs(got["raw_s4"] - 0.32) < 1e-9
    assert abs(got["raw_s0"] - got["raw_s4"]) > 0.3     # thô: khác xa
    assert abs(got["std_s0"] - 0.50) < 1e-9
    assert abs(got["std_s4"] - 0.50) < 1e-9
    assert abs(got["std_s0"] - got["std_s4"]) < 1e-9    # chuẩn hoá: bằng nhau


def test_deciles_used_is_reported():
    """Slot chỉ có quan sát ở một decile -> deciles_used = 1, và con số chuẩn
    hoá của nó không so được với slot có đủ hai decile."""
    recs = [{"slot": 0, "rel_range": 1.0, "h_avail": 10_000, "t_up": 1.0, "t_dn": 1.0}] * 50
    recs += [{"slot": 1, "rel_range": 5.0, "h_avail": 10_000, "t_up": 1.0, "t_dn": 1.0}] * 50
    got = stat_kill_rate_standardized(mk_rows(recs), bar_seconds=60,
                                      horizon_min=720, n_deciles=2)
    assert got["deciles_used_s0"] == 1.0 and got["deciles_used_s1"] == 1.0


def test_standardized_filters_by_horizon_availability_and_finite_rel_range():
    recs = [
        {"slot": 0, "rel_range": 1.0, "h_avail": 10_000, "t_up": 1.0, "t_dn": 1.0},
        {"slot": 0, "rel_range": 1.0, "h_avail": 2, "t_up": 1.0, "t_dn": 1.0},
        {"slot": 0, "rel_range": np.nan, "h_avail": 10_000, "t_up": 1.0, "t_dn": 1.0},
    ]
    got = stat_kill_rate_standardized(mk_rows(recs), bar_seconds=60,
                                      horizon_min=720, n_deciles=2)
    assert got["n_s0"] == 1.0


def test_standardized_empty_gives_nan():
    got = stat_kill_rate_standardized(mk_rows([]), bar_seconds=60)
    assert np.isnan(got["std_s0"]) and np.isnan(got["std_s5"])
```

- [ ] **Step 2: Chạy test để chắc nó fail**

Run: `python -m pytest tests/test_h4_kill.py -q`
Expected: FAIL — `ImportError: cannot import name 'stat_kill_rate_standardized'`

- [ ] **Step 3: Viết implementation tối thiểu**

Thêm vào `rsi_fvg/h4_kill.py`:

```python
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

    Tính tại horizon CHUNG (mặc định 720 phút), không tại cửa sổ ①, vì ① có độ
    dài khác nhau giữa các slot nên không so được (spec §4.2).
    """
    hb = horizon_min * 60 // bar_seconds
    out: dict[str, float] = {}
    if rows.empty:
        for s in range(N_SLOTS):
            out[f"std_s{s}"] = out[f"raw_s{s}"] = float("nan")
            out[f"deciles_used_s{s}"] = out[f"n_s{s}"] = 0.0
        return out

    r = rows[(rows["h_avail"] >= hb) & np.isfinite(rows["rel_range"])].copy()
    if r.empty:
        for s in range(N_SLOTS):
            out[f"std_s{s}"] = out[f"raw_s{s}"] = float("nan")
            out[f"deciles_used_s{s}"] = out[f"n_s{s}"] = 0.0
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
            continue
        by_dec = rs.groupby("dec")["killed"].mean()
        w = weights.reindex(by_dec.index)
        total = float(w.sum())
        out[f"std_s{s}"] = float((by_dec * w).sum() / total) if total > 0 else float("nan")
        out[f"deciles_used_s{s}"] = float(len(by_dec))
    return out
```

- [ ] **Step 4: Chạy test để chắc nó pass**

Run: `python -m pytest tests/test_h4_kill.py -q` → PASS
Cả suite: `python -m pytest -q` → **355 passed**.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/h4_kill.py tests/test_h4_kill.py
git commit -m "feat(h4_kill): dai luong 3 - ti le kill chuan hoa truc tiep theo decile do rong"
```

---

## Task 6: Đại lượng ④ ⑤ ⑥ — thứ tự hai đầu, và hai nghĩa của "max range kill"

**Files:**
- Modify: `rsi_fvg/h4_kill.py` (thêm vào cuối)
- Test: `tests/test_h4_kill.py` (thêm vào cuối)

**Interfaces:**
- Consumes: bảng dòng; `_mean_or_nan`.
- Produces: `PCTS = (50, 75, 90, 95)`; `stat_kill_order(rows) -> dict`; `stat_excursion_atr(rows) -> dict`; `stat_killed_range_atr(rows) -> dict`; `excursion_usd_by_year(rows) -> pd.DataFrame`; `killed_range_usd_by_year(rows) -> pd.DataFrame`.

**Ruling: đơn vị USD tách theo năm là bảng BÁO CÁO, không vào null.** Spec §4.4 đòi ba dạng đơn vị, nhưng chỉ dạng chia `day_atr` đi vào bộ chạy null — dạng USD tách theo năm sẽ sinh hàng nghìn khoá (10 năm × 6 slot × 2 chiều × 5 phân vị) và không có ý nghĩa gì khi so với null lệch mốc neo, vì lưới null cũng có cùng thị trường vàng. Hai hàm `*_by_year` trả `DataFrame` cho báo cáo.

- [ ] **Step 1: Viết test fail**

Thêm vào `tests/test_h4_kill.py`:

```python
from rsi_fvg.h4_kill import (excursion_usd_by_year, killed_range_usd_by_year,
                             stat_excursion_atr, stat_kill_order,
                             stat_killed_range_atr)


def test_kill_order_reports_same_bar_as_its_own_bucket():
    """Cùng một bar là phần KHÔNG XÁC ĐỊNH ĐƯỢC ở độ phân giải đang dùng. Nó
    được báo ra chứ không gán về một phía — engine có quy ước 'SL thắng khi
    trùng bar' nhưng đó là quy ước bảo thủ cho backtest, không phải sự thật."""
    rows = mk_rows([
        {"slot": 0, "k_up": True, "k_dn": True, "t_up": 3.0, "t_dn": 7.0},
        {"slot": 0, "k_up": True, "k_dn": True, "t_up": 9.0, "t_dn": 2.0},
        {"slot": 0, "k_up": True, "k_dn": True, "t_up": 5.0, "t_dn": 5.0},
        {"slot": 0, "k_up": True, "k_dn": False, "t_up": 1.0},   # không vào ④
    ])
    got = stat_kill_order(rows)
    assert got["n_s0"] == 3.0
    assert abs(got["up_first_s0"] - 1 / 3) < 1e-12
    assert abs(got["dn_first_s0"] - 1 / 3) < 1e-12
    assert abs(got["same_bar_s0"] - 1 / 3) < 1e-12
    assert abs(got["up_first_s0"] + got["dn_first_s0"] + got["same_bar_s0"] - 1.0) < 1e-12


def test_excursion_atr_percentiles_only_over_killed_rows():
    rows = mk_rows([
        {"slot": 0, "k_up": True, "exc_up": 1.0, "day_atr": 10.0},
        {"slot": 0, "k_up": True, "exc_up": 3.0, "day_atr": 10.0},
        {"slot": 0, "k_up": False, "exc_up": np.nan, "day_atr": 10.0},
        {"slot": 0, "k_dn": True, "exc_dn": 5.0, "day_atr": 10.0},
    ])
    got = stat_excursion_atr(rows)
    assert got["exc_up_atr_s0_p50"] == 0.2          # (0.1 + 0.3) / 2
    assert got["exc_up_atr_s0_max"] == 0.3
    assert got["exc_up_atr_s0_n"] == 2.0
    assert got["exc_dn_atr_s0_max"] == 0.5 and got["exc_dn_atr_s0_n"] == 1.0


def test_killed_range_atr_only_both_ends():
    """⑥ là nghĩa thứ hai của 'max range kill': range của cây bị quét CẢ HAI
    đầu — 'range rộng tới đâu thì vẫn còn bị quét hai chiều'."""
    rows = mk_rows([
        {"slot": 0, "k_up": True, "k_dn": True, "rel_range": 0.4},
        {"slot": 0, "k_up": True, "k_dn": True, "rel_range": 0.8},
        {"slot": 0, "k_up": True, "k_dn": False, "rel_range": 9.0},
    ])
    got = stat_killed_range_atr(rows)
    assert got["killed_rel_range_s0_max"] == 0.8    # 9.0 không vào: chỉ kill một đầu
    assert got["killed_rel_range_s0_n"] == 2.0


def test_by_year_tables_are_dataframes_split_by_year():
    """Spec §2.3b: range median đi từ 2,56 USD (2017) lên 33,53 (2026), gấp 13
    lần. Một phân vị USD gộp cả mẫu chỉ nói về 2025-2026, nên phải tách năm."""
    rows = mk_rows([
        {"slot": 0, "year": 2017, "k_up": True, "exc_up": 1.0, "k_dn": True,
         "exc_dn": 1.0, "range_usd": 3.0},
        {"slot": 0, "year": 2026, "k_up": True, "exc_up": 30.0, "k_dn": True,
         "exc_dn": 30.0, "range_usd": 40.0},
    ])
    exc = excursion_usd_by_year(rows)
    assert set(exc["year"]) == {2017, 2026}
    assert float(exc[exc["year"] == 2017]["exc_up_max"].iloc[0]) == 1.0
    assert float(exc[exc["year"] == 2026]["exc_up_max"].iloc[0]) == 30.0
    rng = killed_range_usd_by_year(rows)
    assert float(rng[rng["year"] == 2026]["range_usd_max"].iloc[0]) == 40.0


def test_empty_percentile_block_gives_nan_and_zero_n():
    got = stat_excursion_atr(mk_rows([]))
    assert np.isnan(got["exc_up_atr_s0_p90"]) and got["exc_up_atr_s0_n"] == 0.0
```

- [ ] **Step 2: Chạy test để chắc nó fail**

Run: `python -m pytest tests/test_h4_kill.py -q`
Expected: FAIL — `ImportError: cannot import name 'stat_kill_order'`

- [ ] **Step 3: Viết implementation tối thiểu**

Thêm vào `rsi_fvg/h4_kill.py`:

```python
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
```

- [ ] **Step 4: Chạy test để chắc nó pass**

Run: `python -m pytest tests/test_h4_kill.py -q` → PASS
Cả suite: `python -m pytest -q` → **360 passed**.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/h4_kill.py tests/test_h4_kill.py
git commit -m "feat(h4_kill): dai luong 4, 5, 6 - thu tu hai dau va hai nghia max range kill"
```

---

## Task 7: Null A — `make_offsets(cycle_seconds=...)` và `run_grid`/`run_null`

**Files:**
- Modify: `rsi_fvg/quarter_stats.py:190-215` (hàm `make_offsets`) — **thuần thêm một tham số**
- Modify: `rsi_fvg/h4_kill.py` (thêm vào cuối)
- Test: `tests/test_quarter_stats.py` (thêm vào cuối), `tests/test_h4_kill.py` (thêm vào cuối)

**Interfaces:**
- Consumes: `rsi_fvg.quarter_stats.{make_offsets, percentile_of}`; `rsi_fvg.h4_grid.{label_h4, aggregate_days, DAY_SECONDS}`; mọi `stat_*` của Task 4–6.
- Produces: `make_offsets(tier, bar_seconds, shifts, seed, cycle_seconds=None)` (chữ ký cũ vẫn dùng được y nguyên); `build_stats(bar_seconds) -> dict[str, callable]`; `run_grid(bars, bar_seconds, anchor_offset=0, stats=None, **agg_kw) -> tuple[dict, pd.DataFrame]`; `run_null(bars, bar_seconds, offsets, stats=None, **agg_kw) -> pd.DataFrame`.

**`make_offsets` phải KHÔNG đổi hành vi khi không truyền `cycle_seconds`.** Hai study Quarterly Theory đang dùng nó và số của chúng đã được công bố. Thà thêm một tham số còn hơn copy một hàm có ba quyết định được lập luận cẩn thận trong docstring (snap về bội số `bar_seconds`, lấy trọn chu kỳ, loại lân cận 0).

- [ ] **Step 1: Viết test fail**

Thêm vào `tests/test_quarter_stats.py`:

```python
def test_make_offsets_unchanged_without_cycle_seconds():
    """Hai study Quarterly Theory dùng hàm này và số của chúng đã công bố.
    Thêm tham số không được đổi một bit hành vi cũ."""
    a = make_offsets("session", 300, 5, 20260909)
    b = make_offsets("session", 300, 5, 20260909, cycle_seconds=None)
    np.testing.assert_array_equal(a, b)
    # chu kỳ session = 4 * 21600 = 86400 s; lưới 300 s; loại lân cận 600 s
    full = make_offsets("session", 300, 10_000, 1)
    assert full.min() == 600 and full.max() == 86400 - 600
    assert full.size == (86400 // 300) - 3      # bỏ 0, 300, và 86400-300


def test_make_offsets_cycle_seconds_overrides_tier():
    """Lưới H4 có chu kỳ NGÀY (6 slot), không khớp giả định 4-quarter của TIERS,
    nên nó truyền cycle_seconds và tier bị bỏ qua hoàn toàn."""
    got = make_offsets("", 3600, 10_000, 1, cycle_seconds=86400)
    assert got.min() == 3600 and got.max() == 86400 - 3600
    assert got.size == 23
    # tier rác cũng không sao khi đã có cycle_seconds
    assert make_offsets("khong-ton-tai", 3600, 5, 1, cycle_seconds=86400).size == 5
```

Thêm vào `tests/test_h4_kill.py`:

```python
from rsi_fvg.h4_grid import DAY_SECONDS
from rsi_fvg.h4_kill import build_stats, run_grid, run_null
from rsi_fvg.quarter_stats import make_offsets, percentile_of


def test_run_grid_returns_prefixed_keys_and_rows():
    bars = build([(f"2026-01-{d:02d}", CALM) for d in range(5, 25)])
    flat, rows = run_grid(bars, 3600, atr_period=2)
    assert len(rows) > 100
    assert "window.both_s0" in flat and "standardized.std_s5" in flat
    assert "horizon.both_s0_h240" in flat and "context.range_usd_s0" in flat
    assert "order.same_bar_s0" in flat and "excursion_atr.exc_up_atr_s0_p90" in flat
    assert "killed_range_atr.killed_rel_range_s0_max" in flat
    assert all("." in k for k in flat)


def test_run_grid_shifted_grid_gives_different_labels():
    """anchor_offset khác 0 phải cho một lưới khác — nếu không thì null vô nghĩa."""
    bars = build([(f"2026-01-{d:02d}", CALM) for d in range(5, 25)])
    a, _ = run_grid(bars, 3600, anchor_offset=0, atr_period=2)
    b, _ = run_grid(bars, 3600, anchor_offset=2 * 3600, atr_period=2)
    assert a["context.range_usd_s0"] != b["context.range_usd_s0"] or \
           a["window.n_s0"] != b["window.n_s0"]


def test_run_null_one_row_per_offset():
    bars = build([(f"2026-01-{d:02d}", CALM) for d in range(5, 25)])
    offs = make_offsets("", 3600, 4, 1, cycle_seconds=DAY_SECONDS)
    nulls = run_null(bars, 3600, offs, atr_period=2)
    assert len(nulls) == len(offs)
    assert list(nulls["anchor_offset"]) == [int(x) for x in offs]
    assert "standardized.std_s0" in nulls.columns


def test_percentile_of_reused_from_quarter_stats():
    """Không viết lại percentile — dùng đúng hàm mà hai study cũ dùng."""
    assert percentile_of(0.5, np.array([0.1, 0.2, 0.9])) == pytest.approx(200 / 3)
    assert np.isnan(percentile_of(float("nan"), np.array([0.1])))


def test_build_stats_binds_bar_seconds():
    """horizon và standardized cần bar_seconds; chúng được bind sẵn để bộ chạy
    null gọi mọi stat với đúng một tham số (cùng giao ước quarter_stats.STATS)."""
    table = build_stats(3600)
    rows = mk_rows([{"slot": 0, "t_up": 1.0, "t_dn": 1.0, "h_avail": 10_000}])
    for name, fn in table.items():
        got = fn(rows)
        assert isinstance(got, dict) and got, name
```

- [ ] **Step 2: Chạy test để chắc nó fail**

Run: `python -m pytest tests/test_quarter_stats.py tests/test_h4_kill.py -q`
Expected: FAIL — `TypeError: make_offsets() got an unexpected keyword argument 'cycle_seconds'` và `ImportError: cannot import name 'run_grid'`

- [ ] **Step 3: Viết implementation tối thiểu**

Trong `rsi_fvg/quarter_stats.py`, thay hàm `make_offsets` bằng **đúng** phiên bản dưới đây. Chỉ có hai thay đổi so với bản hiện tại — thêm tham số `cycle_seconds` vào chữ ký, và dòng `cycle = ...`; ba quyết định trong docstring giữ nguyên từng chữ vì chúng là lý lẽ, không phải mô tả:

```python
def make_offsets(tier: str, bar_seconds: int, shifts: int, seed: int,
                 cycle_seconds: int | None = None) -> np.ndarray:
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

    `cycle_seconds` cho caller tự đặt độ dài chu kỳ thay vì tra `TIERS`. Nghiên
    cứu H4 kill (spec riêng §5.1) có chu kỳ NGÀY với SÁU slot, không khớp giả
    định bốn-quarter của `TIERS`, nên nó truyền 86400 và `tier` bị bỏ qua. Không
    truyền thì hành vi cũ không đổi một bit — hai study Quarterly Theory phụ
    thuộc vào điều đó, và số của chúng đã được công bố.
    """
    cycle = 4 * TIERS[tier] if cycle_seconds is None else int(cycle_seconds)
    grid = np.arange(0, cycle, bar_seconds, dtype="int64")
    ok = (grid >= OFFSET_EXCLUDE) & (grid <= cycle - OFFSET_EXCLUDE)
    candidates = grid[ok]
    if candidates.size <= shifts:
        return candidates
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(candidates, size=shifts, replace=False))
```

Lưu ý `TIERS[tier]` chỉ được tra khi `cycle_seconds is None` — biểu thức điều kiện đảm bảo điều đó, nên `tier=""` không nổ `KeyError`. Đó là cái test `test_make_offsets_cycle_seconds_overrides_tier` kiểm.

Thêm vào `rsi_fvg/h4_kill.py`:

```python
from functools import partial

from .h4_grid import DAY_SECONDS, aggregate_days, label_h4


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
    `quarter_stats.make_offsets(..., cycle_seconds=DAY_SECONDS)`."""
    recs = []
    for off in np.asarray(offsets, dtype="int64"):
        rec: dict[str, float] = {"anchor_offset": int(off)}
        rec.update(run_grid(bars, bar_seconds, int(off), stats, **agg_kw)[0])
        recs.append(rec)
    return pd.DataFrame(recs)
```

Thêm `import pytest` vào `tests/test_h4_kill.py` nếu chưa có.

- [ ] **Step 4: Chạy test để chắc nó pass**

Run: `python -m pytest tests/test_quarter_stats.py tests/test_h4_kill.py -q` → PASS
Cả suite: `python -m pytest -q` → **367 passed**. **Nếu bất kỳ test Quarterly Theory nào đổi, DỪNG và báo** — `make_offsets` phải thuần thêm.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/quarter_stats.py rsi_fvg/h4_kill.py tests/test_quarter_stats.py tests/test_h4_kill.py
git commit -m "feat(h4_kill): Null A - run_grid/run_null va make_offsets nhan cycle_seconds"
```

---

## Task 8: Cổng chặn dò timezone của nguồn

**Files:**
- Create: `rsi_fvg/data/tz_detect.py`
- Test: `tests/test_tz_detect.py`

**Interfaces:**
- Consumes: `rsi_fvg.quarters.NY_TZ`.
- Produces: `MIN_SCORE = 0.70`, `MIN_MARGIN = 0.30`, `BEFORE_HOUR = 16`, `AFTER_HOUR = 18`, `MIN_GAPS = 30`, `CANDIDATE_OFFSETS`, `CANDIDATE_ZONES`; dataclass `TzDetect(best, score, runner_up, runner_up_score, table, n_gaps, ok, notes)`; `detect_source_tz(time, bar_seconds) -> TzDetect`; `to_ny(time, label) -> pd.DatetimeIndex`.

**Tiêu chí và ngưỡng đều là số ĐO ĐƯỢC, không phải số chọn bừa** (spec §6.1). Trên 3.299.723 bar M1 của XAUUSDc:

```
khe nghỉ hằng ngày: N = 2290
P(bar cuối trước khe ở giờ 16 NY) = 0,8179
P(bar đầu sau khe  ở giờ 18 NY) = 0,9109
score đọc đúng = 0,8644     lệch −1h = 0,0020     lệch +1h = 0,0155
                            lệch −2h = 0,0094     lệch +2h = 0,0181
```

Ngưỡng 0,70 chứ không phải 0,90 vì cách đọc **đúng** chỉ đạt 0,8644 — đặt 0,90 là tự chặn chính mình. Biên 0,30 rộng rãi vì khoảng cách thật là 0,86 so với 0,02.

Không dùng mốc mở tuần: nó chỉ có 331 mẫu sạch, 81% rơi vào giờ kỳ vọng, cần cửa sổ hai giờ rộng nên offset ±1h vẫn lọt — và bộ dữ liệu này còn có 163 bar Thứ Bảy lạc làm sai 22% phép đếm khe cuối tuần (spec §11 mục 10).

- [ ] **Step 1: Viết test fail**

Tạo `tests/test_tz_detect.py`:

```python
import numpy as np
import pandas as pd

from conftest import epoch_for_ny
from rsi_fvg.data.tz_detect import MIN_SCORE, detect_source_tz, to_ny

# Một ngày giao dịch H1: khe nghỉ 17:00-18:00 NY bị bỏ, đúng như dữ liệu thật.
NY_HOURS = (18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4,
            5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)


def daily_break_series(n_days=60, start="2026-01-05"):
    d0 = pd.Timestamp(start)
    out = []
    for i in range(n_days):
        for hh in NY_HOURS:
            day = d0 + pd.Timedelta(days=i + (0 if hh >= 17 else 1))
            out.append(epoch_for_ny(day.year, day.month, day.day, hh))
    return np.asarray(sorted(out), dtype="int64")


def test_detects_utc_on_true_utc_epochs():
    got = detect_source_tz(daily_break_series(), 3600)
    assert got.ok and got.best == "UTC"
    assert got.score > 0.99 and got.n_gaps >= 55


def test_detects_wall_clock_source_shifted_three_hours():
    """CSV export ghi giờ treo tường của platform. Nếu platform đặt UTC+3 thì
    nhãn thời gian lớn hơn instant thật 3 giờ, và cổng phải nhận ra."""
    got = detect_source_tz(daily_break_series() + 3 * 3600, 3600)
    assert got.ok and got.best == "+03:00" and got.score > 0.99


def test_wrong_reading_scores_near_zero():
    """Đây là điều làm cổng có ích: lệch một giờ thì điểm sụp, không chỉ giảm."""
    t = daily_break_series()
    d = np.diff(t)
    after = np.flatnonzero((d > 3600) & (d <= 86400)) + 1
    right = to_ny(t, "UTC")
    wrong = to_ny(t, "+01:00")
    assert (right[after].hour == 18).mean() > 0.99
    assert (wrong[after].hour == 18).mean() < 0.05


def test_fails_on_structureless_series():
    rng = np.random.default_rng(0)
    grid = np.arange(1_700_000_000, 1_700_000_000 + 3600 * 24 * 400, 3600)
    t = np.sort(rng.choice(grid, 6000, replace=False))
    got = detect_source_tz(t, 3600)
    assert not got.ok
    assert got.score < MIN_SCORE
    assert got.notes


def test_fails_when_too_few_gaps():
    t = daily_break_series(n_days=3)
    got = detect_source_tz(t, 3600)
    assert not got.ok and got.n_gaps < 30


def test_table_is_sorted_descending_and_includes_every_candidate():
    got = detect_source_tz(daily_break_series(), 3600)
    scores = [s for _, s in got.table]
    assert scores == sorted(scores, reverse=True)
    labels = [lab for lab, _ in got.table]
    assert "UTC" in labels and "America/New_York" in labels and "+07:00" in labels
    assert got.best == labels[0] and got.runner_up == labels[1]
```

- [ ] **Step 2: Chạy test để chắc nó fail**

Run: `python -m pytest tests/test_tz_detect.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'rsi_fvg.data.tz_detect'`

- [ ] **Step 3: Viết implementation tối thiểu**

Tạo `rsi_fvg/data/tz_detect.py`:

```python
"""Dò timezone của nguồn dữ liệu bằng khe nghỉ hằng ngày — cổng CHẶN.

Spec: docs/superpowers/specs/2026-09-09-h4-kill-both-ends-study-design.md §6.1.

`quarters.verify_server_tz` hardcode nguồn là UTC vì epoch của MT5 đã được kiểm
là UTC thật. CSV export từ Trading Station thì theo timezone HIỂN THỊ của
platform — người dùng đặt sao nó ra vậy, và nghiên cứu này không được giả định.
Lệch một giờ nghĩa là đo một lưới khác.

Tiêu chí là khe nghỉ hằng ngày (17:00->18:00 NY), không phải mốc mở tuần. Đo
trên 3.299.723 bar M1 của XAUUSDc:

    khe nghỉ: N = 2290
    P(bar cuối trước khe ở giờ 16 NY) = 0,8179
    P(bar đầu sau khe  ở giờ 18 NY) = 0,9109
    score đọc đúng 0,8644 | lệch -1h 0,0020 | +1h 0,0155 | -2h 0,0094 | +2h 0,0181

Mốc mở tuần tệ hơn hẳn: chỉ 331 mẫu sạch, 81% rơi vào giờ kỳ vọng, cửa sổ hai
giờ rộng nên offset ±1h vẫn lọt qua. Bộ dữ liệu này còn có 163 bar Thứ Bảy lạc
làm sai 22% phép đếm khe cuối tuần.

Ngưỡng 0,70 chứ không phải 0,90 vì cách đọc ĐÚNG trên dữ liệu thật chỉ đạt
0,8644 — ngày lễ rút ngắn ăn vào phần còn lại. Đặt 0,90 là tự chặn chính mình.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..quarters import NY_TZ

DAILY_GAP_MAX = 86400
BEFORE_HOUR = 16
AFTER_HOUR = 18
MIN_SCORE = 0.70
MIN_MARGIN = 0.30
MIN_GAPS = 30
CANDIDATE_OFFSETS = tuple(range(-12, 15))
CANDIDATE_ZONES = ("America/New_York", "Europe/Athens")


@dataclass(frozen=True)
class TzDetect:
    best: str
    score: float
    runner_up: str
    runner_up_score: float
    table: tuple[tuple[str, float], ...]
    n_gaps: int
    ok: bool
    notes: tuple[str, ...]


def candidate_labels() -> list[str]:
    """Offset 0 chỉ xuất hiện một lần, dưới tên "UTC"."""
    offs = [f"{k:+03d}:00" for k in CANDIDATE_OFFSETS if k != 0]
    return ["UTC"] + offs + list(CANDIDATE_ZONES)


def to_ny(time: np.ndarray, label: str) -> pd.DatetimeIndex:
    """Đọc `time` theo cách `label` mô tả rồi convert sang giờ New York.

    "UTC" và "+hh:00" nghĩa là nhãn thời gian là giờ treo tường của offset cố
    định đó, nên instant thật là `t - offset`. Zone có tên thì localize trực tiếp
    (nguồn có DST riêng); giờ nhập nhằng hoặc không tồn tại thành NaT và bị tính
    là TRƯỢT, không bị bỏ qua — bỏ qua sẽ thổi điểm của một cách đọc sai.
    """
    naive = pd.to_datetime(np.asarray(time, dtype="int64"), unit="s")
    if label == "UTC":
        return naive.tz_localize("UTC").tz_convert(NY_TZ)
    if label[0] in "+-":
        hours = int(label[:3])
        return (naive - pd.Timedelta(hours=hours)).tz_localize("UTC").tz_convert(NY_TZ)
    return naive.tz_localize(label, ambiguous="NaT",
                             nonexistent="NaT").tz_convert(NY_TZ)


def _hour_hits(ny: pd.DatetimeIndex, idx: np.ndarray, want: int) -> float:
    """Tỉ lệ, KHÔNG phải mode: mode ẩn mất chuyện một đoạn lịch sử bị lệch, và
    đó chính là lỗ hổng đã ghi ở §8 mục 5 spec Quarterly Theory Phase 1."""
    if idx.size == 0:
        return 0.0
    # `.hour` cho float64 với NaN ở vị trí NaT, và NaN không bao giờ bằng
    # `want`, nên giờ nhập nhằng/không tồn tại tự động tính là TRƯỢT. Đó là
    # điều ta muốn: bỏ qua chúng sẽ thổi điểm của một cách đọc sai.
    hour = np.asarray(ny[idx].hour, dtype="float64")
    return float(np.mean(hour == want))


def detect_source_tz(time: np.ndarray, bar_seconds: int) -> TzDetect:
    t = np.asarray(time, dtype="int64")
    if t.size < 2:
        return TzDetect("", float("nan"), "", float("nan"), (), 0, False,
                        ("chuoi qua ngan",))
    d = np.diff(t)
    after = np.flatnonzero((d > bar_seconds) & (d <= DAILY_GAP_MAX)) + 1
    if after.size < MIN_GAPS:
        return TzDetect("", float("nan"), "", float("nan"), (), int(after.size),
                        False, (f"chi co {after.size} khe trong ngay, "
                                f"can >= {MIN_GAPS}",))

    scored: list[tuple[str, float]] = []
    for label in candidate_labels():
        try:
            ny = to_ny(t, label)
        except Exception:                         # zone không có trên máy này
            continue
        score = 0.5 * _hour_hits(ny, after - 1, BEFORE_HOUR) \
            + 0.5 * _hour_hits(ny, after, AFTER_HOUR)
        scored.append((label, score))
    scored.sort(key=lambda x: -x[1])

    best, bs = scored[0]
    runner, rs = scored[1]
    notes: list[str] = []
    if bs < MIN_SCORE:
        notes.append(f"diem tot nhat {bs:.4f} < nguong {MIN_SCORE}")
    if bs - rs < MIN_MARGIN:
        notes.append(f"bien {bs - rs:.4f} < {MIN_MARGIN}: {best!r} va {runner!r} "
                     f"khong phan biet duoc")
    ok = bs >= MIN_SCORE and (bs - rs) >= MIN_MARGIN
    return TzDetect(best=best, score=bs, runner_up=runner, runner_up_score=rs,
                    table=tuple(scored), n_gaps=int(after.size), ok=ok,
                    notes=tuple(notes))
```

- [ ] **Step 4: Chạy test để chắc nó pass**

Run: `python -m pytest tests/test_tz_detect.py -q` → PASS
Cả suite: `python -m pytest -q` → **373 passed**.

Kiểm bằng tay trên dữ liệu thật — **con số này phải khớp docstring**, nếu không thì có gì đã đổi:

```bash
python -c "import pandas as pd; from rsi_fvg.data.tz_detect import detect_source_tz; d=pd.read_parquet('data/XAUUSDc_M1.parquet'); g=detect_source_tz(d['time'].to_numpy('int64'),60); print(g.best, round(g.score,4), g.n_gaps, g.ok); print(g.table[:4])"
```
Expected: `UTC 0.8644 2290 True`, và ứng viên nhì có điểm dưới 0,02.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/data/tz_detect.py tests/test_tz_detect.py
git commit -m "feat(tz_detect): cong chan do timezone nguon bang khe nghi hang ngay"
```

---

## Task 9: Dialect FXCM cho `csv_loader`

**Files:**
- Modify: `rsi_fvg/data/csv_loader.py` (cả file, 27 dòng)
- Test: `tests/test_csv_loader.py` (thêm vào cuối)

**Interfaces:**
- Consumes: `rsi_fvg.data.mt5_loader.RATE_COLUMNS = ["time", "open", "high", "low", "close", "tick_volume", "spread"]`.
- Produces: `load_csv(path, point: float = 0.001) -> pd.DataFrame` (chữ ký cũ `load_csv(path)` vẫn dùng được); `FXCM_BID_MAP`, `FXCM_ASK_COLS`.

**Bối cảnh:** FXCM không phát lịch sử vàng miễn phí (spec §6.3 — đã kiểm: `candledata.fxcorporate.com` trả về EURUSD/GBPUSD/USDJPY nhưng XAUUSD 404; `api-demo.fxcm.com` không resolve; `forexconnect` không có wheel cho Python 3.13). Đường đã chọn là người dùng export CSV từ Trading Station. Cột của nó là `DateTime, BidOpen, BidHigh, BidLow, BidClose, AskOpen, AskHigh, AskLow, AskClose`.

**Ruling: `point` là tham số, không phải hằng số.** Repo lưu `spread` theo đơn vị point (int64) nhưng `load_csv` không có `SymbolSpec` nên không biết point là bao nhiêu. Mặc định 0,001 khớp `data/XAUUSDc.spec.json`. Chỉ dùng khi CSV có cột Ask; không có Ask thì `spread = 0` như cũ.

Spread chỉ dùng cho **một dòng chú thích** trong báo cáo (spec §11 mục 4: giá là Bid nên tỉ lệ kill đầu trên thực tế cao hơn con số báo, và thiên lệch đó một phía). Không sửa số nào theo nó.

- [ ] **Step 1: Viết test fail**

Thêm vào `tests/test_csv_loader.py`:

```python
def test_load_csv_fxcm_dialect_uses_bid_and_computes_spread(tmp_path):
    """Trading Station export dùng DateTime + BidOpen..AskClose. Repo dùng BID
    (Bars docstring), và spread lấy từ chênh Ask-Bid theo đơn vị point."""
    p = tmp_path / "fxcm.csv"
    p.write_text(
        "DateTime,BidOpen,BidHigh,BidLow,BidClose,AskOpen,AskHigh,AskLow,AskClose\n"
        "2025-01-01 00:00:00,2000.0,2001.0,1999.0,2000.5,2000.2,2001.2,1999.2,2000.8\n"
        "2025-01-01 01:00:00,2000.5,2002.0,2000.0,2001.5,2000.7,2002.2,2000.2,2001.7\n"
    )
    df = load_csv(p, point=0.001)
    assert list(df.columns) == RATE_COLUMNS
    assert df["close"].iloc[0] == 2000.5          # BID, không phải ASK
    assert df["high"].iloc[0] == 2001.0
    assert df["spread"].iloc[0] == 300            # (2000.8 - 2000.5) / 0.001
    assert df["time"].iloc[0] == int(pd.Timestamp("2025-01-01 00:00:00", tz="UTC").timestamp())


def test_load_csv_fxcm_bid_only_export(tmp_path):
    """Export chỉ có Bid thì spread = 0, không nổ."""
    p = tmp_path / "bid.csv"
    p.write_text("DateTime,BidOpen,BidHigh,BidLow,BidClose\n"
                 "2025-01-01 00:00:00,2000.0,2001.0,1999.0,2000.5\n")
    df = load_csv(p)
    assert df["close"].iloc[0] == 2000.5 and df["spread"].iloc[0] == 0


def test_load_csv_default_point_matches_xauusdc_spec(tmp_path):
    """Mặc định 0.001 khớp data/XAUUSDc.spec.json — gọi không truyền point vẫn
    ra số đúng cho symbol mà nghiên cứu này dùng."""
    p = tmp_path / "d.csv"
    p.write_text("DateTime,BidClose,BidOpen,BidHigh,BidLow,AskClose\n"
                 "2025-01-01 00:00:00,2000.0,2000.0,2000.0,2000.0,2000.26\n")
    assert load_csv(p)["spread"].iloc[0] == 260
```

- [ ] **Step 2: Chạy test để chắc nó fail**

Run: `python -m pytest tests/test_csv_loader.py -q`
Expected: FAIL — `KeyError: 'open'` (loader chưa hiểu cột Bid*)

- [ ] **Step 3: Viết implementation tối thiểu**

Thay `rsi_fvg/data/csv_loader.py` bằng:

```python
"""CSV fallback loader. Nhận epoch seconds hoặc chuỗi datetime trong `time`.

Hiểu hai dialect:
  - dialect gốc: `time, open, high, low, close[, spread, tick_volume]`
  - dialect FXCM Trading Station: `DateTime, BidOpen..BidClose[, AskOpen..AskClose]`

FXCM không phát lịch sử vàng miễn phí (spec H4-kill §6.3), nên đường lấy dữ liệu
XAUUSD của FXCM là export CSV từ Trading Station — đó là lý do dialect thứ hai
tồn tại. Dùng BID theo thông lệ repo (`Bars` docstring: "Prices are BID").
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .mt5_loader import RATE_COLUMNS

FXCM_BID_MAP = {"bidopen": "open", "bidhigh": "high",
                "bidlow": "low", "bidclose": "close"}
FXCM_ASK_COLS = ("askopen", "askhigh", "asklow", "askclose")


def load_csv(path: str | Path, point: float = 0.001) -> pd.DataFrame:
    """Nạp CSV thành frame `RATE_COLUMNS`.

    `point` chỉ dùng khi CSV có cột Ask: repo lưu `spread` theo đơn vị point
    (int64) nhưng loader này không có `SymbolSpec` nên không tự biết point.
    Mặc định 0,001 khớp `data/XAUUSDc.spec.json`. Spread chỉ để chú thích trong
    báo cáo (nghiên cứu H4-kill §11 mục 4: giá là Bid nên tỉ lệ kill đầu trên
    thực tế CAO HƠN con số báo, thiên lệch một phía) — không sửa số nào theo nó.
    """
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "datetime" in df.columns and "time" not in df.columns:
        df = df.rename(columns={"datetime": "time"})

    spread_points = None
    if "bidclose" in df.columns:
        if "askclose" in df.columns:
            spread_points = ((df["askclose"].astype(float)
                              - df["bidclose"].astype(float)) / point).round()
        df = df.rename(columns=FXCM_BID_MAP)
        df = df.drop(columns=[c for c in FXCM_ASK_COLS if c in df.columns])

    t = df["time"]
    if np.issubdtype(t.dtype, np.number):
        time = t.astype("int64")
    else:
        time = (pd.to_datetime(t, utc=True).astype("int64") // 1_000_000_000).astype("int64")

    out = pd.DataFrame({"time": time})
    for c in ("open", "high", "low", "close"):
        out[c] = df[c].astype(float)
    out["tick_volume"] = df["tick_volume"].astype("int64") if "tick_volume" in df else 0
    if spread_points is not None:
        out["spread"] = spread_points.astype("int64")
    else:
        out["spread"] = df["spread"].astype("int64") if "spread" in df else 0
    out = out.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return out[RATE_COLUMNS]
```

- [ ] **Step 4: Chạy test để chắc nó pass**

Run: `python -m pytest tests/test_csv_loader.py -q` → PASS (5 test: 2 cũ + 3 mới)
Cả suite: `python -m pytest -q` → **376 passed**. **Hai test cũ phải xanh không sửa** — dialect là thuần thêm.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/data/csv_loader.py tests/test_csv_loader.py
git commit -m "feat(csv_loader): dialect FXCM Trading Station - DateTime, Bid*, spread tu Ask"
```

---

## Task 10: `scripts/study_h4_kill.py` — CLI, cổng chặn, báo cáo, phán quyết

**Files:**
- Create: `scripts/study_h4_kill.py`
- Test: `tests/test_h4_kill.py` (thêm test cho `verdict`)

**Interfaces:**
- Consumes: `rsi_fvg.bars.Bars`; `rsi_fvg.data.mt5_loader.load_or_fetch(symbol, tf, data_dir) -> tuple[pd.DataFrame, SymbolSpec]`; `rsi_fvg.data.csv_loader.load_csv`; `rsi_fvg.data.tz_detect.detect_source_tz`; `rsi_fvg.h4_kill.{run_grid, run_null, excursion_usd_by_year, killed_range_usd_by_year, STD_HORIZON_MIN}`; `rsi_fvg.h4_grid.DAY_SECONDS`; `rsi_fvg.quarter_stats.{make_offsets, percentile_of}`.
- Produces: `verdict(real: dict, stats: pd.DataFrame) -> tuple[bool, str]` (import được từ script để test); `main(argv=None) -> int`.

Theo đúng khuôn `scripts/study_quarters.py`: cổng chặn in ra rồi `sys.exit(1)` nếu fail, `stats.csv` + `summary.md` trong `results/`, phán quyết tính **bằng máy** chứ không để người đọc tự kết luận, và `DataFrame.to_string` trong khối ``` thay vì `to_markdown` (cần `tabulate`, không có trong requirements).

**Luật kết luận §10, chốt trước khi chạy — HAI cổng, không phải ba:**

> Một slot ĐẶC BIỆT khi và chỉ khi: **(a)** `standardized.std_s{k}` (horizon 720 phút) cao hơn cả bốn slot đối chứng (1, 2, 3, 4); **và (b)** giá trị đó vượt percentile 95 của Null A.
> Phase 2 được phép viết spec khi và chỉ khi slot 0 **hoặc** slot 5 đạt cả hai cổng.

Cổng thứ ba (Null B) đã bị người dùng loại khỏi phạm vi (spec §5.3). Báo cáo phải nói ra ở chỗ dễ thấy rằng kể cả khi hai cổng đạt, kết luận đúng là "lưới 17:00 NY khác lưới bất kỳ, sau khi kiểm soát độ rộng" — **không** phải "mốc H4 phiên Á bị nhắm".

- [ ] **Step 1: Viết test fail**

Thêm vào `tests/test_h4_kill.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _stats_frame(pcts):
    return pd.DataFrame([{"quantity": f"standardized.std_s{s}", "real": 0.0,
                          "real_percentile": p, "n_nulls": 100}
                         for s, p in pcts.items()])


def test_verdict_needs_both_gates():
    from study_h4_kill import verdict
    # slot 0 cao hơn cả bốn slot đối chứng VÀ vượt percentile 95 -> mở cổng
    real = {f"standardized.std_s{s}": v for s, v in
            {0: 0.70, 1: 0.40, 2: 0.42, 3: 0.41, 4: 0.39, 5: 0.38}.items()}
    ok, text = verdict(real, _stats_frame({0: 99.0, 5: 10.0}))
    assert ok and "slot 0" in text and "DUOC phep" in text

    # cao hơn nhưng percentile thấp -> cổng (b) chặn
    ok, text = verdict(real, _stats_frame({0: 50.0, 5: 10.0}))
    assert not ok and "KHONG duoc phep" in text

    # percentile cao nhưng KHÔNG cao hơn slot đối chứng -> cổng (a) chặn
    real2 = dict(real, **{"standardized.std_s0": 0.30})
    ok, text = verdict(real2, _stats_frame({0: 99.0, 5: 10.0}))
    assert not ok


def test_verdict_only_looks_at_slots_0_and_5():
    """Slot 2 vượt cả hai cổng cũng không mở gì: nghiên cứu hỏi về hai cây của
    người dùng, và cho slot khác mở cổng là đổi câu hỏi sau khi thấy số."""
    from study_h4_kill import verdict
    real = {f"standardized.std_s{s}": v for s, v in
            {0: 0.30, 1: 0.40, 2: 0.90, 3: 0.41, 4: 0.39, 5: 0.31}.items()}
    ok, _ = verdict(real, _stats_frame({0: 10.0, 2: 99.0, 5: 10.0}))
    assert not ok


def test_verdict_text_names_the_missing_third_gate():
    """Spec §5.3 và §10: Null B đã bị loại khỏi phạm vi, và điều đó phải xuất
    hiện trong phán quyết chứ không nhét vào cuối báo cáo."""
    from study_h4_kill import verdict
    real = {f"standardized.std_s{s}": 0.4 for s in range(6)}
    _, text = verdict(real, _stats_frame({0: 10.0, 5: 10.0}))
    assert "Null B" in text
```

- [ ] **Step 2: Chạy test để chắc nó fail**

Run: `python -m pytest tests/test_h4_kill.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'study_h4_kill'`

- [ ] **Step 3: Viết implementation tối thiểu**

Tạo `scripts/study_h4_kill.py`:

```python
"""Nến H4 (lưới neo 17:00 New York) có bị quét cả hai đầu nhiều hơn mức mà hình
học đã giải thích được?

Spec: docs/superpowers/specs/2026-09-09-h4-kill-both-ends-study-design.md

Usage:
  python scripts/study_h4_kill.py
  python scripts/study_h4_kill.py --tf M5 --shifts 200
  python scripts/study_h4_kill.py --source csv --csv data/FXCM_XAUUSD_m1.csv

Mã thoát: 0 nghiên cứu chạy xong; 1 cổng chặn timezone fail; 2 không đủ dữ liệu.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from rsi_fvg.bars import Bars  # noqa: E402
from rsi_fvg.data.csv_loader import load_csv  # noqa: E402
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.data.tz_detect import detect_source_tz  # noqa: E402
from rsi_fvg.h4_grid import DAY_SECONDS  # noqa: E402
from rsi_fvg.h4_kill import (STD_HORIZON_MIN, excursion_usd_by_year,  # noqa: E402
                             killed_range_usd_by_year, run_grid, run_null)
from rsi_fvg.quarter_stats import make_offsets, percentile_of  # noqa: E402

TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600}

# Hai slot mà người dùng hỏi, và bốn slot đối chứng.
TARGET_SLOTS = (0, 5)
CONTROL_SLOTS = (1, 2, 3, 4)
VERDICT_KEY = "standardized.std_s{s}"
VERDICT_PERCENTILE = 95.0

SLOT_NY = {0: "17:00-21:00 NY", 1: "21:00-01:00", 2: "01:00-05:00",
           3: "05:00-09:00", 4: "09:00-13:00", 5: "13:00-17:00 NY"}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbol", default="XAUUSDc")
    p.add_argument("--tf", default="M1", choices=sorted(TF_SECONDS))
    p.add_argument("--source", default="mt5", choices=("mt5", "csv"))
    p.add_argument("--csv", type=Path, default=None,
                   help="duong dan CSV khi --source csv (dialect FXCM duoc ho tro)")
    p.add_argument("--shifts", type=int, default=200,
                   help="so luoi null xin; M1 co gan 1440 moc, H1 chi co 23")
    p.add_argument("--seed", type=int, default=20260909)
    p.add_argument("--data-dir", type=Path, default=ROOT / "data")
    p.add_argument("--out-dir", type=Path, default=None)
    return p.parse_args(argv)


def load_bars(args) -> Bars:
    """Nghiên cứu này không dùng SymbolSpec — không sizing, không cost — nên bỏ
    nửa sau của load_or_fetch."""
    if args.source == "csv":
        if args.csv is None:
            raise SystemExit("--source csv can --csv <duong dan>")
        return Bars.from_dataframe(load_csv(args.csv))
    df, _spec = load_or_fetch(args.symbol, args.tf, args.data_dir)
    return Bars.from_dataframe(df)


def gate_timezone(bars: Bars, bar_seconds: int, source: str) -> str:
    """Cổng chặn §6.1. Fail thì thoát 1 và KHÔNG chạy nghiên cứu.

    Mọi biên slot là một mốc giờ treo tường New York, nên nếu cách đọc `time`
    sai thì nghiên cứu đo một lưới khác mà vẫn in ra số trông hợp lý. In cả bảng
    điểm chứ không chỉ người thắng — người đọc phải thấy được khoảng cách.
    """
    chk = detect_source_tz(bars.time, bar_seconds)
    print("--- cong chan timezone (spec 6.1) ---")
    print(f"  khe trong ngay tim duoc : {chk.n_gaps}")
    print(f"  ung vien tot nhat       : {chk.best!r}  score={chk.score:.4f}")
    print(f"  ung vien nhi            : {chk.runner_up!r}  score={chk.runner_up_score:.4f}")
    print("  bang diem (top 5)       : "
          + ", ".join(f"{lab}={sc:.4f}" for lab, sc in chk.table[:5]))
    for note in chk.notes:
        print(f"  ghi chu: {note}")
    if not chk.ok:
        print("\nFAIL: khong xac dinh duoc timezone cua nguon.")
        print("Moi bien slot la mot moc gio New York, nen doc sai mot gio la do")
        print("mot luoi khac. Khong chay tiep. Xem spec 6.1.")
        sys.exit(1)
    if source == "mt5" and chk.best != "UTC":
        print(f"\nFAIL: nguon mt5 phai doc duoc la UTC, do ra {chk.best!r}.")
        print("Bars.time la instant UTC that (rsi_fvg/quarters.py). Neu no doi")
        print("thi moi ket qua cu cung phai doc lai. Khong chay tiep.")
        sys.exit(1)
    print(f"  PASS ({chk.best})\n")
    return chk.best


def compare_to_null(real: dict, nulls: pd.DataFrame) -> pd.DataFrame:
    recs = []
    for key, value in real.items():
        col = (nulls[key].to_numpy(dtype="float64")
               if key in nulls.columns else np.array([]))
        finite = col[np.isfinite(col)]
        recs.append({
            "quantity": key, "real": value,
            "null_mean": float(finite.mean()) if finite.size else float("nan"),
            "null_p05": float(np.percentile(finite, 5)) if finite.size else float("nan"),
            "null_p50": float(np.percentile(finite, 50)) if finite.size else float("nan"),
            "null_p95": float(np.percentile(finite, 95)) if finite.size else float("nan"),
            "real_percentile": percentile_of(value, col),
            "n_nulls": int(finite.size),
        })
    return pd.DataFrame(recs)


def verdict(real: dict, stats: pd.DataFrame) -> tuple[bool, str]:
    """Luật §10, tính bằng máy — không để người đọc tự kết luận.

    HAI cổng, không phải ba: cổng Null B đã bị người dùng loại khỏi phạm vi
    (spec §5.3), và hệ quả của việc thiếu nó được in ngay trong phán quyết chứ
    không nhét vào cuối báo cáo.

    Chỉ xét slot 0 và slot 5. Một slot đối chứng vượt cả hai cổng cũng không mở
    gì: nghiên cứu hỏi về hai cây của người dùng, và để slot khác mở cổng là đổi
    câu hỏi sau khi đã thấy số.
    """
    pct = dict(zip(stats["quantity"], stats["real_percentile"]))
    control = [real.get(VERDICT_KEY.format(s=s), float("nan")) for s in CONTROL_SLOTS]
    best_control = float(np.nanmax(control)) if np.any(np.isfinite(control)) else float("nan")

    lines = ["## Phan quyet section 10", "",
             f"- nguong percentile: {VERDICT_PERCENTILE}  "
             f"- horizon chuan hoa: {STD_HORIZON_MIN} phut",
             f"- slot doi chung cao nhat (std): {best_control:.4f}", ""]
    passed = False
    for s in TARGET_SLOTS:
        key = VERDICT_KEY.format(s=s)
        std = float(real.get(key, float("nan")))
        p = float(pct.get(key, float("nan")))
        gate_a = bool(np.isfinite(std) and np.isfinite(best_control) and std > best_control)
        gate_b = bool(np.isfinite(p) and p > VERDICT_PERCENTILE)
        hit = gate_a and gate_b
        passed = passed or hit
        lines.append(
            f"- **slot {s}** ({SLOT_NY[s]}): std={std:.4f}, percentile={p:.1f} "
            f"-> cong (a) cao hon doi chung: {'DAT' if gate_a else 'khong'}; "
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
        "sau khi kiem soat do rong' — KHONG phai 'moc H4 phien A bi nham'. Cau sau "
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


def main(argv=None) -> int:
    args = parse_args(argv)
    bar_seconds = TF_SECONDS[args.tf]
    bars = load_bars(args)
    src = f"{args.csv}" if args.source == "csv" else f"{args.symbol} {args.tf} (mt5)"
    print(f"nguon: {src} — {len(bars)} bar")
    if len(bars) < 5000:
        print("FAIL: qua it bar de do bat cu thu gi.")
        return 2

    tz_label = gate_timezone(bars, bar_seconds, args.source)

    real, rows = run_grid(bars, bar_seconds)
    print(f"bang dong: {len(rows)} dong, {rows['day_num'].nunique()} ngay giao dich")
    if rows.empty:
        print("FAIL: khong con dong nao sau luat loai.")
        return 2

    offsets = make_offsets("", bar_seconds, args.shifts, args.seed,
                           cycle_seconds=DAY_SECONDS)
    if len(offsets) < args.shifts:
        print(f"chi co {len(offsets)} moc neo kha dung (xin {args.shifts}). "
              f"Chu ky {DAY_SECONDS} s / bar {bar_seconds} s gioi han so luoi null.")
    nulls = run_null(bars, bar_seconds, offsets)
    stats = compare_to_null(real, nulls)

    out_dir = args.out_dir or (ROOT / "results" / "h4_kill" / date.today().isoformat())
    out_dir.mkdir(parents=True, exist_ok=True)
    rows.to_csv(out_dir / "rows.csv", index=False)
    stats.to_csv(out_dir / "stats.csv", index=False)
    excursion_usd_by_year(rows).to_csv(out_dir / "excursion_usd_by_year.csv", index=False)
    killed_range_usd_by_year(rows).to_csv(out_dir / "killed_range_usd_by_year.csv", index=False)

    passed, verdict_md = verdict(real, stats)
    spread_note = ""
    if bars.spread is not None and np.any(bars.spread > 0):
        spread_note = (f"- spread trung vi: {float(np.median(bars.spread)):.0f} points. "
                       f"Gia la BID nen ti le kill dau TREN thuc te cao hon con so bao "
                       f"(stop mua khop o Ask) — thien lech mot phia, khong sua so.\n")

    head = [
        "# Nen H4 bi kill hai dau", "",
        f"- nguon: {src}   timezone do duoc: {tz_label}   bar: {len(bars)}",
        f"- dong: {len(rows)}   ngay giao dich: {rows['day_num'].nunique()}",
        f"- luoi null: {len(nulls)}   seed: {args.seed}",
        spread_note.rstrip("\n") if spread_note else "",
        "- spec: docs/superpowers/specs/2026-09-09-h4-kill-both-ends-study-design.md",
        "",
        "Hai canh bao phai doc truoc bang so:",
        "1. Hai cay duoc hoi (slot 0 va slot 5) la hai cay HEP NHAT trong sau, VA",
        "   theo dinh nghia cua so chung nhan hai cua so DAI NHAT (20h va 24h so",
        "   voi 4-16h). So sanh tho thien vi hai lan cung chieu. Dung dai luong",
        "   'standardized' de so giua cac slot, dung dung 'window'.",
        "2. Phan vi USD gop ca mau bi 2025-2026 chi phoi (range median cua vang",
        "   gap 13 lan tu 2017). Dung dang chia day_atr, hoac excursion_usd_by_year.csv.",
        "",
        "## Bang thong ke", "",
        "```", stats.to_string(index=False), "```", "",
    ]
    (out_dir / "summary.md").write_text("\n".join(head) + verdict_md + "\n",
                                        encoding="utf-8")
    print(verdict_md)
    print(f"\nket qua: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Chạy test để chắc nó pass**

Run: `python -m pytest tests/test_h4_kill.py -q` → PASS
Cả suite: `python -m pytest -q` → **380 passed**.

Rồi chạy thật trên M1 (đây là lần chạy tốn thời gian nhất — 200 lưới null × ~14.300 dòng; ước lượng vài phút tới vài chục phút):

```bash
python scripts/study_h4_kill.py --tf M1 --shifts 200
```

Xác nhận trước khi tin kết quả: cổng chặn in `PASS (UTC)` với `score≈0.8644` và `n_gaps=2290`; bảng dòng có ~14.300 dòng và ~2.385 ngày. **Nếu bất kỳ con số nào lệch xa, DỪNG và báo** thay vì diễn giải kết quả.

- [ ] **Step 5: Commit**

```bash
git add scripts/study_h4_kill.py tests/test_h4_kill.py
git commit -m "feat(scripts): study_h4_kill CLI - cong chan tz, null A, phan quyet hai cong"
```

Rồi commit kết quả riêng (results/ nằm trong .gitignore ở repo này — kiểm `git check-ignore -v results/` trước; nếu bị ignore thì **không** ép thêm vào, chỉ báo đường dẫn cho người dùng).

---

## Self-Review

**1. Spec coverage** — soi từng mục của spec, chỉ ra task nào làm:

| spec | task |
|---|---|
| §2.1 lưới neo 17:00 NY, sáu slot, DST | Task 1 |
| §2.2 số thật của lưới | Task 2 Step 4 (đo thật: **2303 ngày** sống sót cả ba luật loại — Ruling 5; 2385 là số ngày *có mặt* cả sáu slot, không phải cỡ mẫu) |
| §2.3a thiên lệch độ rộng | Task 5 (③) |
| §2.3b thiên lệch đơn vị USD | Task 6 (`*_by_year`) + Task 10 (cảnh báo trong `summary.md`) |
| §3.1 `label_h4` | Task 1 |
| §3.2 `aggregate_days`, ATR ngày | Task 2 |
| §3.3 ba luật loại | Task 2 |
| §4.1 bốn nguyên thuỷ | Task 3 |
| §4.2 hai định nghĩa cửa sổ | Task 3 (`w_from`/`w_to`, `h_avail`) |
| §4.3 ① ② | Task 4 |
| §4.3 ③ | Task 5 (`std_s{k}`, `deciles_used_s{k}`, `min_cell_n_s{k}`) + Task 10 (bảng slot × decile với `n` từng ô, in trong `summary.md`) — Ruling 9 |
| §4.3 ④ ⑤ ⑥ | Task 6 |
| §4.3 ⑦ | Task 4 |
| §4.4 ba dạng đơn vị | Task 6 (ATR trong stat, USD theo năm trong bảng báo cáo) |
| §5.1 Null A, offset trọn chu kỳ ngày | Task 7 |
| §5.2 confound đã biết | Task 10 (in trong phán quyết) |
| §5.3 Null B bị loại | Task 10 (`verdict` in ra, có test) |
| §6.1 cổng dò timezone | Task 8 |
| §6.2 dialect FXCM | Task 9 |
| §6.3 nguồn dữ liệu | Task 10 (`--source`, ghi nguồn vào `summary.md`) |
| §7 file | bảng File Structure, cộng deviation đã ghi |
| §8 mười điểm test | Task 1–9; §8 mục 6 là test quan trọng nhất (Task 5), §8 mục 9 là bất biến tiền tố (Task 3) |
| §9 cỡ mẫu | Task 2 và Task 10 in `n` thật |
| §10 luật kết luận | Task 10 `verdict` |
| §11 giới hạn | Task 10 (`summary.md`) |

Không có mục nào của spec thiếu task.

**2. Placeholder scan** — không có "TBD", "TODO", "tương tự Task N", hay bước nào chỉ mô tả mà không có code. Mọi step code đều có khối code thật.

**3. Type consistency** — tên và kiểu dùng ở task sau khớp task trước: `H4Labels.{ny, trading_day, slot, day_num, utc_offset}` (Task 1) được `aggregate_days` (Task 2) và `scan_kills` (Task 3) đọc đúng tên; `days` index là `day_num` và `scan_kills` tra bằng `days.at[d, f"s{s}_high"]`; cột bảng dòng khai ở Task 3 và mọi `stat_*` chỉ đọc từ danh sách đó; `build_stats` (Task 7) gọi đúng bảy hàm của Task 4–6; `verdict` (Task 10) đọc khoá `standardized.std_s{k}` mà `run_grid` sinh từ tên stat `"standardized"` + khoá `std_s{k}` của Task 5.

**4. Số test tích luỹ** — 304 (hiện có) → 323 → 332 → 344 → 351 → 355 → 360 → 367 → 373 → 376 → 380. Con số ở mỗi Step 4 là *ước lượng*; điều bắt buộc là **304 test cũ không được đổi** ở bất kỳ task nào. Nếu một test cũ đỏ, DỪNG và báo, đừng sửa test cũ cho vừa code mới.

---

## Execution Handoff

Plan xong và đã lưu ở `docs/superpowers/plans/2026-09-09-h4-kill-both-ends-study.md`. Hai cách chạy:

**1. Subagent-Driven (khuyến nghị)** — mỗi task một subagent mới, review giữa các task, vòng lặp nhanh.

**2. Inline Execution** — chạy tuần tự trong session này, checkpoint theo lô để review.

Chọn cách nào?
