# Quarterly Theory Variants Study (Phase 1b) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đo năm cách hình thức hoá khác của ý tưởng sweep-reclaim sau khi cách thứ nhất thất bại ở Phase 1, với kiểm soát đa kiểm định đủ chặt để kết quả có nghĩa.

**Architecture:** Toàn bộ hạ tầng đo đã có từ Phase 1. Việc mới là năm hàm biến thể trên **cùng bảng chu kỳ**, một trigger dùng chung để chúng so sánh được với nhau, phép chia 50/50 theo thời gian, và hai đường kiểm định độc lập. `rsi_fvg/quarter_stats.py` chỉ bị sửa **một chỗ**: thêm tham số `stats` cho `run_grid`/`run_null` để Phase 1b truyền dict riêng.

**Tech Stack:** Python 3.13, numpy ≥ 2.0, pandas ≥ 2.2, pytest ≥ 8.0. **Không thêm dependency nào.**

**Spec:** `docs/superpowers/specs/2026-09-09-quarterly-theory-variants-study-design.md`

**Kế thừa:** `docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md` — lớp thời gian §3, bảng chu kỳ §4.2, mô hình null §4.1.

**Branch:** `feat/quarterly-variants-study` (nhánh từ `7d2e99b`, tip của `feat/quarterly-premise-study`)

---

## Đọc trước: điều Phase 1b dễ bị làm sai

**1. Năm biến thể phải dùng ĐÚNG một trigger.** Nếu từng biến thể tự định nghĩa điều kiện sweep thì chúng không còn so sánh được, và vòng sàng ở Task 5 trở thành so táo với cam. Task 2 tách trigger ra một hàm và bốn biến thể ở Task 3–4 **bắt buộc** gọi nó.

**2. Vòng sàng KHÔNG được tuyên bố gì.** Percentile trên nửa đầu chỉ để **xếp hạng**. Nó không phải bằng chứng, không được vào `summary.md` như một kết luận, và không được đọc thành "V3 pass ở nửa đầu".

**3. Ngưỡng là "vượt CẢ 69 lưới null", không phải "percentile > 95".** Xem spec 1b §5: ở tầng q90 với 69 null, α = 2,5% đòi k = 0. Code phải kiểm `np.all(nulls < real)`, không phải `percentile > 95`. Hai điều đó khác nhau và dùng sai sẽ nới ngưỡng một cách âm thầm.

**4. V2 là chỗ duy nhất có nguy cơ lookahead.** `shift(1)` là thứ chặn nó. Task 4 có một test được thiết kế riêng để phát hiện việc thiếu `shift(1)` — median rất bền nên phần lớn dữ liệu test sẽ **không** phân biệt được, test đó dùng `window=2` và bộ số cố ý.

---

## Global Constraints

- Python 3.13. `from __future__ import annotations` ở đầu mỗi module mới.
- **Không thêm dependency.** Chỉ numpy, pandas, pytest.
- **Số biến thể KHOÁ ở 5.** Không thêm V6 dù có ý tưởng hay tới đâu — spec 1b §1.3 và §9.4. Thêm biến thể làm vô hiệu toàn bộ kiểm soát đa kiểm định.
- **Chỉ sửa `rsi_fvg/quarter_stats.py` ở một chỗ:** tham số `stats` cho `run_grid`/`run_null`. Mặc định phải giữ hành vi Phase 1 **không đổi một bit**, và có test khẳng định.
- **Không chạm** `rsi_fvg/quarters.py`, `scripts/study_quarters.py`, `rsi_fvg/backtest/`, `rsi_fvg/strategies/`, `config/`. Phase 1b không tạo `Signal` nào và không nạp engine.
- Trigger chung, y nguyên ⑥ của Phase 1 §4.2: `swept_up = (q2_high > q1_high) & (q2_close < q1_high)`, `swept_dn = (q2_low < q1_low) & (q2_close > q1_low)`, và **loại** chu kỳ `swept_up & swept_dn`.
- Luật loại chu kỳ thiếu bar (`min_bars = 3`) và luật loại hoà áp y nguyên cho lưới thật và mọi lưới null.
- Cột bảng chu kỳ là `q1_`..`q4_` với **`q1` = Q1 của lý thuyết**.
- Tầng chính **`q90`**. Tầng `session` chỉ báo mô tả, **không tuyên bố gì**, không tính vào số kiểm định.
- Chia 50/50 tại `len(bars) // 2`; bar dư thuộc **nửa sau**.
- Tie-break vòng sàng: percentile cao nhất → `n` lớn hơn → thứ tự `V2 → V3 → V4 → V5`.
- Docstring và comment **tiếng Việt**, theo lối `rsi_fvg/quarter_stats.py` đang dùng: nói *tại sao*, trỏ mục spec, ghi rõ chỗ nào là quyết định có ý thức.
- Commit sau mỗi task, message tiếng Anh không dấu, kết bằng `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

**Số Phase 1 để đối chiếu** (spec 1b §1.1): ⑥ pooled thật = 0,4730 (session, percentile 3,0, n=890) và 0,4847 (q90, percentile 2,9, n=3.988). Tầng q90 có **69** lưới null, tầng session có **200**.

---

## File Structure

- **Create `rsi_fvg/quarter_variants.py`** — năm biến thể + trigger chung + phép chia nửa + hai đường + phán quyết. Một trách nhiệm: *đo biến thể và ra phán quyết*. Không I/O, không CLI.
- **Create `scripts/study_quarter_variants.py`** — CLI. Nạp parquet, chạy cổng chặn timezone, chia, sàng, kiểm, ghi `results/`, in phán quyết.
- **Create `tests/test_quarter_variants.py`** — Task 2–5.
- **Modify `rsi_fvg/quarter_stats.py`** — Task 1, tham số `stats`.
- **Modify `tests/test_quarter_stats.py`** — Task 1, test khẳng định mặc định không đổi hành vi.
- **Modify `README.md`** — Task 7.

Dùng lại **không sửa**: `aggregate_cycles`, `make_offsets`, `percentile_of`, `MIN_BARS_PER_QUARTER` (từ `quarter_stats`); `label_quarters`, `server_to_ny`, `verify_server_tz`, `TIERS` (từ `quarters`); `Bars.slice` (từ `bars`).

---

## Task 1: Tham số `stats` cho `run_grid` / `run_null`

Task này sửa code của Phase 1, nên nó có cổng review riêng: điều phải chứng minh là **hành vi mặc định không đổi một bit**.

**Files:**
- Modify: `rsi_fvg/quarter_stats.py`
- Modify: `tests/test_quarter_stats.py`

**Interfaces:**
- Consumes: `STATS`, `run_grid`, `run_null` hiện có
- Produces:
  - `run_grid(bars, tier, anchor_offset=0, min_bars=MIN_BARS_PER_QUARTER, stats=None) -> dict[str, float]`
  - `run_null(bars, tier, offsets, min_bars=MIN_BARS_PER_QUARTER, stats=None) -> pd.DataFrame`
  - `stats=None` nghĩa là dùng `STATS`

- [ ] **Step 1: Viết test đỏ**

Thêm vào cuối `tests/test_quarter_stats.py`:

```python
def test_stats_param_defaults_to_phase1_behaviour_exactly():
    """Mac dinh phai giu hanh vi Phase 1 khong doi mot bit (spec 1b §8)."""
    bars = _one_session_bars()
    implicit = run_grid(bars, "q90")
    explicit = run_grid(bars, "q90", stats=STATS)
    assert implicit == explicit
    assert {k.split(".")[0] for k in implicit} == {
        "sweep", "range_by_index", "displacement_by_index",
        "q1_predicts_q2", "true_open", "reclaim_q3"}


def test_stats_param_restricts_run_grid_to_the_given_dict():
    bars = _one_session_bars()
    only = run_grid(bars, "q90", stats={"sweep": stat_sweep})
    assert set(only) == {"sweep.sweep_rate", "sweep.n"}


def test_stats_param_flows_through_run_null():
    bars = _one_session_bars()
    out = run_null(bars, "q90", np.array([1800], dtype="int64"),
                   stats={"sweep": stat_sweep})
    assert set(out.columns) == {"anchor_offset", "sweep.sweep_rate", "sweep.n"}


def test_stats_default_is_none_not_a_shared_dict():
    """Mutable default la footgun: mot caller mutate se doc sang moi caller khac."""
    import inspect
    for fn in (run_grid, run_null):
        assert inspect.signature(fn).parameters["stats"].default is None
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarter_stats.py -q -k stats_param`
Expected: FAIL — `TypeError: run_grid() got an unexpected keyword argument 'stats'`

- [ ] **Step 3: Sửa `run_grid` và `run_null`**

Thay hai hàm trong `rsi_fvg/quarter_stats.py` bằng:

```python
def run_grid(bars: Bars, tier: str, anchor_offset: int = 0,
             min_bars: int = MIN_BARS_PER_QUARTER,
             stats: dict | None = None) -> dict[str, float]:
    """Chạy một bộ thống kê trên một lưới. Khoá dạng "<stat>.<đại lượng>".

    `stats = None` dùng `STATS`, giữ hành vi Phase 1 **không đổi một bit**.
    Phase 1b truyền dict biến thể của riêng nó (spec 1b §8).

    Mặc định là `None` chứ không phải `STATS`: default khả biến là footgun —
    một caller mutate nó sẽ đọc sang mọi caller khác.
    """
    labels = label_quarters(bars.time, tier, anchor_offset)
    w = aggregate_cycles(bars, labels, min_bars)
    table = STATS if stats is None else stats
    out: dict[str, float] = {}
    for name, fn in table.items():
        for key, value in fn(w).items():
            out[f"{name}.{key}"] = value
    return out


def run_null(bars: Bars, tier: str, offsets: np.ndarray,
             min_bars: int = MIN_BARS_PER_QUARTER,
             stats: dict | None = None) -> pd.DataFrame:
    """Một dòng mỗi lưới null. `stats` truyền thẳng xuống `run_grid`."""
    rows = []
    for off in np.asarray(offsets, dtype="int64"):
        row = {"anchor_offset": int(off)}
        row.update(run_grid(bars, tier, int(off), min_bars, stats))
        rows.append(row)
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarter_stats.py -q`
Expected: PASS — 33 test (29 của Phase 1 + 4 mới).

- [ ] **Step 5: Chạy cả suite**

Run: `python -m pytest -q`
Expected: **255 passed** trước Task 1, nên bây giờ **259 passed**. Con số phải khớp đúng — lệch nghĩa là có test khác bị ảnh hưởng, tức mặc định đã đổi hành vi.

- [ ] **Step 6: Commit**

```bash
git add rsi_fvg/quarter_stats.py tests/test_quarter_stats.py
git commit -m "feat(quarter_stats): tham so stats cho run_grid/run_null

Phase 1b can truyen dict bien the rieng. Mac dinh None -> dung STATS nen
hanh vi Phase 1 khong doi mot bit, co test khang dinh dieu do.

Mac dinh None chu khong phai STATS: default kha bien la footgun, mot
caller mutate se doc sang moi caller khac. Co test khang dinh default
dung la None.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Trigger chung và bộ gộp — lõi để năm biến thể so sánh được

Nếu task này sai, cả nghiên cứu sai mà không lộ ra: các biến thể vẫn chạy, vẫn ra số, nhưng không còn đo cùng một thứ.

**Files:**
- Create: `rsi_fvg/quarter_variants.py`
- Create: `tests/test_quarter_variants.py`

**Interfaces:**
- Consumes: `rsi_fvg.quarter_stats.MIN_BARS_PER_QUARTER`
- Produces:
  - `base_trigger(w: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]` — `(up, dn)` đã loại chu kỳ sweep hai phía
  - `pooled(up, dn, direction, against: bool) -> dict[str, float]` — khoá `p`, `n`, `n_up`, `n_dn`
  - `q3_dir(w: pd.DataFrame) -> np.ndarray`

- [ ] **Step 1: Viết test đỏ**

Tạo `tests/test_quarter_variants.py`:

```python
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
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarter_variants.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'rsi_fvg.quarter_variants'`

- [ ] **Step 3: Tạo module với ba hàm lõi**

Tạo `rsi_fvg/quarter_variants.py`:

```python
"""Năm biến thể của phép đo ⑥, cộng hai đường kiểm định của Phase 1b.

Spec: docs/superpowers/specs/2026-09-09-quarterly-theory-variants-study-design.md

Phase 1 đo MỘT cách hình thức hoá ý tưởng sweep-reclaim và nó thất bại
(percentile 3,0 ở tầng session và 2,9 ở q90). Module này đo năm cách khác.

Điều quan trọng nhất về file này: năm biến thể **bắt buộc** dùng đúng
`base_trigger`. Nếu từng biến thể tự định nghĩa điều kiện sweep thì chúng
không còn so sánh được với nhau và vòng sàng ở §4 của spec trở thành so táo
với cam — nghiên cứu vẫn ra số, nhưng số đó vô nghĩa.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .quarter_stats import MIN_BARS_PER_QUARTER


def _mean_or_nan(x: np.ndarray) -> float:
    """Bản sao của hàm cùng tên trong quarter_stats.

    Để cục bộ có ý: spec 1b §Phạm vi cho phép sửa quarter_stats ĐÚNG MỘT chỗ
    (tham số `stats`). Nâng một hàm private của module đó thành public là chỗ
    sửa thứ hai. Hai dòng trùng lặp rẻ hơn việc nới phạm vi.
    """
    return float(np.mean(x)) if x.size else float("nan")


def base_trigger(w: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Trigger chung của mọi biến thể, y nguyên ⑥ của Phase 1 §4.2.

    Trả về `(up, dn)` đã LOẠI chu kỳ sweep cả hai phía: lý thuyết không đưa ra
    kỳ vọng hướng nào cho trường hợp đó, và giữ nó lại sẽ đếm một chu kỳ hai
    lần với hai kỳ vọng trái nhau.

    So sánh là `>` và `<`, không phải `>=` và `<=`: chạm đúng biên không phải
    sweep, và `q2_close` bằng đúng biên là hoà nên không tính reclaim.
    """
    q1h = w["q1_high"].to_numpy()
    q1l = w["q1_low"].to_numpy()
    q2h = w["q2_high"].to_numpy()
    q2l = w["q2_low"].to_numpy()
    q2c = w["q2_close"].to_numpy()
    swept_up = (q2h > q1h) & (q2c < q1h)
    swept_dn = (q2l < q1l) & (q2c > q1l)
    both = swept_up & swept_dn
    return swept_up & ~both, swept_dn & ~both


def q3_dir(w: pd.DataFrame) -> np.ndarray:
    """Hướng của Q3. 0 là hoà và bị `pooled` loại."""
    return np.sign(w["q3_close"].to_numpy() - w["q3_open"].to_numpy())


def pooled(up: np.ndarray, dn: np.ndarray, direction: np.ndarray,
           against: bool) -> dict[str, float]:
    """Gộp hai phía sweep thành một xác suất, chuẩn hoá theo hướng.

    `against=True`  -> P(direction đi NGƯỢC hướng sweep)  — ⑥ và V2..V5
    `against=False` -> P(direction đi CÙNG hướng sweep)   — V1

    `direction == 0` là hoà và bị loại (spec 1b §2). Không loại thì `np.sign`
    cho 0 và quan sát đó rơi vào nhánh "không đạt" một cách tuỳ ý.
    """
    live = direction != 0
    u, d = up & live, dn & live
    if against:
        hits = np.concatenate([direction[u] < 0, direction[d] > 0])
    else:
        hits = np.concatenate([direction[u] > 0, direction[d] < 0])
    return {"p": _mean_or_nan(hits), "n": float(hits.size),
            "n_up": float(u.sum()), "n_dn": float(d.sum())}
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarter_variants.py -q`
Expected: PASS — 9 test.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/quarter_variants.py tests/test_quarter_variants.py
git commit -m "feat(quarter_variants): trigger chung va bo gop cho nam bien the

base_trigger la y nguyen trigger cua phep do 6 o Phase 1, tach ra mot cho
de nam bien the dung chung. Neu tung bien the tu dinh nghia dieu kien
sweep thi chung khong con so sanh duoc va vong sang cua spec 1b section 4
tro thanh so tao voi cam.

pooled chuan hoa huong va nhan co against=True/False de V1 dung chung code
voi V2..V5 thay vi viet lai nguoc dau.

_mean_or_nan de cuc bo co y: spec 1b cho phep sua quarter_stats DUNG MOT
cho (tham so stats), nen nang mot ham private cua no thanh public la cho
sua thu hai.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: V1, V3, V4, V5

Bốn biến thể cùng khuôn: trigger chung, rồi một thay đổi nhỏ. Gộp một task vì chúng cùng hình dạng và cùng bề mặt review.

**Files:**
- Modify: `rsi_fvg/quarter_variants.py`
- Modify: `tests/test_quarter_variants.py`

**Interfaces:**
- Consumes: `base_trigger`, `pooled`, `q3_dir` (Task 2)
- Produces: `variant_v1(w)`, `variant_v3(w)`, `variant_v4(w)`, `variant_v5(w)` — mỗi hàm trả `dict[str, float]` với khoá `p`, `n`, `n_up`, `n_dn`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `tests/test_quarter_variants.py`:

```python
from rsi_fvg.quarter_variants import (variant_v1, variant_v3, variant_v4,
                                      variant_v5)

_SWEEP_UP = _RANGE | {"q2_high": 115.0, "q2_low": 95.0, "q2_close": 105.0}
_SWEEP_DN = _RANGE | {"q2_high": 105.0, "q2_low": 85.0, "q2_close": 95.0}


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


@pytest.mark.parametrize("fn", [variant_v1, variant_v3, variant_v4, variant_v5])
def test_variants_on_empty_table_return_nan(fn):
    got = fn(_wide([]))
    assert got["n"] == 0.0 and np.isnan(got["p"])
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarter_variants.py -q -k "v1 or v3 or v4 or v5"`
Expected: FAIL — `ImportError: cannot import name 'variant_v1'`

- [ ] **Step 3: Cài bốn biến thể**

Thêm vào `rsi_fvg/quarter_variants.py`:

```python
def variant_v1(w: pd.DataFrame) -> dict[str, float]:
    """V1 — Q3 đi CÙNG hướng sweep, tức đảo thesis của ⑥.

    Lý do: số Phase 1 nói Q3 đi cùng hướng sweep 52,7% số lần.

    CẢNH BÁO (spec 1b §7): V1 = 1 − ⑥ trên đúng cùng tập con, nên
    `percentile(V1) = 100 − percentile(⑥)` một cách máy móc. Trên toàn dữ liệu
    nó sẽ ra ~97 và con số đó VÔ GIÁ TRỊ, vì ⑥ đã được xem trước khi V1 được
    nghĩ ra. Giá trị duy nhất của V1 là kiểm độ ổn định qua thời gian trên nửa
    sau — không phải phát hiện.
    """
    up, dn = base_trigger(w)
    return pooled(up, dn, q3_dir(w), against=False)


def variant_v3(w: pd.DataFrame) -> dict[str, float]:
    """V3 — reclaim quyết đoán: Q2 đóng VƯỢT TRUNG ĐIỂM range Q1.

    Lý do: ICT nhấn displacement, còn "đóng lại trong range" của ⑥ nhận cả một
    cú reclaim sát biên.

    Luật loại `both` giữ nguyên như mọi biến thể (spec 1b §2), dù điều kiện của
    V3 khiến `up` và `dn` không thể cùng đúng — một giá đóng không thể vừa dưới
    vừa trên trung điểm. Không đổi luật loại giữa các biến thể, nếu không chúng
    mất tính so sánh được.
    """
    up, dn = base_trigger(w)
    mid = (w["q1_high"].to_numpy() + w["q1_low"].to_numpy()) / 2.0
    q2c = w["q2_close"].to_numpy()
    return pooled(up & (q2c < mid), dn & (q2c > mid), q3_dir(w), against=True)


def variant_v4(w: pd.DataFrame) -> dict[str, float]:
    """V4 — chân trời đo là Q3+Q4 thay vì Q3 một mình.

    Lý do: hai profile AMDX và XAMD dịch vai trò các quarter (spec indicator
    §2.2), nên payoff hướng có thể không gói trong Q3.
    """
    up, dn = base_trigger(w)
    direction = np.sign(w["q4_close"].to_numpy() - w["q3_open"].to_numpy())
    return pooled(up, dn, direction, against=True)


def variant_v5(w: pd.DataFrame) -> dict[str, float]:
    """V5 — lọc theo phía True Open (= open của bar đầu Q2).

    Lý do: §2.4 True Open, kết hợp hai yếu tố được nhắc nhiều nhất của lý thuyết.

    Sweep lên kỳ vọng Q3 giảm nên đòi đầu Q3 ở premium (trên TO); sweep xuống
    đòi đầu Q3 ở discount (dưới TO). Bằng đúng TO là hoà nên bị loại.
    """
    up, dn = base_trigger(w)
    side = np.sign(w["q3_open"].to_numpy() - w["q2_open"].to_numpy())
    return pooled(up & (side > 0), dn & (side < 0), q3_dir(w), against=True)
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarter_variants.py -q`
Expected: PASS — 23 test (9 của Task 2 + 10 test đơn + 4 tham số).

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/quarter_variants.py tests/test_quarter_variants.py
git commit -m "feat(quarter_variants): V1, V3, V4, V5

V1 dao thesis (Q3 di cung huong sweep). Docstring ghi ro dieu no KHONG
chung minh duoc: V1 = 1 - phep do 6 tren dung cung tap con nen percentile
la 100 tru percentile cua 6 mot cach may moc, va con so tren toan du lieu
vo gia tri vi 6 da duoc xem truoc.

V3 doi reclaim quyet doan (dong vuot trung diem range Q1). Giu nguyen luat
loai both du dieu kien V3 khien up va dn khong the cung dung.

V4 doi chan troi sang Q3+Q4. V5 loc theo phia True Open.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: V2 — điều kiện Q1 hẹp, và chỗ duy nhất có nguy cơ lookahead

**Files:**
- Modify: `rsi_fvg/quarter_variants.py`
- Modify: `tests/test_quarter_variants.py`

**Interfaces:**
- Consumes: `base_trigger`, `pooled`, `q3_dir` (Task 2)
- Produces:
  - `TRAILING_WINDOW = 20`
  - `trailing_tight(r1: pd.Series, window: int) -> np.ndarray`
  - `variant_v2(w) -> dict[str, float]`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `tests/test_quarter_variants.py`:

```python
from rsi_fvg.quarter_variants import TRAILING_WINDOW, trailing_tight, variant_v2


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
    assert list(naive) == [False, False, False]


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
                             "q2_high": 115.0, "q2_low": 95.0, "q2_close": 100.0,
                             "q3_open": 100.0, "q3_close": 95.0})
    got = variant_v2(_wide(rows))
    assert got["n"] == 1.0
    assert got["p"] == 1.0


def test_v2_uses_the_module_window():
    assert TRAILING_WINDOW == 20


def test_v2_on_empty_table_returns_nan():
    got = variant_v2(_wide([]))
    assert got["n"] == 0.0 and np.isnan(got["p"])
```

Giải thích `test_v2_only_counts_cycles_with_a_tight_q1`: 20 chu kỳ đầu có `range(Q1) = 20`, nên median trượt tại chu kỳ 21 là 20; chu kỳ 21 có `range(Q1) = 2 < 20` nên **tính**. Hai mươi chu kỳ đầu không đủ cửa sổ nên bị loại. Chu kỳ 21 sweep lên (`q2_high 115 > q1_high 101`, `q2_close 100 < 101`) và Q3 giảm (100 → 95), tức **đi ngược** hướng sweep, nên `p = 1`.

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarter_variants.py -q -k "trailing or v2"`
Expected: FAIL — `ImportError: cannot import name 'TRAILING_WINDOW'`

- [ ] **Step 3: Cài V2**

Thêm vào `rsi_fvg/quarter_variants.py`:

```python
TRAILING_WINDOW = 20


def trailing_tight(r1: pd.Series, window: int) -> np.ndarray:
    """`range(Q1)` nhỏ hơn median TRƯỢT của `window` chu kỳ TRƯỚC ĐÓ.

    `shift(1)` là thứ chặn lookahead, và nó là dòng quan trọng nhất của hàm
    này: thiếu nó thì chu kỳ hiện tại tham gia vào median của chính nó, tức
    điều kiện "Q1 hẹp" được quyết bằng thông tin của chính chu kỳ đang xét.

    Chu kỳ chưa đủ `window` chu kỳ trước đó cho median NaN; `NaN` so sánh ra
    False nên chúng bị loại — đúng ý.

    So sánh `<` chặt: bằng đúng median là hoà nên loại.

    Yêu cầu: `r1` theo thứ tự thời gian. `aggregate_cycles` groupby với
    `sort=True` nên index đã sắp theo `cycle_id`, tức đã theo thời gian.
    """
    med = r1.shift(1).rolling(window).median()
    return (r1 < med).to_numpy()


def variant_v2(w: pd.DataFrame) -> dict[str, float]:
    """V2 — chỉ tính chu kỳ có Q1 hẹp so với quá khứ gần.

    Lý do: chính phát biểu ④ của lý thuyết — "Q1 dictates the quarters which
    follow", Q1 hẹp báo Q2 giãn, nên cú manipulation ở Q2 "thật" hơn.

    Đáng lưu ý: Phase 1 đo ④ và thấy tương quan range Q1 với range Q2 là
    DƯƠNG (+0,71..+0,77), tức ngược hẳn điều lý thuyết đòi. V2 vẫn được thử vì
    ④ đo tương quan tuyến tính đơn điệu trên toàn bộ chu kỳ, còn V2 hỏi một
    câu khác và hẹp hơn: trong tập con Q1 hẹp, tín hiệu sweep có tốt hơn không.
    """
    r1 = w["q1_high"] - w["q1_low"]
    tight = trailing_tight(r1, TRAILING_WINDOW)
    up, dn = base_trigger(w)
    return pooled(up & tight, dn & tight, q3_dir(w), against=True)
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarter_variants.py -q`
Expected: PASS — 29 test.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/quarter_variants.py tests/test_quarter_variants.py
git commit -m "feat(quarter_variants): V2 - dieu kien Q1 hep, khong lookahead

Median TRUOT tren 20 chu ky TRUOC DO, khong phai tercile toan cuc. shift(1)
la dong quan trong nhat: thieu no thi chu ky hien tai tham gia vao median
cua chinh no, tuc dieu kien 'Q1 hep' duoc quyet bang thong tin cua chinh
chu ky dang xet.

Co mot test duoc thiet ke rieng de bat viec thieu shift(1): median rat ben
nen phan lon du lieu test khong phan biet duoc hai cai dat, nen test dung
window=2 va bo so [10, 2, 4] la co y - co shift cho True, thieu shift cho
False.

Docstring ghi ro V2 van duoc thu du Phase 1 da thay tuong quan range Q1 va
Q2 la DUONG (nguoc dieu ly thuyet doi): phep do 4 hoi ve toan bo chu ky,
V2 hoi ve tap con Q1 hep - hai cau khac nhau.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: Chia nửa, hai đường, phán quyết

Đây là lõi phương pháp. Nếu ngưỡng cài sai thành `percentile > 95` thì nghiên cứu tự nới ngưỡng một cách âm thầm.

**Files:**
- Modify: `rsi_fvg/quarter_variants.py`
- Modify: `tests/test_quarter_variants.py`

**Interfaces:**
- Consumes: năm biến thể (Task 3–4); `rsi_fvg.quarter_stats.run_grid`, `run_null`, `percentile_of`, `MIN_BARS_PER_QUARTER`; `rsi_fvg.bars.Bars.slice`
- Produces:
  - `VARIANTS: dict[str, callable]` — cả năm
  - `SCREEN_VARIANTS = ("V2", "V3", "V4", "V5")`, `DIRECT_VARIANT = "V1"`, `PRIMARY_TIER = "q90"`
  - `split_halves(bars) -> tuple[Bars, Bars]`
  - `screen(bars_first, tier, offsets, min_bars=...) -> pd.DataFrame` — cột `variant`, `real`, `n`, `percentile`
  - `pick_winner(screened) -> str`
  - `confirm(bars_second, tier, offsets, variant, min_bars=...) -> dict`
  - `verdict(track_a, track_b) -> tuple[str | None, str]`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `tests/test_quarter_variants.py`:

```python
from conftest import epoch_for_ny, make_bars
from rsi_fvg.quarter_variants import (DIRECT_VARIANT, PRIMARY_TIER,
                                      SCREEN_VARIANTS, VARIANTS, confirm,
                                      pick_winner, screen, split_halves,
                                      verdict)


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
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarter_variants.py -q -k "registry or split or pick or verdict"`
Expected: FAIL — `ImportError: cannot import name 'DIRECT_VARIANT'`

- [ ] **Step 3: Cài registry, chia nửa, hai đường, phán quyết**

Thêm vào `rsi_fvg/quarter_variants.py`. Bổ sung import ở đầu file:
`from .bars import Bars` và `from .quarter_stats import MIN_BARS_PER_QUARTER, percentile_of, run_grid, run_null`.

```python
VARIANTS = {
    "V1": variant_v1, "V2": variant_v2, "V3": variant_v3,
    "V4": variant_v4, "V5": variant_v5,
}

# Đường A: V1 KHÔNG qua vòng sàng — nó đã được định trước nên sàng nó là vô
# nghĩa (spec 1b §4). Đường B: bốn biến thể còn lại.
DIRECT_VARIANT = "V1"
SCREEN_VARIANTS = ("V2", "V3", "V4", "V5")

# Tie-break chốt trong spec §4 để không phải quyết sau khi thấy số.
TIE_BREAK = SCREEN_VARIANTS

# Tầng chính: q90 ít bị confound mốc 18:00 hơn (Phase 1 §8.2). Tầng session
# chỉ báo mô tả, không tuyên bố gì, không tính vào số kiểm định.
PRIMARY_TIER = "q90"


def split_halves(bars: Bars) -> tuple[Bars, Bars]:
    """Chia mảng bar làm hai tại `len//2`; bar dư thuộc NỬA SAU (spec 1b §3).

    Toàn bộ pipeline chạy độc lập trên từng nửa. Chu kỳ vắt qua điểm chia sẽ
    thiếu bar ở nửa nào cũng vậy và bị luật `min_bars` loại tự nhiên — không
    cần xử lý riêng.
    """
    n = len(bars)
    mid = n // 2
    return bars.slice(0, mid), bars.slice(mid, n)


def screen(bars_first: Bars, tier: str, offsets: np.ndarray,
           min_bars: int = MIN_BARS_PER_QUARTER) -> pd.DataFrame:
    """Xếp hạng V2–V5 trên nửa đầu.

    KHÔNG TUYÊN BỐ GÌ TẠI ĐÂY. Percentile trả về chỉ để xếp hạng; nó không
    phải bằng chứng và không được đọc thành "biến thể này pass" (spec 1b §4).
    """
    subset = {k: VARIANTS[k] for k in SCREEN_VARIANTS}
    real = run_grid(bars_first, tier, min_bars=min_bars, stats=subset)
    nulls = run_null(bars_first, tier, offsets, min_bars=min_bars, stats=subset)
    rows = []
    for name in SCREEN_VARIANTS:
        key = f"{name}.p"
        rows.append({"variant": name, "real": real[key], "n": real[f"{name}.n"],
                     "percentile": percentile_of(real[key], nulls[key].to_numpy())})
    return pd.DataFrame(rows)


def pick_winner(screened: pd.DataFrame) -> str:
    """Percentile cao nhất → `n` lớn hơn → thứ tự `TIE_BREAK` (spec 1b §4).

    NaN percentile xuống cuối: một biến thể loại hết chu kỳ không được thắng.
    """
    d = screened.copy()
    d["_order"] = [TIE_BREAK.index(v) for v in d["variant"]]
    d = d.sort_values(["percentile", "n", "_order"],
                      ascending=[False, False, True], na_position="last")
    return str(d.iloc[0]["variant"])


def confirm(bars_second: Bars, tier: str, offsets: np.ndarray, variant: str,
            min_bars: int = MIN_BARS_PER_QUARTER) -> dict:
    """Kiểm định cuối của ĐÚNG MỘT biến thể trên nửa sau.

    `beat_all_nulls` là cờ quyết định, không phải `percentile`. Spec 1b §5:
    tầng q90 có 69 lưới null nên α ≤ 2,5% đòi k = 0, tức giá trị thật phải
    vượt CẢ 69 lưới. Dùng `percentile > 95` sẽ nới ngưỡng một cách âm thầm —
    percentile 96 trên 69 lưới vẫn còn 2 lưới null vượt giá trị thật.
    """
    subset = {variant: VARIANTS[variant]}
    real = run_grid(bars_second, tier, min_bars=min_bars, stats=subset)
    nulls = run_null(bars_second, tier, offsets, min_bars=min_bars, stats=subset)
    value = real[f"{variant}.p"]
    col = nulls[f"{variant}.p"].to_numpy(dtype="float64")
    finite = col[np.isfinite(col)]
    return {
        "variant": variant, "real": value, "n": real[f"{variant}.n"],
        "percentile": percentile_of(value, col),
        "n_nulls": int(finite.size),
        "beat_all_nulls": bool(finite.size > 0 and np.isfinite(value)
                               and np.all(finite < value)),
    }


def verdict(track_a: dict, track_b: dict) -> tuple[str | None, str]:
    """Luật §6 của spec 1b, tính bằng máy — không để người đọc tự kết luận.

    Trả về `(tên đường thắng, văn bản)`. `None` nghĩa là không đường nào pass,
    và khi đó Quarterly Theory ĐÓNG LẠI với repo này: không có Phase 1c.
    """
    lines = ["## Phan quyet spec 1b section 6", ""]
    for name, t in (("A", track_a), ("B", track_b)):
        lines.append(
            f"- duong **{name}** ({t['variant']}): real={t['real']:.4f}, "
            f"percentile={t['percentile']:.1f}, n={t['n']:.0f}, "
            f"nulls={t['n_nulls']} -> "
            f"{'VUOT CA MOI LUOI NULL' if t['beat_all_nulls'] else 'khong vuot'}")

    a_ok, b_ok = bool(track_a["beat_all_nulls"]), bool(track_b["beat_all_nulls"])
    if a_ok and b_ok:
        # Đồng percentile thì ưu tiên đường B: nó là phát hiện, còn đường A chỉ
        # là kiểm độ ổn định của một con số đã biết (spec 1b §6, §7).
        winner = "A" if track_a["percentile"] > track_b["percentile"] else "B"
    elif a_ok:
        winner = "A"
    elif b_ok:
        winner = "B"
    else:
        winner = None

    lines.append("")
    if winner is None:
        lines.append(
            "**KHONG duong nao pass. Quarterly Theory dong lai voi repo nay.** "
            "Day la ket luan, khong phai mot vong thu nua: khong co Phase 1c "
            "(spec 1b section 6).")
    elif winner == "A":
        lines.append(
            f"**Duong A pass** ({track_a['variant']}). Cau duoc phep noi la "
            "'chieu continuation on dinh qua hai nua lich su'. Cau KHONG duoc "
            "phep noi la 'da tim ra mot edge' — xem spec 1b section 7.")
    else:
        lines.append(
            f"**Duong B pass** ({track_b['variant']}). Phase 2 duoc phep viet "
            "spec cho bien the nay.")
    lines += ["", (
        "Pass VAN KHONG nghia la co lai. Nghien cuu nay khong tinh cost; spread "
        "XAUUSDc trong config/default.yaml la 260 points = 0,26 USD "
        "(spec 1b section 6).")]
    return winner, "\n".join(lines)
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarter_variants.py -q`
Expected: PASS — 40 test.

- [ ] **Step 5: Chạy cả suite**

Run: `python -m pytest -q`
Expected: **299 passed** (259 sau Task 1 + 40).

- [ ] **Step 6: Commit**

```bash
git add rsi_fvg/quarter_variants.py tests/test_quarter_variants.py
git commit -m "feat(quarter_variants): chia nua, hai duong, phan quyet section 6

split_halves chia tai len//2, bar du thuoc nua sau. Chu ky vat qua diem
chia bi luat min_bars loai tu nhien.

screen xep hang V2-V5 tren nua dau va KHONG tuyen bo gi tai do. pick_winner
tie-break percentile -> n -> thu tu V2..V5, chot trong spec de khong phai
quyet sau khi thay so.

confirm dung co beat_all_nulls chu KHONG dung percentile > 95: tang q90 co
69 luoi null nen alpha 2.5% doi k=0, tuc phai vuot CA 69 luoi. percentile
96 tren 69 luoi van con 2 luoi null vuot gia tri that, nen dung percentile
se noi nguong mot cach am tham. Co test khang dinh dieu nay.

verdict tinh phan quyet bang may va in ca cau 'khong duong nao pass thi
Quarterly Theory dong lai, khong co Phase 1c'.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: CLI `scripts/study_quarter_variants.py`

**Files:**
- Create: `scripts/study_quarter_variants.py`

**Interfaces:**
- Consumes: Task 1–5; `rsi_fvg.data.mt5_loader.load_or_fetch`; `rsi_fvg.quarters.verify_server_tz`, `TIERS`; `rsi_fvg.quarter_stats.make_offsets`
- Produces: `results/quarter_variants/<YYYY-MM-DD>/{screen.csv, confirm.csv, summary.md}`; mã thoát 0/1/2

- [ ] **Step 1: Viết script**

```python
"""Phase 1b: do nam bien the cua phep do ⑥ sau khi cach thu nhat that bai.

Spec: docs/superpowers/specs/2026-09-09-quarterly-theory-variants-study-design.md

Usage:
  python scripts/study_quarter_variants.py
  python scripts/study_quarter_variants.py --tf M5 --shifts 200 --seed 20260909

Ma thoat: 0 chay xong; 1 cong chan timezone fail; 2 khong du du lieu.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from rsi_fvg.bars import Bars  # noqa: E402
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.quarter_stats import make_offsets  # noqa: E402
from rsi_fvg.quarter_variants import (DIRECT_VARIANT, PRIMARY_TIER,  # noqa: E402
                                      confirm, pick_winner, screen,
                                      split_halves, verdict)
from rsi_fvg.quarters import TIERS, verify_server_tz  # noqa: E402

TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbol", default="XAUUSDc")
    p.add_argument("--tf", default="M5", choices=sorted(TF_SECONDS))
    p.add_argument("--tier", default=PRIMARY_TIER, choices=sorted(TIERS),
                   help="tang chinh cua ca hai duong; spec 1b section 5 chot q90")
    p.add_argument("--shifts", type=int, default=200,
                   help="so luoi null xin; tang q90 chi co 69 moc kha dung")
    p.add_argument("--seed", type=int, default=20260909)
    p.add_argument("--data-dir", type=Path, default=ROOT / "data")
    p.add_argument("--out-dir", type=Path, default=None)
    return p.parse_args(argv)


def load_bars(symbol: str, tf: str, data_dir: Path) -> Bars:
    """load_or_fetch tra ve (DataFrame, SymbolSpec); nghien cuu nay khong dung spec."""
    df, _spec = load_or_fetch(symbol, tf, data_dir)
    return Bars.from_dataframe(df)


def gate_timezone(bars: Bars, bar_seconds: int) -> None:
    """Cong chan Phase 1 section 3.2. Fail thi thoat 1 va KHONG chay tiep."""
    chk = verify_server_tz(bars.time, bar_seconds)
    print("--- cong chan timezone ---")
    print(f"  mo dau tuan  : {chk.weekly_open_mode!r}  ok={chk.weekly_ok}")
    print(f"  ket khe ngay : {chk.daily_gap_end_mode!r}  ok={chk.daily_ok}")
    for note in chk.notes:
        print(f"  ghi chu: {note}")
    if not chk.ok:
        print("\nFAIL: cach doc Bars.time khong khop du lieu nay. Khong chay tiep.")
        sys.exit(1)
    print("  PASS\n")


def main(argv=None) -> int:
    args = parse_args(argv)
    bar_seconds = TF_SECONDS[args.tf]
    bars = load_bars(args.symbol, args.tf, args.data_dir)
    print(f"{args.symbol} {args.tf}: {len(bars)} bar")
    if len(bars) < 2000:
        print("FAIL: qua it bar de chia hai nua roi do.")
        return 2

    gate_timezone(bars, bar_seconds)

    first, second = split_halves(bars)
    print(f"chia 50/50: nua dau {len(first)} bar, nua sau {len(second)} bar")
    offsets = make_offsets(args.tier, bar_seconds, args.shifts, args.seed)
    if len(offsets) < args.shifts:
        print(f"  [{args.tier}] chi co {len(offsets)} moc neo kha dung "
              f"(xin {args.shifts}). Chu ky {4 * TIERS[args.tier]} s / bar "
              f"{bar_seconds} s gioi han so luoi null.")
    print()

    # Duong B: sang V2-V5 tren nua dau. KHONG tuyen bo gi tai day.
    screened = screen(first, args.tier, offsets)
    print("--- vong sang tren NUA DAU (chi de xep hang, KHONG phai bang chung) ---")
    print(screened.to_string(index=False))
    winner_b = pick_winner(screened)
    print(f"  -> bien the mang sang nua sau: {winner_b}\n")

    # Hai kiem dinh cuoi tren nua sau.
    track_a = confirm(second, args.tier, offsets, DIRECT_VARIANT)
    track_b = confirm(second, args.tier, offsets, winner_b)
    conf = pd.DataFrame([{"track": "A", **track_a}, {"track": "B", **track_b}])
    print("--- kiem dinh cuoi tren NUA SAU ---")
    print(conf.to_string(index=False))
    print()

    winner, verdict_md = verdict(track_a, track_b)
    print(verdict_md)

    out_dir = args.out_dir or (ROOT / "results" / "quarter_variants"
                               / date.today().isoformat())
    out_dir.mkdir(parents=True, exist_ok=True)
    screened.to_csv(out_dir / "screen.csv", index=False)
    conf.to_csv(out_dir / "confirm.csv", index=False)
    head = ["# Quarterly Theory - nghien cuu bien the (phase 1b)", "",
            f"- symbol: {args.symbol}  timeframe: {args.tf}  bars: {len(bars)}",
            f"- tang chinh: {args.tier}  shifts xin: {args.shifts}  "
            f"thuc te: {len(offsets)}  seed: {args.seed}",
            f"- chia 50/50: nua dau {len(first)} bar, nua sau {len(second)} bar",
            "- spec: docs/superpowers/specs/"
            "2026-09-09-quarterly-theory-variants-study-design.md", "",
            "## Vong sang tren nua dau (chi de xep hang, KHONG phai bang chung)",
            "", "```", screened.to_string(index=False), "```", "",
            "## Kiem dinh cuoi tren nua sau", "",
            "```", conf.to_string(index=False), "```", ""]
    (out_dir / "summary.md").write_text("\n".join(head) + verdict_md + "\n",
                                        encoding="utf-8")
    print(f"\nket qua: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Không dùng `to_markdown` ở bất kỳ đâu: nó đòi `tabulate`, không có trong `requirements.txt`.

- [ ] **Step 2: Smoke test hai hàm thuần của script**

Run:
```bash
python -c "
import sys; sys.path.insert(0,'scripts'); sys.path.insert(0,'.')
from study_quarter_variants import parse_args, TF_SECONDS
a = parse_args(['--tf','M15','--tier','session','--shifts','50'])
assert a.tf=='M15' and a.tier=='session' and a.shifts==50
b = parse_args([])
assert b.tf=='M5' and b.tier=='q90' and b.shifts==200 and b.seed==20260909
assert TF_SECONDS['M5']==300
print('smoke ok')
"
```
Expected: in ra `smoke ok`.

- [ ] **Step 3: Chạy cả suite**

Run: `python -m pytest -q`
Expected: **299 passed**.

- [ ] **Step 4: Commit**

```bash
git add scripts/study_quarter_variants.py
git commit -m "feat(scripts): study_quarter_variants CLI

Cong chan timezone chay truoc va thoat 1 khi fail. Chia 50/50, sang V2-V5
tren nua dau, roi hai kiem dinh cuoi tren nua sau.

Output in ro dong 'vong sang chi de xep hang, KHONG phai bang chung' de
percentile nua dau khong bi doc thanh ket luan. Phan quyet section 6 tinh
bang may.

Khong dung to_markdown vi tabulate khong co trong requirements.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: Chạy trên dữ liệu thật, README, báo số

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: toàn bộ Task 1–6
- Produces: không có

- [ ] **Step 1: Chạy nghiên cứu**

Run: `python scripts/study_quarter_variants.py --tf M5`
Expected: cổng chặn PASS, in bảng sàng nửa đầu, biến thể mang sang, hai kiểm định cuối, phán quyết §6.

Nếu chạy quá 10 phút, giảm `--shifts 50` để xem trước, rồi chạy lại đủ 200. **Kết quả báo cáo phải là lần chạy đủ**, không phải lần rút gọn.

- [ ] **Step 2: Báo số, không diễn giải quá dữ liệu**

Báo lại: mode cổng chặn; số bar mỗi nửa; **bảng sàng nửa đầu kèm nhắc rõ nó không phải bằng chứng**; biến thể được mang sang và **lý do tie-break nếu có**; hai kiểm định cuối với `real`, `percentile`, `n`, `n_nulls`, `beat_all_nulls`; và phán quyết §6 mà script đã tính.

Ba điều **phải** nói kèm, bất kể kết quả:

- **Nửa sau không trong sạch** (spec 1b §9.2). Phase 1 đã chạy trên toàn bộ 2017–2026 nên kiến thức về dấu hiệu ứng đã có trước khi Phase 1b được thiết kế. Không cái nào là out-of-sample thật.
- **Nếu đường A pass**, câu được phép nói là "chiều continuation ổn định qua hai nửa lịch sử", **không** phải "đã tìm ra edge" (spec 1b §7).
- **Nếu không đường nào pass**, kết luận là "**năm cách hình thức hoá này** không đứng trên XAUUSDc M5" — **không** phải "Quarterly Theory sai" (spec 1b §9.5). Và theo §6, không có Phase 1c.

- [ ] **Step 3: Thêm mục vào `README.md`**

Chèn ngay **sau** mục `## Quarterly Theory — nghiên cứu tiền đề` đã có:

```markdown
### Phase 1b — năm biến thể

    python scripts/study_quarter_variants.py --tf M5   # -> results/quarter_variants/<ngày>/

Phase 1 đo **một** cách hình thức hoá ý tưởng sweep-reclaim và nó thất bại. Phase 1b đo năm cách khác, với kiểm soát đa kiểm định chặt hơn: số biến thể khoá ở 5 trước khi viết code, dữ liệu chia 50/50 theo thời gian (sàng trên nửa đầu và **không tuyên bố gì tại đó**, kiểm một lần trên nửa sau), hai đường độc lập nên chỉ còn 2 kiểm định cuối với Bonferroni α = 2,5%. Tầng chính là q90 vì nó ít bị confound mốc 18:00 hơn. Ở tầng đó có 69 lưới null nên α = 2,5% đòi giá trị thật **vượt cả 69 lưới**. Spec, luật chốt trước và giới hạn: `docs/superpowers/specs/2026-09-09-quarterly-theory-variants-study-design.md`.
```

Sau khi có kết quả Step 1, thêm một câu nữa vào cuối mục đó nêu phán quyết thật, theo đúng lối mục Phase 1 đã làm.

- [ ] **Step 4: Commit**

`results/` bị `.gitignore` nên **không** `git add results/` — số liệu vào README và commit message để nằm trong version control.

Message dòng đầu cố định; phần thân **phải** chứa đủ bảy mục sau, lấy từ lần chạy đủ ở Step 1 — commit message là nơi duy nhất số liệu nằm trong version control, nên thiếu mục nào là mất mục đó vĩnh viễn:

1. Mode cổng chặn timezone (`weekly_open_mode`, `daily_gap_end_mode`).
2. Tổng số bar và số bar mỗi nửa.
3. Số lưới null thực tế dùng (nhớ tầng q90 chỉ có 69, không phải 200).
4. Bảng sàng nửa đầu: bốn biến thể với `real`, `n`, `percentile` — kèm một dòng nói rõ đây **không phải bằng chứng**.
5. Biến thể được mang sang, và **luật tie-break nào đã quyết** nếu có đồng hạng.
6. Hai kiểm định cuối: mỗi đường một dòng với `variant`, `real`, `percentile`, `n`, `n_nulls`, `beat_all_nulls`.
7. Phán quyết §6 mà `verdict()` đã tính, nguyên văn dòng kết luận của nó.

```bash
git add README.md
git commit -F - <<'MSG'
study: chay Phase 1b nam bien the tren XAUUSDc M5

<bay muc tren, moi muc mot doan>

Ket qua tho o results/quarter_variants/ (results/ bi gitignore nen so lieu
duoc ghi vao commit message nay va vao README).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
```

---

## Self-review: đối chiếu plan với spec

| Mục spec 1b | Task |
|---|---|
| §1.1 Câu hỏi, số Phase 1 để đối chiếu | Global Constraints |
| §1.2 Không vi phạm §7 Phase 1 (chỉ đo, không sinh `Signal`) | Global Constraints; không task nào nạp engine |
| §1.3 Nguy cơ p-hacking, số biến thể khoá ở 5 | Global Constraints; 3, 4 (đúng 5 biến thể, không hơn) |
| §2 Trigger chung | 2 |
| §2 Năm biến thể | 3 (V1, V3, V4, V5), 4 (V2) |
| §2 V2 không lookahead, `<` chặt | 4 (test `shift(1)` riêng) |
| §2 V3 giữ luật loại `both` | 3 (`test_v3_keeps_the_both_sided_exclusion`) |
| §2 Hoà theo từng biến thể | 2 (`pooled`), 3 (V3 trung điểm, V5 True Open), 4 (V2 median) |
| §3 Chia 50/50, bar dư nửa sau | 5 (`split_halves`) |
| §4 Hai đường, sàng không tuyên bố | 5 (`screen`, `DIRECT_VARIANT not in SCREEN_VARIANTS`) |
| §4 Sàng xếp hạng theo q90 | 5 (`screen` nhận `tier`), 6 (CLI truyền `--tier`, mặc định `PRIMARY_TIER`) |
| §4 Tie-break | 5 (`pick_winner`, ba test) |
| §5 Tầng chính q90; session chỉ mô tả | 5 (`PRIMARY_TIER`), 6 (`--tier` mặc định q90) |
| §5 Ngưỡng "vượt cả 69 null", không phải percentile 95 | 5 (`beat_all_nulls` + test khẳng định percentile 96 không đủ) |
| §6 Luật chốt trước, tính bằng máy | 5 (`verdict`), 6 (in ra) |
| §6 Không pass ⇒ đóng lại, không Phase 1c | 5 (test văn bản), 7 Step 2 |
| §7 Điều đường A không chứng minh được | 3 (docstring V1 + `test_v1_is_exactly_one_minus_the_reversal_measure`), 5 (`verdict` in câu này), 7 Step 2 |
| §8 File, `stats` param giữ hành vi Phase 1 | 1 (test khẳng định) |
| §9 Giới hạn | 7 Step 2 (bắt buộc báo kèm) |

Không có mục spec nào thiếu task.

**Tên dùng xuyên plan, kiểm nhất quán:**
`_mean_or_nan` `base_trigger` `q3_dir` `pooled` · `variant_v1` `variant_v2` `variant_v3` `variant_v4` `variant_v5` · `TRAILING_WINDOW` `trailing_tight` · `VARIANTS` `DIRECT_VARIANT` `SCREEN_VARIANTS` `TIE_BREAK` `PRIMARY_TIER` · `split_halves` `screen` `pick_winner` `confirm` `verdict` · `TF_SECONDS` `parse_args` `load_bars` `gate_timezone` `main` · từ Phase 1: `run_grid` `run_null` `percentile_of` `make_offsets` `MIN_BARS_PER_QUARTER` `aggregate_cycles` `label_quarters` `verify_server_tz` `TIERS` `STATS`

Mọi biến thể trả về đúng bốn khoá `p` / `n` / `n_up` / `n_dn`, nên `screen` và `confirm` đọc `f"{name}.p"` và `f"{name}.n"` được cho cả năm.
