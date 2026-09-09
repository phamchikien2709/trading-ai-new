import numpy as np
import pandas as pd
import pytest

from conftest import epoch_for_ny
from rsi_fvg.quarters import NY_TZ, server_to_ny, verify_server_tz


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
