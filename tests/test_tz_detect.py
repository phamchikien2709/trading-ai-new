import numpy as np
import pandas as pd
import pytest

from conftest import epoch_for_ny
from rsi_fvg.data import tz_detect
from rsi_fvg.data.tz_detect import MIN_SCORE, detect_source_tz, to_ny

# Một ngày giao dịch H1: khe nghỉ 17:00-18:00 NY bị bỏ, đúng như dữ liệu thật.
NY_HOURS = (18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4,
            5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)

# Giống NY_HOURS nhưng phiên đóng lúc 14:00 NY thay vì 16:00. Nửa AFTER của
# công thức score vẫn đúng (bar đầu sau khe ở giờ 18), nửa BEFORE thì trượt.
NY_HOURS_EARLY_CLOSE = (18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4,
                        5, 6, 7, 8, 9, 10, 11, 12, 13, 14)


def _session_epochs(day, hours):
    """Một phiên: `hours` >= 17 thuộc chiều `day`, còn lại thuộc sáng hôm sau."""
    out = []
    for hh in hours:
        d = day + pd.Timedelta(days=0 if hh >= 17 else 1)
        out.append(epoch_for_ny(d.year, d.month, d.day, hh))
    return out


def daily_break_series(n_days=60, start="2026-01-05", hours=NY_HOURS):
    d0 = pd.Timestamp(start)
    out = []
    for i in range(n_days):
        out += _session_epochs(d0 + pd.Timedelta(days=i), hours)
    return np.asarray(sorted(out), dtype="int64")


def weekend_break_series(n_weeks=12, start="2026-01-04", hole_at=None):
    """Chuỗi có khe CUỐI TUẦN thật (bỏ Thứ Bảy + Chủ Nhật), tuỳ chọn thêm một
    lỗ 3 ngày giữa tuần — đúng hình dạng của một CSV export thiếu vài phiên.

    Trả về `(time, dates)`; `dates` là danh sách ngày-chiều-mở-phiên để test tự
    đếm số cặp ngày liền kề mà không phải dựng lại logic của cổng.
    """
    d0 = pd.Timestamp(start)
    dates = [d0 + pd.Timedelta(days=i) for i in range(n_weeks * 7)]
    dates = [d for d in dates if d.weekday() in (6, 0, 1, 2, 3)]  # CN..T5
    if hole_at is not None:
        dates = dates[:hole_at] + dates[hole_at + 3:]
    out = []
    for day in dates:
        out += _session_epochs(day, NY_HOURS)
    return np.asarray(sorted(out), dtype="int64"), dates


def stamp_wall_clock(t, zone):
    """epoch thật -> "epoch" đọc từ giờ TREO TƯỜNG của `zone`.

    Đây là thứ một CSV export sinh ra: nhãn thời gian là giờ hiển thị của
    platform, không phải instant UTC.
    """
    wall = pd.to_datetime(t, unit="s", utc=True).tz_convert(zone).tz_localize(None)
    return np.asarray(wall.view("int64") // 10**9, dtype="int64")


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
    # NỘI DUNG của note, không chỉ sự tồn tại: Task 10 in thẳng chuỗi này ra
    # summary.md, nên nó phải mang cả điểm đo được lẫn ngưỡng đã trượt.
    msg = [n for n in got.notes if "nguong" in n]
    assert msg, got.notes
    assert f"{got.score:.4f}" in msg[0], msg[0]
    assert str(MIN_SCORE) in msg[0], msg[0]


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
    # Hai BIÊN của dải ứng viên, không phải một nhãn ở giữa: spec §6.1 nói −12
    # đến +14, và cắt cụt dải làm cổng chặn nhầm một nguồn đọc được hoàn toàn.
    assert "+14:00" in labels and "-12:00" in labels
    assert got.best == labels[0] and got.runner_up == labels[1]
    # Task 10 in thẳng runner_up_score; nếu nó không khớp bảng thì summary.md
    # nói dối trong khi `ok` vẫn đúng và không ai thấy.
    assert got.runner_up_score == got.table[1][1]
    assert got.score == got.table[0][1]


def test_detects_broker_stamped_at_plus_eight():
    """Broker MT4/MT5 đặt GMT+8 là chuyện thường. Nếu dải ứng viên bị cắt cụt
    thì cổng chọn bừa một offset xa lắc và báo lỗi SAI HƯỚNG — người dùng đi
    sửa dữ liệu trong khi thứ hỏng là danh sách ứng viên."""
    got = detect_source_tz(daily_break_series() + 8 * 3600, 3600)
    assert got.ok and got.best == "+08:00" and got.score > 0.99


def test_daily_gap_cap_excludes_weekend_and_multi_day_holes():
    """`d <= DAILY_GAP_MAX` là thứ giữ cổng sống trên dữ liệu thủng.

    Bỏ chặn trên thì khe cuối tuần (50h) và lỗ 3 ngày (74h) lọt vào phép đếm
    "khe nghỉ hằng ngày" — phép đo không còn là cái nó tự nhận là đo.
    """
    t, dates = weekend_break_series(n_weeks=12, hole_at=11)
    n_daily = sum(1 for a, b in zip(dates, dates[1:]) if (b - a).days == 1)
    n_long = len(dates) - 1 - n_daily
    assert n_daily == 44 and n_long == 12   # 11 khe cuối tuần + 1 lỗ 3 ngày

    got = detect_source_tz(t, 3600)
    assert got.n_gaps == n_daily
    assert got.ok and got.best == "UTC" and got.score > 0.99


def test_score_is_half_before_half_after():
    """Spec §6.1 định nghĩa score hai vế 0,5/0,5. Chuỗi này đóng phiên lúc
    14:00 NY: nửa AFTER đúng hoàn toàn, nửa BEFORE trượt hoàn toàn."""
    got = detect_source_tz(daily_break_series(hours=NY_HOURS_EARLY_CLOSE), 3600)
    by_label = dict(got.table)
    assert by_label["UTC"] == pytest.approx(0.5)
    # -02:00 là ảnh gương: BEFORE đúng, AFTER trượt. Không vế nào được nuốt vế
    # kia, nên KHÔNG ứng viên nào chạm 1,0.
    assert by_label["-02:00"] == pytest.approx(0.5)
    assert got.score == pytest.approx(0.5)


def test_named_zone_win_says_why_it_won():
    """Spec §6.1: "zone có tên sẽ thắng; cổng in ra rằng nó thắng và thắng vì
    lý do gì." Vế lý do phải sinh ra ở ca PASS, chứ không chỉ ca FAIL."""
    # Phải dùng chuỗi có cuối tuần: mọi mốc DST (NY lẫn Athens) rơi vào Chủ
    # nhật, và chuỗi này không có bar Chủ nhật nên không có giờ nhập nhằng /
    # không tồn tại. 60 tuần bắc qua cả hai biên DST của Athens.
    t = stamp_wall_clock(weekend_break_series(n_weeks=60)[0], "Europe/Athens")
    got = detect_source_tz(t, 3600)
    assert got.ok and got.best == "Europe/Athens"

    why = [n for n in got.notes if n.startswith("nguon co DST:")]
    assert why, got.notes
    assert "'+02:00'" in why[0] and "'+03:00'" in why[0], why[0]
    assert "'Europe/Athens'" in why[0], why[0]
    assert f"{got.score:.4f}" in why[0], why[0]
    # Hai mảnh vỡ phải được nêu ĐÍCH DANH kèm điểm, nếu không thì câu giải
    # thích chỉ là lời khẳng định suông.
    by_label = dict(got.table)
    assert f"{by_label['+02:00']:.4f}" in why[0], why[0]
    assert f"{by_label['+03:00']:.4f}" in why[0], why[0]


def test_zone_missing_from_tzdata_is_skipped_not_fatal():
    """Máy thiếu `tzdata` là ca thật. Zone không load được phải bị bỏ qua, chứ
    cổng không được nổ — nổ thì cả nghiên cứu dừng vì một gói hệ điều hành."""
    real = tz_detect.CANDIDATE_ZONES
    tz_detect.CANDIDATE_ZONES = ("Khong/CoThat",)
    try:
        got = detect_source_tz(daily_break_series(), 3600)
    finally:
        tz_detect.CANDIDATE_ZONES = real
    assert got.ok and got.best == "UTC" and got.score > 0.99
    assert "Khong/CoThat" not in [lab for lab, _ in got.table]
