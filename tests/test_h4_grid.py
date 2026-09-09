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
