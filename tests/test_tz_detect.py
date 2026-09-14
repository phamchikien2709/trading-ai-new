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
