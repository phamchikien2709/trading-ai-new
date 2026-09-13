import numpy as np
import pandas as pd

from conftest import epoch_for_ny
from rsi_fvg.bars import Bars
from rsi_fvg.h4_grid import N_SLOTS, aggregate_days, label_h4
from rsi_fvg.h4_kill import (COLUMNS, DTYPES, scan_kills, stat_context,
                             stat_kill_rate_horizon, stat_kill_rate_window)

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


def test_empty_result_keeps_full_column_set():
    """Ruling của controller: khi không ngày nào sống sót, `scan_kills` vẫn
    phải trả về đủ bộ cột đã khai báo, ĐÚNG DTYPE — nếu không, mọi hàm đo của
    Task 4/6 (dạng `rows[rows["slot"] == s]` rồi `np.isfinite(...)`, hoặc lọc
    `rows[~rows["crosses_weekend"]]`) sẽ vỡ trên frame rỗng: cột `object` khiến
    `np.isfinite` ném `TypeError`, và lọc boolean trên cột `object` lặng lẽ trả
    về frame KHÔNG CỘT NÀO thay vì 0 dòng đủ cột — đúng chỗ KeyError mà COLUMNS
    được lập ra để chặn. Task 7 chạy 200 lưới null dịch offset và một offset
    bệnh lý có thể xoá hết ngày, nên trường hợp rỗng này không phải giả thuyết
    suông."""
    times = [epoch_for_ny(2026, 1, 5, 18), epoch_for_ny(2026, 1, 5, 19)]
    bars = Bars(time=np.asarray(times, dtype="int64"),
                open=np.full(2, 2000.0), high=np.full(2, 2000.5),
                low=np.full(2, 1999.5), close=np.full(2, 2000.0))
    lab = label_h4(bars.time)
    days = aggregate_days(bars, lab, 3600, atr_period=2)
    assert len(days) == 0, "setup phai tao ra 0 ngay song sot"

    empty = scan_kills(bars, lab, days, 3600)
    assert len(empty) == 0
    assert list(empty.columns) == list(COLUMNS)
    assert empty.dtypes.astype(str).to_dict() == DTYPES

    # Các pattern tiêu thụ thật sự mà Task 4-7 dùng, chạy trực tiếp trên frame
    # rỗng (không lọc slot trước) -- đây chính là hai lỗi reviewer chỉ ra.
    finite = np.isfinite(empty["rel_range"])          # object -> TypeError truoc fix
    assert len(finite) == 0
    filtered = empty[~empty["crosses_weekend"]]        # object -> mat het cot truoc fix
    assert list(filtered.columns) == list(COLUMNS)
    assert len(filtered) == 0
    assert empty["k_up"].to_numpy(dtype=bool).shape == (0,)
    assert empty["t_up"].to_numpy(dtype="float64").shape == (0,)
    assert pd.isna(empty["w_hours"].median())
    qcut = pd.qcut(empty["rel_range"], 2, labels=False, duplicates="drop")
    assert len(qcut) == 0

    full = rows_for(build([("2026-01-05", CALM), ("2026-01-06", CALM),
                            ("2026-01-07", CALM), ("2026-01-08", CALM)]))
    assert len(full) > 0, "setup phai tao ra it nhat 1 dong song sot"
    assert list(full.columns) == list(COLUMNS)
    assert full.dtypes.astype(str).to_dict() == DTYPES


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
    trả lời horizon đó bị loại KHỎI horizon đó, không tính là 'không kill'.

    h_avail của hai dòng đầu là 150 (không phải 100): gate của
    `stat_kill_rate_horizon` là `h_avail >= hb` một cách VÔ ĐIỀU KIỆN — không
    có ngoại lệ dù t_up/t_dn đã biết sớm hơn. Dòng thứ ba (h_avail=2) chứng
    minh điều đó: t_up=t_dn=1.0 (kill xảy ra ở bar 1, nằm gọn trong 2 bar sẵn
    có), vậy nếu gate có ngoại lệ "đã biết thì khỏi cần đủ h_avail" thì dòng
    này phải được tính ở CẢ HAI horizon (n_s0_h4 và n_s0_h120 đều thành 3) —
    nhưng test đòi n=2 ở cả hai, tức dòng này bị loại vô điều kiện. Cùng một
    gate đó, ở horizon 120 (hb=120), sẽ loại luôn hai dòng đầu nếu h_avail của
    chúng là 100 (100 < 120) — mâu thuẫn với việc test muốn chúng được tính.
    Nâng h_avail của hai dòng đầu lên 150 (>=120) là cách duy nhất giữ được
    một gate DUY NHẤT, không ngoại lệ, khớp với cả ba dòng.
    """
    rows = mk_rows([
        {"slot": 0, "t_up": 2.0, "t_dn": 3.0, "h_avail": 150},   # kill trong 4 bar
        {"slot": 0, "t_up": 2.0, "t_dn": 90.0, "h_avail": 150},  # chỉ kill ở horizon dài
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
