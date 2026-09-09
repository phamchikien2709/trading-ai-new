import numpy as np
import pandas as pd
import pytest

from rsi_fvg.quarter_variants import base_trigger, pooled, q3_dir

_RANGE = {"q1_high": 110.0, "q1_low": 90.0}


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
	assert got["n"] == 1.0 and got["p"] == 1.0


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
