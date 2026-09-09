import numpy as np
import pandas as pd
import pytest

from conftest import epoch_for_ny
from rsi_fvg.quarters import NY_TZ, label_quarters, server_to_ny, verify_server_tz


def _offset_hours(epoch: int, ny_wall: str) -> float:
    """Số giờ giữa giờ treo tường server (chính là epoch đọc như UTC) và giờ NY."""
    server_wall = pd.to_datetime(epoch, unit="s")
    return (server_wall - pd.Timestamp(ny_wall)).total_seconds() / 3600.0


@pytest.mark.parametrize("date_str,hh,want_offset", [
    ("2026-01-15", 12, 7.0),    # giữa đông, cả hai vùng đều ngoài DST
    ("2026-07-01", 12, 7.0),    # giữa hè, cả hai vùng đều trong DST
    ("2026-03-10", 12, 6.0),    # Mỹ vào DST 08/03, EU phải chờ 29/03
    ("2026-10-28", 12, 6.0),    # EU ra DST 25/10, Mỹ phải chờ 01/11
])
def test_server_to_ny_offset_only_ever_6_or_7(date_str, hh, want_offset):
    y, m, d = (int(x) for x in date_str.split("-"))
    e = epoch_for_ny(y, m, d, hh)
    assert _offset_hours(e, f"{date_str} {hh:02d}:00:00") == want_offset
    got = server_to_ny(np.array([e], dtype="int64"))[0]
    assert got == pd.Timestamp(f"{date_str} {hh:02d}:00:00", tz=NY_TZ)


def test_server_to_ny_never_yields_offset_8():
    """Offset 8 đòi Athens giờ hè trong khi NY giờ đông — bất khả, xem spec §2."""
    days = pd.date_range("2026-01-01", "2026-12-31", freq="D")
    offs = set()
    for ts in days:
        e = epoch_for_ny(ts.year, ts.month, ts.day, 12)
        offs.add(_offset_hours(e, f"{ts.date()} 12:00:00"))
    assert offs == {6.0, 7.0}


def test_server_to_ny_is_tz_aware_new_york():
    e = epoch_for_ny(2026, 6, 1, 18)
    out = server_to_ny(np.array([e], dtype="int64"))
    assert str(out.tz) == NY_TZ
    assert out[0].hour == 18


def _synth_weeks(open_hour_ny: int = 18, n_weeks: int = 3) -> np.ndarray:
    """Epoch M5: mỗi tuần mở Chủ nhật open_hour_ny NY, 5 phiên 23 giờ, nghỉ 1 giờ.

    Phiên chạy 18:00 -> 17:00 hôm sau, nên khe nghỉ hằng ngày kết thúc 18:00 NY.
    Khe từ 17:00 thứ Sáu tới 18:00 Chủ nhật là 49 giờ -> khe cuối tuần.
    """
    times: list[int] = []
    for w in range(n_weeks):
        sunday = 7 + 7 * w                       # 07, 14, 21/06/2026 đều là Chủ nhật
        base = epoch_for_ny(2026, 6, sunday, open_hour_ny)
        times.extend(range(base, base + 23 * 3600, 300))
        for k in range(1, 5):                    # T2 -> T5
            b = epoch_for_ny(2026, 6, sunday + k, 18)
            times.extend(range(b, b + 23 * 3600, 300))
    return np.array(sorted(set(times)), dtype="int64")


def _synth_weeks_no_daily_break(n_weeks: int = 3) -> np.ndarray:
    """Như trên nhưng mỗi tuần là MỘT khối liền: có khe cuối tuần, không khe trong ngày."""
    times: list[int] = []
    for w in range(n_weeks):
        base = epoch_for_ny(2026, 6, 7 + 7 * w, 18)
        times.extend(range(base, base + 5 * 24 * 3600 - 3600, 300))   # CN 18:00 -> T6 17:00
    return np.array(sorted(set(times)), dtype="int64")


def test_verify_server_tz_passes_on_correct_grid():
    chk = verify_server_tz(_synth_weeks(open_hour_ny=18), bar_seconds=300)
    assert chk.weekly_open_mode == "Sun 18:00"
    assert chk.daily_gap_end_mode == "18:00"
    assert chk.weekly_ok and chk.daily_ok and chk.ok


def test_verify_server_tz_fails_when_grid_is_off_by_an_hour():
    """Cùng dữ liệu dịch 1 giờ: mở Chủ nhật 19:00 là ngoài cửa sổ hợp lệ."""
    chk = verify_server_tz(_synth_weeks(open_hour_ny=18) + 3600, bar_seconds=300)
    assert chk.weekly_open_mode == "Sun 19:00"
    assert not chk.weekly_ok
    assert not chk.ok


def test_verify_server_tz_daily_ok_when_no_daily_gaps():
    """Có khe cuối tuần nhưng không khe trong ngày: kiểm định 2 pass RỖNG.

    Không được chặn oan — tài khoản có thể không có phiên nghỉ, và kiểm định 2
    chỉ mang tính xác nhận.
    """
    chk = verify_server_tz(_synth_weeks_no_daily_break(), bar_seconds=300)
    assert chk.daily_gap_end_mode == ""
    assert chk.daily_ok and chk.weekly_ok and chk.ok


def test_verify_server_tz_reports_no_gaps():
    base = epoch_for_ny(2026, 6, 7, 18)
    t = np.arange(base, base + 3600, 300, dtype="int64")
    chk = verify_server_tz(t, bar_seconds=300)
    assert not chk.ok
    assert any("khe" in n for n in chk.notes)


@pytest.mark.parametrize("hh,mm,want_sess,want_q90", [
    (18, 0, 0, 0), (19, 30, 0, 1), (21, 0, 0, 2), (23, 59, 0, 3),
    (0, 0, 1, 0), (1, 30, 1, 1),
    (6, 0, 2, 0), (7, 30, 2, 1),
    (12, 0, 3, 0), (13, 30, 3, 1), (17, 59, 3, 3),
])
def test_label_quarters_boundary_table(hh, mm, want_sess, want_q90):
    """Bảng này đã được kiểm tay khi làm indicator Pine — spec indicator §8."""
    e = epoch_for_ny(2026, 6, 1, hh, mm)
    t = np.array([e], dtype="int64")
    assert label_quarters(t, "session").q_index[0] == want_sess
    assert label_quarters(t, "q90").q_index[0] == want_q90


def test_trading_day_spans_midnight():
    """23:00 ngày D và 01:00 ngày D+1 thuộc CÙNG chu kỳ ngày (bắt đầu 18:00 D).

    Chỗ dễ cài sai nhất: kiểm cả trading_day bằng nhau VÀ q_index khác nhau —
    chỉ kiểm một trong hai sẽ không bắt được lỗi lệch ngày.
    """
    a = epoch_for_ny(2026, 6, 1, 23)
    b = epoch_for_ny(2026, 6, 2, 1)
    lab = label_quarters(np.array([a, b], dtype="int64"), "session")
    assert lab.trading_day[0] == lab.trading_day[1] == pd.Timestamp("2026-06-01")
    assert lab.q_index[0] == 0 and lab.q_index[1] == 1


def test_trading_day_rolls_at_18():
    """17:59 và 18:01 cùng ngày dương lịch nhưng thuộc HAI chu kỳ khác nhau."""
    a = epoch_for_ny(2026, 6, 1, 17, 59)
    b = epoch_for_ny(2026, 6, 1, 18, 1)
    lab = label_quarters(np.array([a, b], dtype="int64"), "session")
    assert lab.trading_day[0] == pd.Timestamp("2026-05-31")
    assert lab.trading_day[1] == pd.Timestamp("2026-06-01")
    assert lab.cycle_id[1] == lab.cycle_id[0] + 1


def test_cycle_id_q90_is_finer_than_session():
    """Tầng q90: mỗi session 6h là một chu kỳ, nên 4 chu kỳ mỗi ngày."""
    base = epoch_for_ny(2026, 6, 1, 18)
    t = np.array([base + h * 3600 for h in (0, 6, 12, 18)], dtype="int64")
    lab_s = label_quarters(t, "session")
    lab_q = label_quarters(t, "q90")
    assert len(set(lab_s.cycle_id)) == 1          # cùng một ngày giao dịch
    assert len(set(lab_q.cycle_id)) == 4          # bốn session khác nhau
    assert list(lab_q.q_index) == [0, 0, 0, 0]    # đều là block đầu của session


def test_anchor_offset_shifts_grid_by_exactly_one_quarter():
    """Dịch neo đúng 5400 s phải làm nhãn q90 lùi đúng một bậc."""
    base = epoch_for_ny(2026, 6, 1, 18)
    t = np.arange(base, base + 6 * 3600, 300, dtype="int64")
    a = label_quarters(t, "q90", anchor_offset=0).q_index
    b = label_quarters(t, "q90", anchor_offset=5400).q_index
    assert list(b) == list((a - 1) % 4)


def test_label_quarters_rejects_unknown_tier():
    t = np.array([epoch_for_ny(2026, 6, 1, 18)], dtype="int64")
    with pytest.raises(ValueError, match="tier"):
        label_quarters(t, "micro")


def test_label_quarters_correct_inside_dst_mismatch_window():
    """10/03/2026 nằm trong cửa sổ offset 6 giờ. Nhãn vẫn phải theo giờ NY."""
    e = epoch_for_ny(2026, 3, 10, 19, 30)
    lab = label_quarters(np.array([e], dtype="int64"), "q90")
    assert lab.q_index[0] == 1
    assert lab.ny[0].hour == 19 and lab.ny[0].minute == 30
