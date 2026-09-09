import numpy as np
import pandas as pd
import pytest

from conftest import epoch_for_ny, make_bars
from rsi_fvg.quarter_stats import (MIN_BARS_PER_QUARTER, OFFSET_EXCLUDE, STATS,
                                   aggregate_cycles, make_offsets, percentile_of,
                                   run_grid, run_null, stat_displacement_by_index,
                                   stat_q1_predicts_q2, stat_range_by_index,
                                   stat_reclaim_q3, stat_sweep, stat_true_open)
from rsi_fvg.quarters import label_quarters


def _one_session_bars(n_per_quarter=(6, 6, 6, 6), start_hh=18):
    """Bar M5 cho một session 6h, số bar mỗi block 90m do caller đặt.

    Bar được đặt Ở ĐẦU mỗi block để số lượng là chính xác: block 90m chứa 18 bar
    M5, ta chỉ dùng n_per_quarter[i] bar đầu của block i.
    """
    base = epoch_for_ny(2026, 6, 1, start_hh)
    times, o, h, l, c = [], [], [], [], []
    for q, n in enumerate(n_per_quarter):
        q_start = base + q * 5400
        for i in range(n):
            times.append(q_start + i * 300)
            o.append(100.0 + q)
            h.append(110.0 + q)
            l.append(90.0 - q)
            c.append(105.0 + q)
    bars = make_bars(o, h, l, c)
    bars.time = np.array(times, dtype="int64")
    return bars


def test_aggregate_cycles_columns_use_theory_numbering():
    bars = _one_session_bars()
    w = aggregate_cycles(bars, label_quarters(bars.time, "q90"))
    assert len(w) == 1
    for q in (1, 2, 3, 4):
        for f in ("open", "high", "low", "close", "n"):
            assert f"q{q}_{f}" in w.columns
    assert "q0_open" not in w.columns


def test_aggregate_cycles_ohlc_is_first_max_min_last():
    bars = _one_session_bars(n_per_quarter=(6, 6, 6, 6))
    w = aggregate_cycles(bars, label_quarters(bars.time, "q90"))
    row = w.iloc[0]
    assert row["q1_open"] == 100.0 and row["q1_close"] == 105.0
    assert row["q1_high"] == 110.0 and row["q1_low"] == 90.0
    assert row["q4_open"] == 103.0 and row["q4_high"] == 113.0
    assert row["q1_n"] == 6


def test_aggregate_cycles_drops_cycle_when_one_quarter_too_thin():
    """Q3 chỉ có 2 bar (< MIN_BARS_PER_QUARTER = 3) => loại CẢ chu kỳ."""
    bars = _one_session_bars(n_per_quarter=(6, 6, 2, 6))
    w = aggregate_cycles(bars, label_quarters(bars.time, "q90"))
    assert len(w) == 0


def test_aggregate_cycles_drops_cycle_when_a_quarter_is_missing():
    """Không bar nào trong Q4 => loại cả chu kỳ, không để NaN lọt xuống thống kê."""
    bars = _one_session_bars(n_per_quarter=(6, 6, 6, 0))
    w = aggregate_cycles(bars, label_quarters(bars.time, "q90"))
    assert len(w) == 0


def test_aggregate_cycles_min_bars_is_a_parameter():
    bars = _one_session_bars(n_per_quarter=(6, 6, 2, 6))
    assert len(aggregate_cycles(bars, label_quarters(bars.time, "q90"), min_bars=2)) == 1
    assert MIN_BARS_PER_QUARTER == 3


def _wide(rows: list[dict]) -> pd.DataFrame:
    """Bảng chu kỳ dựng tay. Thiếu cột nào thì điền giá trị trung tính.

    Danh sách rỗng vẫn phải trả về DataFrame CÓ ĐỦ CỘT: aggregate_cycles luôn
    reindex về đủ cột nên bảng rỗng thật vẫn có cột, và pd.DataFrame([]) thì
    không — helper phải mô phỏng đúng thứ production sinh ra.
    """
    base = {}
    for q in (1, 2, 3, 4):
        base |= {f"q{q}_open": 100.0, f"q{q}_high": 101.0,
                 f"q{q}_low": 99.0, f"q{q}_close": 100.0, f"q{q}_n": 10.0}
    if not rows:
        return pd.DataFrame(columns=list(base)).astype("float64")
    return pd.DataFrame([base | r for r in rows])


def test_stat_sweep_counts_either_side():
    w = _wide([
        {"q1_high": 110, "q1_low": 90, "q2_high": 111, "q2_low": 95},   # sweep lên
        {"q1_high": 110, "q1_low": 90, "q2_high": 105, "q2_low": 89},   # sweep xuống
        {"q1_high": 110, "q1_low": 90, "q2_high": 105, "q2_low": 95},   # trong range
        {"q1_high": 110, "q1_low": 90, "q2_high": 111, "q2_low": 89},   # cả hai phía
    ])
    got = stat_sweep(w)
    assert got["sweep_rate"] == 0.75
    assert got["n"] == 4.0


def test_stat_sweep_boundary_touch_is_not_a_sweep():
    """Bằng đúng biên KHÔNG phải sweep — so sánh phải là > và <, không phải >= <=."""
    w = _wide([{"q1_high": 110, "q1_low": 90, "q2_high": 110, "q2_low": 90}])
    assert stat_sweep(w)["sweep_rate"] == 0.0


def test_stat_range_by_index_and_q1_ratio():
    w = _wide([{
        "q1_high": 102, "q1_low": 100,     # range 2
        "q2_high": 108, "q2_low": 100,     # range 8
        "q3_high": 104, "q3_low": 100,     # range 4
        "q4_high": 106, "q4_low": 100,     # range 6
    }])
    got = stat_range_by_index(w)
    assert got["range_q1"] == 2.0 and got["range_q2"] == 8.0
    assert got["range_q1_ratio"] == pytest.approx(2.0 / 5.0)   # mean(2,8,4,6) = 5


def test_stat_displacement_uses_absolute_value():
    w = _wide([
        {"q1_open": 100, "q1_close": 103, "q3_open": 100, "q3_close": 90},
        {"q1_open": 100, "q1_close": 97, "q3_open": 100, "q3_close": 110},
    ])
    got = stat_displacement_by_index(w)
    assert got["disp_q1"] == 3.0        # |+3| và |-3| đều là 3
    assert got["disp_q3"] == 10.0


def test_stats_on_empty_table_return_nan_not_crash():
    w = _wide([]).iloc[0:0]
    assert np.isnan(stat_sweep(w)["sweep_rate"])
    assert np.isnan(stat_range_by_index(w)["range_q1"])
    assert np.isnan(stat_displacement_by_index(w)["disp_q1"])


def test_spearman_is_minus_one_when_q1_range_perfectly_inverts_q2():
    """Lý thuyết dự đoán tương quan ÂM: Q1 hẹp thì Q2 giãn."""
    w = _wide([
        {"q1_high": 101, "q1_low": 100, "q2_high": 110, "q2_low": 100},
        {"q1_high": 102, "q1_low": 100, "q2_high": 108, "q2_low": 100},
        {"q1_high": 103, "q1_low": 100, "q2_high": 106, "q2_low": 100},
        {"q1_high": 104, "q1_low": 100, "q2_high": 104, "q2_low": 100},
    ])
    assert stat_q1_predicts_q2(w)["spearman_r1_r2"] == pytest.approx(-1.0)


def test_spearman_is_rank_based_not_value_based():
    """Spearman phải bất biến với phép biến đổi đơn điệu — đó là lý do dùng nó."""
    w = _wide([
        {"q1_high": 101, "q1_low": 100, "q2_high": 102, "q2_low": 100},
        {"q1_high": 102, "q1_low": 100, "q2_high": 140, "q2_low": 100},
        {"q1_high": 103, "q1_low": 100, "q2_high": 900, "q2_low": 100},
    ])
    assert stat_q1_predicts_q2(w)["spearman_r1_r2"] == pytest.approx(1.0)


def test_true_open_persistence_counts_same_side():
    """TO = open bar đầu Q2. Đo P(cuối Q4 cùng phía TO với đầu Q3)."""
    w = _wide([
        {"q2_open": 100, "q3_open": 105, "q4_close": 110},   # trên, trên -> cùng
        {"q2_open": 100, "q3_open": 95, "q4_close": 90},     # dưới, dưới -> cùng
        {"q2_open": 100, "q3_open": 105, "q4_close": 90},    # trên, dưới -> khác
    ])
    got = stat_true_open(w)
    assert got["true_open_persistence"] == pytest.approx(2.0 / 3.0)
    assert got["n"] == 3.0 and got["ties"] == 0.0


def test_true_open_drops_ties_instead_of_assigning_a_side():
    """Giá bằng đúng TO bị LOẠI, không gán về một phía (spec §4.2)."""
    w = _wide([
        {"q2_open": 100, "q3_open": 100, "q4_close": 110},   # hoà ở đầu Q3
        {"q2_open": 100, "q3_open": 105, "q4_close": 100},   # hoà ở cuối Q4
        {"q2_open": 100, "q3_open": 105, "q4_close": 110},   # cùng phía
    ])
    got = stat_true_open(w)
    assert got["n"] == 1.0 and got["ties"] == 2.0
    assert got["true_open_persistence"] == 1.0


def test_true_open_all_ties_returns_nan():
    w = _wide([{"q2_open": 100, "q3_open": 100, "q4_close": 100}])
    got = stat_true_open(w)
    assert got["n"] == 0.0 and np.isnan(got["true_open_persistence"])


_RANGE = {"q1_high": 110.0, "q1_low": 90.0}


def test_reclaim_up_requires_sweep_and_close_back_inside():
    """Sweep lên: q2_high > q1_high VÀ q2_close < q1_high. Đo P(Q3 giảm)."""
    w = _wide([
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 105,
                  "q3_open": 105, "q3_close": 100},          # reclaim, Q3 giảm
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 105,
                  "q3_open": 105, "q3_close": 108},          # reclaim, Q3 tăng
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 112,
                  "q3_open": 112, "q3_close": 100},          # KHÔNG reclaim, loại
    ])
    got = stat_reclaim_q3(w)
    assert got["n_up"] == 2.0
    assert got["reclaim_up_p_q3_down"] == 0.5


def test_reclaim_down_is_mirrored():
    w = _wide([
        _RANGE | {"q2_high": 105, "q2_low": 85, "q2_close": 95,
                  "q3_open": 95, "q3_close": 100},           # reclaim, Q3 tăng
        _RANGE | {"q2_high": 105, "q2_low": 85, "q2_close": 95,
                  "q3_open": 95, "q3_close": 92},            # reclaim, Q3 giảm
    ])
    got = stat_reclaim_q3(w)
    assert got["n_dn"] == 2.0
    assert got["reclaim_dn_p_q3_up"] == 0.5


def test_reclaim_pooled_normalises_direction():
    """Pooled đo P(Q3 đi NGƯỢC hướng sweep), gộp cả hai phía."""
    w = _wide([
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 105,
                  "q3_open": 105, "q3_close": 100},          # sweep lên, Q3 giảm -> ngược
        _RANGE | {"q2_high": 105, "q2_low": 85, "q2_close": 95,
                  "q3_open": 95, "q3_close": 100},           # sweep xuống, Q3 tăng -> ngược
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 105,
                  "q3_open": 105, "q3_close": 108},          # sweep lên, Q3 tăng -> theo
    ])
    got = stat_reclaim_q3(w)
    assert got["n_pooled"] == 3.0
    assert got["reclaim_pooled_against"] == pytest.approx(2.0 / 3.0)


def test_reclaim_excludes_cycles_that_swept_both_sides():
    """Sweep cả hai phía: lý thuyết không có kỳ vọng hướng nào => loại khỏi cả ba.

    Đưa vào pooled sẽ đếm một chu kỳ hai lần với hai kỳ vọng trái nhau.
    """
    w = _wide([
        _RANGE | {"q2_high": 115, "q2_low": 85, "q2_close": 100,
                  "q3_open": 100, "q3_close": 95},           # cả hai phía
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 105,
                  "q3_open": 105, "q3_close": 100},          # chỉ lên
    ])
    got = stat_reclaim_q3(w)
    assert got["n_both_sides"] == 1.0
    assert got["n_up"] == 1.0 and got["n_dn"] == 0.0
    assert got["n_pooled"] == 1.0


def test_reclaim_drops_ties_at_the_boundary_and_in_q3():
    """q2_close bằng đúng biên là hoà; Q3 không đổi giá cũng là hoà. Cả hai bị loại."""
    w = _wide([
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 110,
                  "q3_open": 105, "q3_close": 100},          # close == q1_high -> hoà
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 105,
                  "q3_open": 105, "q3_close": 105},          # Q3 phẳng -> hoà
    ])
    got = stat_reclaim_q3(w)
    assert got["n_up"] == 0.0 and got["n_pooled"] == 0.0
    assert np.isnan(got["reclaim_pooled_against"])


def test_reclaim_on_empty_table_returns_nan():
    got = stat_reclaim_q3(_wide([]).iloc[0:0])
    assert np.isnan(got["reclaim_pooled_against"])
    assert got["n_pooled"] == 0.0


def test_offsets_are_snapped_to_bar_interval():
    """Snap là BẮT BUỘC: lưới thật có biên trùng bar, lưới giả rơi giữa nến sẽ bị
    handicap hình học và lưới thật trông tốt hơn chỉ vì căn lề (spec §4.1)."""
    off = make_offsets("session", bar_seconds=300, shifts=50, seed=1)
    assert np.all(off % 300 == 0)


def test_offsets_exclude_neighbourhood_of_zero():
    off = make_offsets("session", bar_seconds=300, shifts=50, seed=1)
    cycle = 4 * 21600
    assert off.min() >= OFFSET_EXCLUDE
    assert off.max() <= cycle - OFFSET_EXCLUDE


def test_offsets_are_unique_and_deterministic_by_seed():
    a = make_offsets("session", 300, 50, seed=7)
    b = make_offsets("session", 300, 50, seed=7)
    c = make_offsets("session", 300, 50, seed=8)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    assert len(set(a.tolist())) == len(a)


def test_q90_tier_caps_at_69_offsets_not_200():
    """Trần thật của tầng q90: chu kỳ 21600 s / bar 300 s = 72 mốc, trừ lân cận 0
    còn 69. Yêu cầu 200 sẽ chỉ nhận được 69 — phải báo ra, không im lặng."""
    off = make_offsets("q90", bar_seconds=300, shifts=200, seed=1)
    assert len(off) == 69
    off_sess = make_offsets("session", bar_seconds=300, shifts=200, seed=1)
    assert len(off_sess) == 200


def test_run_grid_returns_namespaced_keys_for_all_six_stats():
    bars = _one_session_bars()
    got = run_grid(bars, "q90")
    assert set(STATS) == {"sweep", "range_by_index", "displacement_by_index",
                          "q1_predicts_q2", "true_open", "reclaim_q3"}
    assert "sweep.sweep_rate" in got
    assert "reclaim_q3.reclaim_pooled_against" in got
    assert all("." in k for k in got)


def test_percentile_of_counts_nulls_below_real():
    null = np.array([0.1, 0.2, 0.3, 0.4])
    assert percentile_of(0.35, null) == 75.0
    assert percentile_of(0.05, null) == 0.0
    assert percentile_of(0.5, null) == 100.0


def test_percentile_of_ignores_nan_nulls_and_nan_real():
    null = np.array([0.1, np.nan, 0.3])
    assert percentile_of(0.2, null) == 50.0
    assert np.isnan(percentile_of(np.nan, null))
    assert np.isnan(percentile_of(0.2, np.array([np.nan, np.nan])))


def test_run_null_has_one_row_per_offset():
    bars = _one_session_bars()
    offsets = np.array([1800, 3600], dtype="int64")
    out = run_null(bars, "q90", offsets)
    assert len(out) == 2
    assert list(out["anchor_offset"]) == [1800, 3600]
