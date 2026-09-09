import numpy as np
import pandas as pd
import pytest

from conftest import epoch_for_ny, make_bars
from rsi_fvg.quarter_variants import (DIRECT_VARIANT, PRIMARY_TIER, SCREEN_VARIANTS,
                                      TRAILING_WINDOW, VARIANTS, base_trigger, confirm,
                                      pick_winner, pooled, q3_dir, screen, split_halves,
                                      trailing_tight, variant_v1, variant_v2, variant_v3,
                                      variant_v4, variant_v5, verdict)

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
