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


# Task 2: aggregate_days tests

from rsi_fvg.bars import Bars
from rsi_fvg.h4_grid import (
    MIN_BAR_FRACTION, ATR_PERIOD, expected_bars, aggregate_days
)
from rsi_fvg.indicators import atr_wilder


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
            wick = 500.0 if i in wide_days else 1.0
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
    assert days["day_atr"].max() < 100.0


def test_day_atr_nan_during_warmup():
    days = _days(h1_days("2026-01-05", 20))
    assert days["day_atr"].iloc[:13].isna().all()
    assert days["day_atr"].iloc[13:].notna().all()
