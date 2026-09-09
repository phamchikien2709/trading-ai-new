import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conftest import epoch_for_ny, make_bars
from rsi_fvg.quarter_stats import make_offsets
from rsi_fvg.quarter_variants import (DIRECT_VARIANT, PRIMARY_TIER, SCREEN_VARIANTS,
                                      TRAILING_WINDOW, VARIANTS, base_trigger, confirm,
                                      pick_winner, pooled, q3_dir, screen, split_halves,
                                      trailing_tight, variant_v1, variant_v2, variant_v3,
                                      variant_v4, variant_v5, verdict)

ROOT = Path(__file__).resolve().parents[1]

_RANGE = {"q1_high": 110.0, "q1_low": 90.0}
_SWEEP_UP = _RANGE | {"q2_high": 115.0, "q2_low": 95.0, "q2_close": 105.0}
_SWEEP_DN = _RANGE | {"q2_high": 105.0, "q2_low": 85.0, "q2_close": 95.0}


def _wide(rows: list[dict]) -> pd.DataFrame:
    """Bang chu ky dung tay. Danh sach rong van phai co du cot, vi
    aggregate_cycles luon reindex ve du cot."""
    base = {}
    for q in (1, 2, 3, 4):
        base |= {f"q{q}_open": 100.0, f"q{q}_high": 101.0,
                 f"q{q}_low": 99.0, f"q{q}_close": 100.0, f"q{q}_n": 10.0}
    if not rows:
        return pd.DataFrame(columns=list(base)).astype("float64")
    return pd.DataFrame([base | r for r in rows])


def test_base_trigger_matches_phase1_definition():
    w = _wide([
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 105},   # sweep len + reclaim
        _RANGE | {"q2_high": 105, "q2_low": 85, "q2_close": 95},    # sweep xuong + reclaim
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 112},   # sweep len, KHONG reclaim
        _RANGE | {"q2_high": 105, "q2_low": 95, "q2_close": 100},   # khong sweep
    ])
    up, dn = base_trigger(w)
    assert list(up) == [True, False, False, False]
    assert list(dn) == [False, True, False, False]


def test_base_trigger_excludes_both_sided_sweeps():
    """Sweep ca hai phia bi loai khoi CA up va dn (spec 1b §2)."""
    w = _wide([_RANGE | {"q2_high": 115, "q2_low": 85, "q2_close": 100}])
    up, dn = base_trigger(w)
    assert not up[0] and not dn[0]


def test_base_trigger_treats_boundary_touch_as_no_sweep():
    """Bang dung bien khong phai sweep: so sanh la > va <, khong phai >= <=."""
    w = _wide([_RANGE | {"q2_high": 110, "q2_low": 90, "q2_close": 100}])
    up, dn = base_trigger(w)
    assert not up[0] and not dn[0]


def test_base_trigger_treats_close_on_the_edge_as_no_reclaim():
    """q2_close bang dung q1_high la hoa, khong tinh reclaim."""
    w = _wide([_RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 110}])
    assert not base_trigger(w)[0][0]


def test_base_trigger_treats_close_on_the_low_edge_as_no_reclaim():
    """q2_close bang dung q1_low la hoa, khong tinh reclaim (down-side mirror)."""
    w = _wide([_RANGE | {"q2_high": 105, "q2_low": 85, "q2_close": 90}])
    assert not base_trigger(w)[1][0]


def test_pooled_against_normalises_direction():
    up = np.array([True, False, True])
    dn = np.array([False, True, False])
    direction = np.array([-1.0, 1.0, 1.0])      # xuong, len, len
    got = pooled(up, dn, direction, against=True)
    assert got["p"] == pytest.approx(2.0 / 3.0)  # -1 sau sweep len, +1 sau sweep xuong
    assert got["n"] == 3.0 and got["n_up"] == 2.0 and got["n_dn"] == 1.0


def test_pooled_with_against_false_is_the_complement():
    up = np.array([True, False, True])
    dn = np.array([False, True, False])
    direction = np.array([-1.0, 1.0, 1.0])
    a = pooled(up, dn, direction, against=True)
    b = pooled(up, dn, direction, against=False)
    assert a["p"] + b["p"] == pytest.approx(1.0)
    assert a["n"] == b["n"]


def test_pooled_drops_zero_direction_as_a_tie():
    up = np.array([True, True])
    dn = np.array([False, False])
    direction = np.array([-1.0, 0.0])
    got = pooled(up, dn, direction, against=True)
    assert got["n"] == 1.0 and got["p"] == 1.0 and got["n_up"] == 1.0


def test_pooled_on_empty_selection_returns_nan():
    up = np.array([False, False])
    dn = np.array([False, False])
    got = pooled(up, dn, np.array([1.0, -1.0]), against=True)
    assert got["n"] == 0.0 and np.isnan(got["p"])


def test_q3_dir_is_sign_of_close_minus_open():
    w = _wide([{"q3_open": 100, "q3_close": 105},
               {"q3_open": 100, "q3_close": 95},
               {"q3_open": 100, "q3_close": 100}])
    assert list(q3_dir(w)) == [1.0, -1.0, 0.0]


def test_v1_measures_continuation_not_reversal():
    """V1 dao thesis: dem Q3 di CUNG huong sweep."""
    w = _wide([
        _SWEEP_UP | {"q3_open": 105, "q3_close": 110},   # sweep len, Q3 len -> cung
        _SWEEP_UP | {"q3_open": 105, "q3_close": 100},   # sweep len, Q3 xuong -> nguoc
    ])
    assert variant_v1(w)["p"] == 0.5


def test_v1_is_exactly_one_minus_the_reversal_measure():
    """V1 = 1 - phep do 6 tren dung cung tap con (spec 1b §7). Day la ly do
    duong A khong chung minh duoc gi tren du lieu da xem."""
    w = _wide([
        _SWEEP_UP | {"q3_open": 105, "q3_close": 110},
        _SWEEP_UP | {"q3_open": 105, "q3_close": 100},
        _SWEEP_DN | {"q3_open": 95, "q3_close": 100},
    ])
    up, dn = base_trigger(w)
    reversal = pooled(up, dn, q3_dir(w), against=True)["p"]
    assert variant_v1(w)["p"] + reversal == pytest.approx(1.0)


def test_v3_requires_close_past_the_midpoint():
    """Trung diem cua range Q1 [90, 110] la 100."""
    w = _wide([
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 99,
                  "q3_open": 99, "q3_close": 95},        # dong DUOI 100 -> tinh
        _RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 105,
                  "q3_open": 105, "q3_close": 100},      # dong tren 100 -> loai
    ])
    got = variant_v3(w)
    assert got["n"] == 1.0 and got["n_up"] == 1.0
    assert got["p"] == 1.0


def test_v3_midpoint_is_a_tie_and_gets_dropped():
    w = _wide([_RANGE | {"q2_high": 115, "q2_low": 95, "q2_close": 100,
                         "q3_open": 100, "q3_close": 95}])
    assert variant_v3(w)["n"] == 0.0


def test_v3_keeps_the_both_sided_exclusion():
    """Dieu kien V3 khien up va dn khong the cung dung, nhung chu ky sweep ca
    hai bien van bi loai nhu moi bien the khac (spec 1b §2)."""
    w = _wide([_RANGE | {"q2_high": 115, "q2_low": 85, "q2_close": 95,
                         "q3_open": 95, "q3_close": 90}])
    assert variant_v3(w)["n"] == 0.0


def test_v4_measures_q3_open_to_q4_close():
    w = _wide([
        _SWEEP_UP | {"q3_open": 105, "q4_close": 100},   # sweep len, ket thap -> nguoc
        _SWEEP_UP | {"q3_open": 105, "q4_close": 108},   # sweep len, ket cao -> theo
    ])
    got = variant_v4(w)
    assert got["n"] == 2.0 and got["p"] == 0.5


def test_v4_uses_q4_close_not_q3_close():
    """Q3 di mot huong, Q4 keo lai huong khac: V4 phai theo q4_close."""
    w = _wide([_SWEEP_UP | {"q3_open": 105, "q3_close": 95, "q4_close": 112}])
    assert variant_v4(w)["p"] == 0.0        # theo huong sweep, khong nguoc
    assert variant_v3(w)["n"] == 0.0        # V3 loai vi q2_close 105 > trung diem


def test_v5_filters_by_true_open_side():
    """True Open = q2_open. Sweep len can dau Q3 o premium (tren TO)."""
    w = _wide([
        _SWEEP_UP | {"q2_open": 100, "q3_open": 105, "q3_close": 100},  # premium -> giu
        _SWEEP_UP | {"q2_open": 100, "q3_open": 95, "q3_close": 90},    # discount -> loai
    ])
    got = variant_v5(w)
    assert got["n"] == 1.0 and got["p"] == 1.0


def test_v5_mirrors_for_downside_sweeps():
    w = _wide([
        _SWEEP_DN | {"q2_open": 100, "q3_open": 95, "q3_close": 100},   # discount -> giu
        _SWEEP_DN | {"q2_open": 100, "q3_open": 105, "q3_close": 110},  # premium -> loai
    ])
    got = variant_v5(w)
    assert got["n"] == 1.0 and got["n_dn"] == 1.0 and got["p"] == 1.0


def test_v5_drops_price_exactly_at_the_true_open():
    w = _wide([_SWEEP_UP | {"q2_open": 100, "q3_open": 100, "q3_close": 95}])
    assert variant_v5(w)["n"] == 0.0


def test_v3_down_side_genuine_single_sweep_above_midpoint():
    """V3 down-side: single-sweep down voi q2_close tren trung diem cua q1_range.

    So voi test_v3_requires_close_past_the_midpoint (up-side) nhung day la
    down-side sweep: Q1 [90, 110], trung diem 100; Q2 scan xuong (q2_low 85 <
    q1_low 90) va dong tren trung diem (q2_close > 100), Q3 tang (95 -> 100).
    Expect n_dn = 1, co tac dong tien thuan (100 > 95).
    """
    w = _wide([_RANGE | {"q2_high": 105, "q2_low": 85, "q2_close": 105,
                         "q3_open": 95, "q3_close": 100}])
    got = variant_v3(w)
    assert got["n"] == 1.0 and got["n_dn"] == 1.0
    assert got["p"] == 1.0


def test_trailing_tight_uses_only_prior_cycles():
    """Test nay duoc thiet ke rieng de bat viec THIEU shift(1).

    window=2 va bo so [10, 2, 4] la co y: median rat ben nen phan lon du lieu
    test se KHONG phan biet duoc hai cai dat. O day chung khac nhau ro:
      co shift(1)   : median(idx0, idx1) = median(10, 2) = 6 -> 4 < 6  -> True
      thieu shift(1): median(idx1, idx2) = median(2, 4)  = 3 -> 4 < 3  -> False
    """
    r1 = pd.Series([10.0, 2.0, 4.0])
    assert list(trailing_tight(r1, 2)) == [False, False, True]
    naive = (r1 < r1.rolling(2).median()).to_numpy()      # ban thieu shift(1)
    assert list(naive) == [False, True, False]


def test_trailing_tight_drops_cycles_without_a_full_window():
    """Chua du `window` chu ky truoc do -> median NaN -> loai."""
    r1 = pd.Series([5.0, 5.0, 5.0, 1.0])
    got = trailing_tight(r1, 3)
    assert list(got[:3]) == [False, False, False]
    assert got[3]


def test_trailing_tight_treats_equality_as_a_tie():
    """`<` chat: bang dung median la hoa nen loai (spec 1b §2)."""
    r1 = pd.Series([4.0, 4.0, 4.0])
    assert not trailing_tight(r1, 2)[2]


def test_v2_only_counts_cycles_with_a_tight_q1():
    """Q1 range: 20 chu ky dau la 20, chu ky cuoi la 2 -> chi chu ky cuoi tinh."""
    rows = []
    for _ in range(TRAILING_WINDOW):
        rows.append(_SWEEP_UP | {"q1_high": 110.0, "q1_low": 90.0,
                                 "q3_open": 105.0, "q3_close": 100.0})
    rows.append(_SWEEP_UP | {"q1_high": 101.0, "q1_low": 99.0,
                             "q2_high": 115.0, "q2_low": 99.5, "q2_close": 100.0,
                             "q3_open": 100.0, "q3_close": 95.0})
    got = variant_v2(_wide(rows))
    assert got["n"] == 1.0
    assert got["p"] == 1.0


def test_v2_uses_the_module_window():
    assert TRAILING_WINDOW == 20


def test_v2_on_empty_table_returns_nan():
    got = variant_v2(_wide([]))
    assert got["n"] == 0.0 and np.isnan(got["p"])


@pytest.mark.parametrize("fn", [variant_v1, variant_v3, variant_v4, variant_v5])
def test_variants_on_empty_table_return_nan(fn):
    got = fn(_wide([]))
    assert got["n"] == 0.0 and np.isnan(got["p"])


def test_registry_holds_all_five_and_splits_the_two_tracks():
    assert set(VARIANTS) == {"V1", "V2", "V3", "V4", "V5"}
    assert DIRECT_VARIANT == "V1"
    assert SCREEN_VARIANTS == ("V2", "V3", "V4", "V5")
    assert DIRECT_VARIANT not in SCREEN_VARIANTS      # V1 KHONG qua vong sang
    assert PRIMARY_TIER == "q90"


def test_split_halves_puts_the_odd_bar_in_the_second_half():
    base = epoch_for_ny(2026, 6, 1, 18)
    n = 7
    bars = make_bars([1.0] * n, [1.0] * n, [1.0] * n, [1.0] * n)
    bars.time = np.arange(base, base + 300 * n, 300, dtype="int64")
    first, second = split_halves(bars)
    assert len(first) == 3 and len(second) == 4
    assert first.time[-1] < second.time[0]


def test_split_halves_covers_every_bar_exactly_once():
    base = epoch_for_ny(2026, 6, 1, 18)
    n = 10
    bars = make_bars([1.0] * n, [1.0] * n, [1.0] * n, [1.0] * n)
    bars.time = np.arange(base, base + 300 * n, 300, dtype="int64")
    first, second = split_halves(bars)
    assert list(np.concatenate([first.time, second.time])) == list(bars.time)


def test_pick_winner_takes_the_highest_percentile():
    d = pd.DataFrame([
        {"variant": "V2", "real": 0.5, "n": 100.0, "percentile": 40.0},
        {"variant": "V3", "real": 0.6, "n": 100.0, "percentile": 90.0},
        {"variant": "V4", "real": 0.5, "n": 100.0, "percentile": 70.0},
        {"variant": "V5", "real": 0.5, "n": 100.0, "percentile": 10.0},
    ])
    assert pick_winner(d) == "V3"


def test_pick_winner_breaks_a_percentile_tie_by_larger_n():
    d = pd.DataFrame([
        {"variant": "V2", "real": 0.5, "n": 100.0, "percentile": 90.0},
        {"variant": "V3", "real": 0.5, "n": 500.0, "percentile": 90.0},
        {"variant": "V4", "real": 0.5, "n": 100.0, "percentile": 10.0},
        {"variant": "V5", "real": 0.5, "n": 100.0, "percentile": 10.0},
    ])
    assert pick_winner(d) == "V3"


def test_pick_winner_falls_back_to_the_declared_order():
    """Luat tie-break chot trong spec de khong phai quyet sau khi thay so."""
    d = pd.DataFrame([
        {"variant": "V5", "real": 0.5, "n": 100.0, "percentile": 90.0},
        {"variant": "V3", "real": 0.5, "n": 100.0, "percentile": 90.0},
        {"variant": "V2", "real": 0.5, "n": 100.0, "percentile": 90.0},
        {"variant": "V4", "real": 0.5, "n": 100.0, "percentile": 90.0},
    ])
    assert pick_winner(d) == "V2"


def test_pick_winner_ignores_nan_percentiles():
    d = pd.DataFrame([
        {"variant": "V2", "real": np.nan, "n": 0.0, "percentile": np.nan},
        {"variant": "V3", "real": 0.5, "n": 10.0, "percentile": 20.0},
        {"variant": "V4", "real": np.nan, "n": 0.0, "percentile": np.nan},
        {"variant": "V5", "real": np.nan, "n": 0.0, "percentile": np.nan},
    ])
    assert pick_winner(d) == "V3"


def test_verdict_requires_beating_every_null_not_percentile_95():
    """Nguong la 'vuot CA moi luoi null' (spec 1b §5). percentile 96 tren 69
    luoi null KHONG du: no nghia la con 2 luoi null vuot gia tri that."""
    a = {"variant": "V1", "real": 0.55, "percentile": 96.0, "n": 100.0,
         "n_nulls": 69, "beat_all_nulls": False}
    b = {"variant": "V3", "real": 0.52, "percentile": 80.0, "n": 100.0,
         "n_nulls": 69, "beat_all_nulls": False}
    winner, text = verdict(a, b)
    assert winner is None
    assert "KHONG duong nao pass" in text


def test_verdict_passes_the_track_that_beat_every_null():
    a = {"variant": "V1", "real": 0.55, "percentile": 100.0, "n": 100.0,
         "n_nulls": 69, "beat_all_nulls": True}
    b = {"variant": "V3", "real": 0.52, "percentile": 80.0, "n": 100.0,
         "n_nulls": 69, "beat_all_nulls": False}
    winner, _ = verdict(a, b)
    assert winner == "A"


def test_verdict_prefers_track_b_when_both_pass_and_tie():
    """Duong B la phat hien, duong A chi la kiem do on dinh (spec 1b §6, §7)."""
    a = {"variant": "V1", "real": 0.55, "percentile": 100.0, "n": 100.0,
         "n_nulls": 69, "beat_all_nulls": True}
    b = {"variant": "V3", "real": 0.60, "percentile": 100.0, "n": 100.0,
         "n_nulls": 69, "beat_all_nulls": True}
    winner, _ = verdict(a, b)
    assert winner == "B"


def test_verdict_text_says_quarterly_theory_is_closed_when_nothing_passes():
    a = {"variant": "V1", "real": 0.5, "percentile": 50.0, "n": 10.0,
         "n_nulls": 69, "beat_all_nulls": False}
    b = {"variant": "V3", "real": 0.5, "percentile": 50.0, "n": 10.0,
         "n_nulls": 69, "beat_all_nulls": False}
    _, text = verdict(a, b)
    assert "dong lai" in text and "Phase 1c" in text


def _build_variant_bars(n_cycles: int = 30):
    """Dung bar M5 THEO TUNG CHU KY de Q2 that su sweep va dong lai trong range.

    Fix round 1 dung `open = 100 + (i % 10)`: chu ky 10 chia het cua so 18 bar
    cua quarter nen MOI quarter co high/low giong het nhau va `q2_high ==
    q1_high` khong bao gio thoa so sanh chat `>` -> khong chu ky nao duoc
    chon. Ham nay xay tung quarter co y, khong dung ham tuan hoan toan cuc bo:

      Q1 (bar 0..17)  : dai hep, high/low CO DINH trong chu ky nay. Tu chu ky
                        thu 20 tro di (TIGHT_FROM) range hep lai (0.5 thay vi
                        1.0) de tao "qua khu" cho `trailing_tight` cua V2 so
                        sanh - 20 chu ky dau (range rong) lam median truot, 10
                        chu ky sau (range hep) deu hep hon median do.
      Q2 (bar 18..35) : bar dau tien co high vuot han high Q1 (sweep len); 17
                        bar con lai dong FLAT tai mot gia trong khoang (q1_low,
                        trung diem Q1) - do la q2_close, tuc dong lai (reclaim)
                        trong range Q1 va o duoi trung diem. Khong bar nao cham
                        q1_low nen khong bao gio sweep ca hai phia.
      Q3 (bar 36..53) : mo dau co dinh 100.1 (tren True Open 100.0 cua Q2 ->
                        "premium", de V5 co du lieu), dong doi chieu (103.0
                        hoac 97.0) theo tinh chan-le cua chu ky de q3_close !=
                        q3_open (khong hoa) va xac suat do khong tam thuong la
                        0.0 hay 1.0.
      Q4 (bar 54..71) : dong doi chieu song song voi Q3 (gia tri khac) de V4
                        (do q3_open doi q4_close) cung co du lieu; hinh dang
                        khong quan trong voi cac bien the con lai.

    Hoan toan tat dinh: khong dung random, ke ca co seed.
    """
    base = epoch_for_ny(2026, 6, 1, 18)
    o: list[float] = []
    h: list[float] = []
    l: list[float] = []
    c: list[float] = []

    TIGHT_FROM = 20
    for cyc in range(n_cycles):
        if cyc < TIGHT_FROM:
            q1_high, q1_low = 100.5, 99.5      # range 1.0 - "qua khu" cho V2
        else:
            q1_high, q1_low = 100.25, 99.75    # range 0.5 - hep hon median qua khu

        up = cyc % 2 == 0      # tinh chan-le quyet dinh huong Q3/Q4

        # Q1: dai hep, high/low co dinh trong tung bar cua chu ky nay.
        for _ in range(18):
            o.append(100.0); h.append(q1_high); l.append(q1_low); c.append(100.0)

        # Q2: bar dau sweep vuot high Q1; cac bar sau dong flat tai gia
        # reclaim (duoi trung diem Q1, tren q1_low) - do la q2_close.
        o.append(100.0); h.append(q1_high + 1.5); l.append(q1_low + 0.2)
        c.append(q1_high + 1.0)
        reclaim = q1_low + 0.05
        for _ in range(17):
            o.append(reclaim); h.append(reclaim); l.append(reclaim); c.append(reclaim)

        # Q3: bar dau mo tai 100.1 (q3_open); bar cuoi dong tai q3_close doi
        # chieu theo tinh chan-le.
        q3_close = 103.0 if up else 97.0
        for _ in range(17):
            o.append(100.1); h.append(100.2); l.append(100.0); c.append(100.1)
        o.append(100.1)
        h.append(max(100.1, q3_close) + 0.1)
        l.append(min(100.1, q3_close) - 0.1)
        c.append(q3_close)

        # Q4: song song voi Q3, gia tri khac (q4_close).
        q4_close = 103.5 if up else 96.5
        for _ in range(17):
            o.append(100.1); h.append(100.2); l.append(100.0); c.append(100.1)
        o.append(100.1)
        h.append(max(100.1, q4_close) + 0.1)
        l.append(min(100.1, q4_close) - 0.1)
        c.append(q4_close)

    bars = make_bars(o, h, l, c)
    bars.time = np.arange(base, base + 300 * len(c), 300, dtype="int64")
    return bars


def test_screen_returns_four_variants_with_correct_columns():
    """Test end-to-end screen() tren bar tong hop theo tung chu ky.

    30 chu ky q90 (2160 bar M5, xem `_build_variant_bars`): 20 chu ky dau Q1
    rong (range 1.0), 10 chu ky sau (20..29) Q1 hep (range 0.5). Vi 20 chu ky
    dau deu rong, median truot 20-chu-ky cua ca 10 chu ky sau van con neo o
    1.0, nen ca 10 chu ky do deu hep hon median va duoc V2 giu lai -> V2 CO
    du lieu that (n=10), khong phai truong hop duoc mien tru khoi assertion
    n>0. Da xac nhan bang script chay thu (xem bao cao task-5, muc Fix round
    2): n = {V2:10, V3:30, V4:30, V5:30}, real = 0.5 o ca bon dong.
    """
    bars = _build_variant_bars()

    # Tao offset nho de chay nhanh (5 offset, seed=1).
    offsets = make_offsets("q90", 300, 5, seed=1)
    assert offsets.size > 0

    # Run screen.
    result = screen(bars, "q90", offsets)

    # Kiem tra: 4 dong (V2, V3, V4, V5).
    assert len(result) == 4

    # Kiem tra: dung cac cot required.
    assert set(result.columns) == {"variant", "real", "n", "percentile"}

    # Kiem tra: variant theo thu tu, neu f"{name}.p" sai thi raise KeyError.
    assert list(result["variant"]) == list(SCREEN_VARIANTS)

    # Khong suy bien (day la phan fix round 1 thieu): MOI dong, ke ca V2,
    # phai chon duoc chu ky (n > 0) va real phai huu han. Neu bar khong tao
    # duoc sweep thi n = 0 va real = NaN cho tat ca, dung nhu fix round 1.
    for _, row in result.iterrows():
        assert row["n"] > 0, f"{row['variant']}: n=0, bar khong tao duoc sweep"
        assert np.isfinite(row["real"]), f"{row['variant']}: real khong huu han"

    # It nhat mot dong phai co percentile huu han (can luoi null cho gia tri
    # so sanh duoc, khong chi la lua chon xep hang tren mot ket qua rong).
    assert result["percentile"].apply(np.isfinite).any()


def test_confirm_returns_dict_with_required_keys_and_bool_flag():
    """Test end-to-end confirm() tren cung bo bar tung-chu-ky cua screen().

    Kiem tra confirm tra ve dict co dung bo khoa (khoa "p-value/n_up/n_dn"
    them vao boi fix round cuoi cho legible/auditable, xem fix 3 va fix 4 cua
    dot review cuoi nhanh), beat_all_nulls la bool (khong phai numpy bool hay
    None) vi logic quyet dinh o task sau branch tren, VA ket qua khong suy
    bien (n > 0, real huu han) - phan fix round 1 thieu. Da xac nhan bang
    script chay thu: n=30, real=0.5.
    """
    bars = _build_variant_bars()

    # Tao offset.
    offsets = make_offsets("q90", 300, 5, seed=1)
    assert offsets.size > 0

    # Run confirm cho V1.
    result = confirm(bars, "q90", offsets, "V1")

    # Kiem tra: dung bo khoa da duoc chot (khoa pin, khong phai subset check -
    # diem cua assertion nay la bo khoa bi khoa cung).
    assert set(result.keys()) == {"variant", "real", "n", "n_up", "n_dn",
                                  "percentile", "n_nulls", "k_nulls_ge",
                                  "p_value", "beat_all_nulls"}

    # Kiem tra: variant la "V1".
    assert result["variant"] == "V1"

    # Kiem tra: beat_all_nulls la bool that (khong phai numpy.bool_).
    assert isinstance(result["beat_all_nulls"], bool)
    assert not isinstance(result["beat_all_nulls"], np.bool_)

    # Khong suy bien: phai co chu ky duoc chon va real phai huu han.
    assert result["n"] > 0
    assert np.isfinite(result["real"])


def _make_gapped_bars(n1: int = 1200, n2: int = 1300, step: int = 300):
    """2500 bar M5 lien tuc trong hai doan, cach nhau dung mot khe cuoi tuan
    that (Chu nhat 18:00 NY -> Chu nhat 18:00 NY tuan sau), de cong chan
    `verify_server_tz` PASS ma khong can du lieu MT5 that.

    Khong co khe nao khac (moi doan lien tuc noi bo) nen kiem dinh 2 (khe
    trong ngay) pass rong - dung y, chi can kiem dinh 1 (khe cuoi tuan) that.
    """
    sun1 = epoch_for_ny(2026, 6, 7, 18)    # Chu nhat
    sun2 = epoch_for_ny(2026, 6, 14, 18)   # Chu nhat tuan sau
    t1 = np.arange(sun1, sun1 + step * n1, step, dtype="int64")
    t2 = np.arange(sun2, sun2 + step * n2, step, dtype="int64")
    time = np.concatenate([t1, t2])
    n = time.size
    bars = make_bars([1.0] * n, [1.0] * n, [1.0] * n, [1.0] * n)
    bars.time = time
    return bars


def _cli_module():
    """Nap scripts/study_quarter_variants.py nhu mot module co the monkeypatch.

    Cung cach test_cli.py da dung cho run_rsi2_swing: chen thu muc scripts/
    vao sys.path roi importlib.import_module theo ten file (scripts/ khong
    phai package).
    """
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    return importlib.import_module("study_quarter_variants")


def test_main_wires_screen_to_first_half_and_confirm_to_second_half(monkeypatch, tmp_path):
    """Pin chieu noi day quan trong nhat cua CLI (spec 1b sec 3-4): sang tren
    NUA DAU, kiem CA HAI duong tren NUA SAU. Neu ai do hoan doi hai nua khi
    goi `screen`/`confirm`, nghien cuu se sai ma van ra ket qua hop ly - chi
    con nguoi review moi bat duoc dieu do tu truoc. Test nay thay the review
    do bang mot assertion tu dong.

    Monkeypatch `load_bars` de khong dung MT5/parquet that; monkeypatch
    `screen`/`confirm` nhu chung duoc tra cuu trong module CLI (khong phai
    trong rsi_fvg.quarter_variants) de ghi lai object `Bars` moi ham nhan
    duoc, roi doi chieu voi `split_halves` goi truc tiep tren cung bo bar.
    """
    mod = _cli_module()
    bars = _make_gapped_bars()
    expected_first, expected_second = split_halves(bars)

    monkeypatch.setattr(mod, "load_bars", lambda symbol, tf, data_dir: bars)

    screen_calls: list = []
    confirm_calls: list = []

    def fake_screen(bars_first, tier, offsets, min_bars=3):
        screen_calls.append(bars_first)
        return pd.DataFrame([
            {"variant": "V2", "real": 0.5, "n": 10.0, "percentile": 40.0},
            {"variant": "V3", "real": 0.6, "n": 10.0, "percentile": 90.0},
            {"variant": "V4", "real": 0.5, "n": 10.0, "percentile": 70.0},
            {"variant": "V5", "real": 0.5, "n": 10.0, "percentile": 10.0},
        ])

    def fake_confirm(bars_second, tier, offsets, variant, min_bars=3):
        confirm_calls.append((bars_second, variant))
        return {"variant": variant, "real": 0.5, "n": 10.0, "n_up": 5.0,
                "n_dn": 5.0, "percentile": 50.0, "n_nulls": 69,
                "k_nulls_ge": 34, "p_value": 0.5, "beat_all_nulls": False}

    monkeypatch.setattr(mod, "screen", fake_screen)
    monkeypatch.setattr(mod, "confirm", fake_confirm)

    rc = mod.main(["--tf", "M5", "--out-dir", str(tmp_path)])
    assert rc == 0

    # screen() nhan dung mot lan, dung NUA DAU.
    assert len(screen_calls) == 1
    assert np.array_equal(screen_calls[0].time, expected_first.time)

    # confirm() nhan dung hai lan, CA HAI lan deu la NUA SAU.
    assert len(confirm_calls) == 2
    for bars_second, _variant in confirm_calls:
        assert np.array_equal(bars_second.time, expected_second.time)

    # Hai nua khong de chong nhau - bat mot test vo tinh truyen trung mot
    # object hai lan roi goi la "da kiem tra".
    assert expected_first.time[-1] < expected_second.time[0]
    assert screen_calls[0].time[-1] < confirm_calls[0][0].time[0]

    # Duong A dung bien the pre-specified; duong B dung bien the thang vong
    # sang. Hoan doi hai duong cung se bi bat o day.
    called_variants = [v for _, v in confirm_calls]
    assert called_variants[0] == DIRECT_VARIANT == "V1"
    assert called_variants[1] == "V3"      # percentile cao nhat trong fake_screen
