# Quarterly Theory Premise Study (Phase 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đo xem lưới thời gian của Quarterly Theory có cấu trúc thật trên XAUUSDc hay chỉ là hình học của việc chia một chuỗi giá thành bốn phần — bằng sáu phép đo, mỗi phép so với 200 lưới neo lệch.

**Architecture:** Ba lớp tách rời. `rsi_fvg/quarters.py` lo thời gian: convert đồng hồ server sang giờ New York và gán nhãn quarter. `rsi_fvg/quarter_stats.py` lo phép đo: gộp bar thành bảng chu kỳ, sáu thống kê, và bộ máy permutation. `scripts/study_quarters.py` chỉ lo I/O và CLI. Mọi thứ trong hai module đầu là hàm thuần, không state, không I/O — nên test được thật.

**Tech Stack:** Python 3.13, numpy ≥ 2.0, pandas ≥ 2.2, pytest ≥ 8.0. **Không thêm dependency nào** — không scipy; Spearman lấy từ `pandas.Series.corr(method="spearman")`, p-value lấy từ chính phân phối permutation.

**Spec:** `docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md`

**Branch:** `feat/quarterly-premise-study` (nhánh từ `fcdc655`, tip của `feat/python-backtest`)

---

## Ba chỗ plan này đi khác spec — đọc trước

**1. Năm file, không phải ba.** Spec §Phạm vi liệt kê ba file. Plan tách thêm `rsi_fvg/quarter_stats.py` và `tests/test_quarter_stats.py`. Lý do: sáu thống kê là phần **substance** của nghiên cứu và định nghĩa của ⑥ rất dễ cài sai; nếu chúng nằm trong `scripts/` thì theo quy ước repo chúng sẽ không được test. Danh sách ba file của spec là một phát biểu về **phạm vi** (không chạm engine), không phải một ràng buộc về cách chia module bên trong. Phạm vi thật vẫn giữ nguyên: không sửa `rsi_fvg/backtest/`, `strategies/`, `params.py`, `config/`.

**2. Cột đặt tên theo số quarter của lý thuyết, không theo chỉ số 0.** `q_index` chạy 0..3 nhưng lý thuyết gọi chúng Q1..Q4. Bảng chu kỳ dùng cột `q1_*`..`q4_*` với **`q1` = Q1 của lý thuyết = `q_index` 0**. Nếu để `q0_*` thì mọi công thức sẽ đọc lệch một bậc so với spec và đó là chỗ bug sẽ trốn.

**3. Chu kỳ sweep CẢ HAI phía — spec không nói, plan chốt.** Q2 có thể vượt cả high lẫn low của range Q1 rồi đóng lại bên trong. Khi đó lý thuyết **không** đưa ra kỳ vọng hướng nào. Luật: **loại khỏi cả ba thống kê của ⑥**, và báo số lượng. Đưa vào pooled sẽ đếm một chu kỳ hai lần với hai kỳ vọng trái nhau.

---

## Global Constraints

Áp dụng cho mọi task, không nhắc lại:

- Python 3.13. `from __future__ import annotations` ở đầu mỗi module mới.
- **Không thêm dependency.** Chỉ numpy, pandas, pytest — đều đã có trong `requirements.txt`.
- Code thư viện vào `rsi_fvg/`, CLI vào `scripts/` theo đúng idiom repo: `ROOT = Path(__file__).resolve().parents[1]`, `sys.path.insert(0, str(ROOT))`, rồi import với `# noqa: E402`.
- Test vào `tests/`, hàm `pytest` phẳng, không class. Chạy bằng `python -m pytest -q`.
- **Không sửa** `rsi_fvg/backtest/`, `rsi_fvg/strategies/`, `rsi_fvg/params.py`, `rsi_fvg/signals.py`, `config/`. Nghiên cứu này không tạo `Signal` nào và không nạp engine.
- Docstring và comment viết **tiếng Việt**, theo đúng lối `rsi_fvg/strategies/rsi2_ema_swing.py` đang dùng: nói *tại sao*, trỏ về mục spec, ghi rõ chỗ nào là quyết định có ý thức.
- `SERVER_TZ = "Europe/Athens"`, `NY_TZ = "America/New_York"` — hằng số module, không rải chuỗi literal.
- Quarter của lý thuyết đánh số **1..4**; `q_index` nội bộ là 0..3. Cột bảng dùng `q1_`..`q4_`.
- Commit sau mỗi task, message tiếng Anh không dấu, kết bằng `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

**Bảng hằng số:**

| Tên | Giá trị | Nghĩa |
|---|---|---|
| `TIERS["session"]` | `21600` | quarter tầng session = 6 giờ |
| `TIERS["q90"]` | `5400` | quarter tầng 90 phút |
| `WEEK_GAP_SECONDS` | `86400` | khe lớn hơn mức này tính là khe cuối tuần |
| `MIN_BARS_PER_QUARTER` | `3` | dưới mức này thì loại cả chu kỳ (spec §4.2) |
| `OFFSET_EXCLUDE` | `600` | loại lân cận 0 khi sinh offset null (spec §4.1) |
| `VERDICT_THRESHOLD` | `95.0` | percentile mở cổng Phase 2 (spec §7) |

**Offset server→NY** (đã kiểm bằng `zoneinfo` trên cả năm 2026): chỉ tồn tại **7 giờ** (337 ngày) và **6 giờ** (28 ngày, 08/03→31/10). **Không tồn tại 8 giờ** — xem spec §2. Test nào assert 8 là test sai.

---

## File Structure

- **Create `rsi_fvg/quarters.py`** — lớp thời gian. Trách nhiệm duy nhất: từ epoch seconds ra giờ New York đúng, và từ giờ New York ra nhãn quarter. Không biết gì về thống kê. Phase 2 dùng lại nguyên vẹn.
- **Create `rsi_fvg/quarter_stats.py`** — lớp phép đo. Gộp bar thành bảng chu kỳ, sáu thống kê, sinh offset, chạy permutation. Không biết gì về file hay CLI.
- **Create `scripts/study_quarters.py`** — CLI. Nạp parquet, gọi cổng chặn, chạy permutation, ghi `stats.csv` + `summary.md`, in phán quyết §7.
- **Create `tests/test_quarters.py`** — Task 1, 2.
- **Create `tests/test_quarter_stats.py`** — Task 3–7.
- **Modify `tests/conftest.py`** — thêm helper `epoch_for_ny` (Task 1); giữ nguyên `make_bars` / `bars_from_closes` / fixtures đang có.
- **Modify `README.md`** — Task 9, một mục ngắn.

**Một lợi thế của cách chia này, dùng nó khi viết test:** sáu thống kê nhận vào một `DataFrame` bảng chu kỳ, nên test của Task 4–6 chỉ cần **dựng DataFrame bằng tay** — không cần bar, không cần số học thời gian. Chỉ Task 3 cần bar thật.

---

## Task 1: Lớp timezone — `server_to_ny` và cổng chặn `verify_server_tz`

**Files:**
- Create: `rsi_fvg/quarters.py`
- Create: `tests/test_quarters.py`
- Modify: `tests/conftest.py` (thêm `epoch_for_ny` và fixture `mk_epoch_ny`)

**Interfaces:**
- Consumes: `rsi_fvg.bars.Bars` (chỉ dùng `.time`)
- Produces:
  - `SERVER_TZ = "Europe/Athens"`, `NY_TZ = "America/New_York"`
  - `WEEK_GAP_SECONDS = 86400`
  - `server_to_ny(epoch: np.ndarray) -> pd.DatetimeIndex` (tz-aware, NY)
  - `TzCheck` dataclass: `weekly_open_mode: str`, `weekly_open_counts: dict[str, int]`, `daily_gap_end_mode: str`, `daily_gap_end_counts: dict[str, int]`, `weekly_ok: bool`, `daily_ok: bool`, `ok: bool`, `notes: tuple[str, ...]`
  - `verify_server_tz(time: np.ndarray, bar_seconds: int) -> TzCheck`
  - trong conftest: `epoch_for_ny(y, m, d, hh, mm=0, ss=0) -> int`

- [ ] **Step 1: Thêm helper `epoch_for_ny` vào `tests/conftest.py`**

Chèn sau `bars_from_closes`, trước khối fixture. Helper này là nền của mọi test thời gian: nó dựng đúng loại epoch mà loader sinh ra — giờ treo tường của server được gán nhãn UTC.

```python
def epoch_for_ny(y, m, d, hh, mm=0, ss=0):
    """Epoch seconds mà server_to_ny sẽ đọc thành đúng giờ New York này.

    Loader gán nhãn giờ treo tường của server là UTC (README, "Timestamps").
    Nên đường đi ngược là: giờ NY -> giờ treo tường Athens -> bỏ tz -> coi như UTC.
    """
    ny = pd.Timestamp(year=y, month=m, day=d, hour=hh, minute=mm, second=ss,
                      tz="America/New_York")
    server_wall = ny.tz_convert("Europe/Athens").tz_localize(None)
    return int(server_wall.value // 1_000_000_000)


@pytest.fixture
def mk_epoch_ny():
    return epoch_for_ny
```

`tests/conftest.py` hiện chưa import pandas. Thêm `import pandas as pd` vào khối import ở đầu file, cạnh `import numpy as np`.

- [ ] **Step 2: Viết test đỏ cho `server_to_ny`**

Thêm vào `tests/test_quarters.py` (file mới):

```python
import numpy as np
import pandas as pd
import pytest

from conftest import epoch_for_ny
from rsi_fvg.quarters import NY_TZ, TzCheck, server_to_ny, verify_server_tz


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
```

- [ ] **Step 3: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarters.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'rsi_fvg.quarters'`

- [ ] **Step 4: Viết `rsi_fvg/quarters.py` phần `server_to_ny`**

```python
"""Gán nhãn quarter của Quarterly Theory theo giờ New York.

Spec: docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md §3.

Bars.time là đồng hồ server của broker được gán nhãn UTC mà KHÔNG convert
(README, mục "Timestamps"). Exness chạy EET/EEST. Với RSI2 và RSI-FVG việc gán
nhãn sai này vô hại vì không có gì trong backtest phụ thuộc giờ treo tường; với
Quarterly Theory thì mọi biên quarter LÀ một mốc giờ New York, nên lệch một giờ
là đo một lý thuyết khác.

Offset server->NY chỉ nhận hai giá trị: 7 giờ (bình thường) và 6 giờ (~28 ngày
mỗi năm, khi Mỹ đã vào DST mà EU chưa, hoặc EU đã ra mà Mỹ chưa). Không tồn tại
8 giờ — giai đoạn DST của EU nằm hoàn toàn bên trong giai đoạn của Mỹ.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SERVER_TZ = "Europe/Athens"      # EET/EEST, khớp ghi chú README về đồng hồ Exness
NY_TZ = "America/New_York"
WEEK_GAP_SECONDS = 86400


def server_to_ny(epoch: np.ndarray) -> pd.DatetimeIndex:
    """epoch seconds (giờ server gán nhãn UTC) -> DatetimeIndex tz-aware giờ NY.

    ambiguous="raise" và nonexistent="raise" là CÓ Ý, không phải mặc định bỏ quên:
    DST của EU đổi lúc 03:00 Chủ nhật, giữa lúc thị trường đóng, nên lẽ ra không
    bar nào rơi vào giờ lặp hay giờ mất. Nếu nó raise thật thì đó là phát hiện về
    dữ liệu cần điều tra, không phải lỗi cần bọc try — bọc lại sẽ che đúng thứ
    đáng biết.
    """
    naive = pd.to_datetime(np.asarray(epoch, dtype="int64"), unit="s")
    return naive.tz_localize(SERVER_TZ, ambiguous="raise",
                             nonexistent="raise").tz_convert(NY_TZ)
```

- [ ] **Step 5: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarters.py -q`
Expected: PASS — 6 test (4 tham số + 2 test đơn).

- [ ] **Step 6: Viết test đỏ cho `verify_server_tz`**

Thêm vào `tests/test_quarters.py`:

**Chú ý về dữ liệu tổng hợp:** chuỗi phải chứa **ít nhất một khe cuối tuần**, nếu không `verify_server_tz` trả về sớm với `ok=False` và test sẽ fail vì lý do sai. Nên hai helper dưới đây đều dựng **ba tuần**. `2026-06-07`, `-14`, `-21` đều là Chủ nhật — đã kiểm.

```python
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
```

- [ ] **Step 7: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarters.py -q -k verify`
Expected: FAIL — `ImportError: cannot import name 'verify_server_tz'`

- [ ] **Step 8: Cài `TzCheck` và `verify_server_tz`**

Thêm vào cuối `rsi_fvg/quarters.py`:

```python
# Nhãn thứ trong tuần tự viết, KHÔNG dùng strftime("%a"): %a phụ thuộc locale của
# máy và repo này chạy trên Windows tiếng Việt.
DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# Vàng/forex mở Chủ nhật 17:00-18:00 NY; khe nghỉ hằng ngày của Exness
# (00:00-01:00 EET) kết thúc trong cùng cửa sổ đó tính theo giờ NY.
WEEKLY_OPEN_OK = ("Sun 17:00", "Sun 17:30", "Sun 18:00")
DAILY_GAP_END_OK = ("17:00", "17:30", "18:00")


@dataclass(frozen=True)
class TzCheck:
    weekly_open_mode: str
    weekly_open_counts: dict[str, int]
    daily_gap_end_mode: str
    daily_gap_end_counts: dict[str, int]
    weekly_ok: bool
    daily_ok: bool
    ok: bool
    notes: tuple[str, ...]


def verify_server_tz(time: np.ndarray, bar_seconds: int) -> TzCheck:
    """Kiểm giả định "đồng hồ server = EET" bằng dữ liệu, không bằng niềm tin.

    Kiểm định 1 (CHẶN): giờ NY của bar đầu tiên sau mỗi khe cuối tuần. Thị trường
    mở Chủ nhật 17:00-18:00 NY, nên mode phải nằm trong cửa sổ đó.

    Kiểm định 2 (BỔ TRỢ): giờ NY của bar đầu tiên sau mỗi khe trong ngày. Khe nghỉ
    hằng ngày của Exness kết thúc 01:00 EET = 18:00 NY. Kiểm định này KHÔNG chặn
    một mình khi không có khe nào — tài khoản có thể không có phiên nghỉ, và chặn
    oan sẽ khoá cả nghiên cứu vì một thứ chỉ mang tính xác nhận.

    Ghi chú cho spec §8.2: khe nghỉ kết thúc đúng 18:00 NY, trùng mốc neo chu kỳ
    ngày. Vừa là kiểm định tốt, vừa là confound.
    """
    t = np.asarray(time, dtype="int64")
    notes: list[str] = []
    if t.size < 2:
        return TzCheck("", {}, "", {}, False, False, False, ("chuoi qua ngan",))

    ny = server_to_ny(t)
    d = np.diff(t)
    after = np.flatnonzero(d > bar_seconds) + 1        # bar ngay SAU mỗi khe
    if after.size == 0:
        return TzCheck("", {}, "", {}, False, False, False,
                       ("khong tim thay khe nao trong chuoi",))

    gap = d[after - 1]
    weekly_idx = after[gap > WEEK_GAP_SECONDS]
    daily_idx = after[gap <= WEEK_GAP_SECONDS]

    def labels(idx: np.ndarray, with_dow: bool) -> dict[str, int]:
        if idx.size == 0:
            return {}
        sub = ny[idx]
        out: list[str] = []
        for dw, hh, mm in zip(sub.dayofweek, sub.hour, sub.minute):
            stamp = f"{hh:02d}:{mm:02d}"
            out.append(f"{DOW[dw]} {stamp}" if with_dow else stamp)
        vc = pd.Series(out).value_counts()
        return {str(k): int(v) for k, v in vc.items()}

    w_counts = labels(weekly_idx, True)
    d_counts = labels(daily_idx, False)
    w_mode = next(iter(w_counts), "")
    d_mode = next(iter(d_counts), "")

    weekly_ok = w_mode in WEEKLY_OPEN_OK
    daily_ok = (d_mode == "") or (d_mode in DAILY_GAP_END_OK)
    if not weekly_ok:
        notes.append(f"mo dau tuan mode={w_mode!r}, ngoai cua so {WEEKLY_OPEN_OK}")
    if d_mode == "":
        notes.append("khong co khe trong ngay: kiem dinh 2 pass rong")
    elif not daily_ok:
        notes.append(f"ket khe hang ngay mode={d_mode!r}, ngoai cua so {DAILY_GAP_END_OK}")
    return TzCheck(w_mode, w_counts, d_mode, d_counts,
                   weekly_ok, daily_ok, weekly_ok and daily_ok, tuple(notes))
```

`value_counts()` trả về theo thứ tự giảm dần, nên `next(iter(...))` là mode. Khi có hai nhãn đồng hạng thì pandas chọn một cách xác định — chấp nhận được vì `weekly_open_counts` luôn được báo ra để người đọc thấy phân phối.

- [ ] **Step 9: Chạy toàn bộ test file, xác nhận xanh**

Run: `python -m pytest tests/test_quarters.py -q`
Expected: PASS — 10 test.

- [ ] **Step 10: Chạy cả suite để chắc không phá gì**

Run: `python -m pytest -q`
Expected: toàn bộ PASS (test MT5 tự skip khi terminal không chạy).

- [ ] **Step 11: Commit**

```bash
git add rsi_fvg/quarters.py tests/test_quarters.py tests/conftest.py
git commit -m "feat(quarters): server->NY conversion va cong chan verify_server_tz

Loader gan nhan gio server la UTC khong convert. Voi RSI2/RSI-FVG vo hai,
voi Quarterly Theory thi moi bien quarter la mot moc gio NY nen phai
convert dung. ambiguous/nonexistent = raise co y: DST cua EU doi luc
03:00 CN khi thi truong dong, raise nghia la phat hien ve du lieu.

verify_server_tz kiem gia dinh EET bang du lieu: khe cuoi tuan phai mo
CN 17:00-18:00 NY (chan), khe nghi hang ngay phai ket 17:00-18:00 NY
(bo tro, pass rong khi khong co khe de khong chan oan).

Test khang dinh offset chi nhan 6 hoac 7 tren ca nam 2026, khong bao gio 8.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: `label_quarters` — gán nhãn hai tầng

Đây là task rủi ro nhất của cả plan. `trading_day` qua nửa đêm và số học DST là hai chỗ dễ sai mà không lộ ra.

**Files:**
- Modify: `rsi_fvg/quarters.py` (thêm vào cuối)
- Modify: `tests/test_quarters.py` (thêm vào cuối)

**Interfaces:**
- Consumes: `server_to_ny`, `NY_TZ` (Task 1); `epoch_for_ny` (conftest)
- Produces:
  - `TIERS: dict[str, int] = {"session": 21600, "q90": 5400}`
  - `QuarterLabels` dataclass: `ny: pd.DatetimeIndex`, `trading_day: pd.DatetimeIndex` (naive), `i_sess: np.ndarray`, `i_q90: np.ndarray`, `cycle_id: np.ndarray` (int64), `q_index: np.ndarray` (int64, 0..3)
  - `label_quarters(time: np.ndarray, tier: str, anchor_offset: int = 0) -> QuarterLabels`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `tests/test_quarters.py`:

```python
from rsi_fvg.quarters import TIERS, label_quarters


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
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarters.py -q -k "label or trading or cycle or anchor"`
Expected: FAIL — `ImportError: cannot import name 'TIERS'`

- [ ] **Step 3: Cài `label_quarters`**

Thêm vào cuối `rsi_fvg/quarters.py`:

```python
TIERS: dict[str, int] = {"session": 21600, "q90": 5400}
NS_PER_DAY = 24 * 3600 * 1_000_000_000


@dataclass(frozen=True)
class QuarterLabels:
    ny: pd.DatetimeIndex          # tz-aware, giờ New York
    trading_day: pd.DatetimeIndex  # naive, nửa đêm NY của ngày mở 18:00
    i_sess: np.ndarray            # 0..3 — Asia / London / NY-AM / NY-PM
    i_q90: np.ndarray             # 0..3 — block 90 phút trong session
    cycle_id: np.ndarray          # int64, một giá trị mỗi chu kỳ của tier
    q_index: np.ndarray           # int64 0..3 — quarter của tier (Q1 lý thuyết = 0)


def label_quarters(time: np.ndarray, tier: str,
                   anchor_offset: int = 0) -> QuarterLabels:
    """Gán nhãn quarter theo giờ New York. Cùng số học với indicator Pine.

    Xem pine/quarterly_theory_ict.pine: hShift = (hour + 6) % 24 dịch 18:00 NY về 0,
    nên chu kỳ ngày chạy 18:00 -> 18:00.

    `anchor_offset` (giây) dịch cả lưới và tồn tại CHỈ để mô hình null dùng
    (spec §4.1). Đây là lý do hàm nhận tham số thay vì hardcode mốc neo.

    `trading_day` tính bằng số học LỊCH trên giờ treo tường naive, không bằng số
    giây tích luỹ: trừ một ngày trên timestamp tz-aware là trừ 24 giờ tuyệt đối,
    và qua biên DST của New York điều đó cho ra 23:00 hoặc 01:00 thay vì nửa đêm.
    """
    if tier not in TIERS:
        raise ValueError(f"tier phai la mot trong {sorted(TIERS)}, nhan {tier!r}")

    ny = server_to_ny(time)
    if anchor_offset:
        ny = ny - pd.Timedelta(seconds=int(anchor_offset))

    naive = ny.tz_localize(None)
    hour = naive.hour.to_numpy()
    h_shift = (hour + 6) % 24
    i_sess = (h_shift // 6).astype("int64")
    sec_in_sess = ((h_shift % 6) * 3600
                   + naive.minute.to_numpy() * 60
                   + naive.second.to_numpy())
    i_q90 = (sec_in_sess // 5400).astype("int64")

    back_a_day = pd.to_timedelta((hour < 18).astype("int64"), unit="D")
    trading_day = naive.normalize() - back_a_day
    day_num = (trading_day.asi8 // NS_PER_DAY).astype("int64")

    if tier == "session":
        cycle_id, q_index = day_num, i_sess
    else:
        cycle_id, q_index = day_num * 4 + i_sess, i_q90

    return QuarterLabels(ny=ny, trading_day=trading_day, i_sess=i_sess,
                         i_q90=i_q90, cycle_id=cycle_id.astype("int64"),
                         q_index=q_index.astype("int64"))
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarters.py -q`
Expected: PASS — 27 test (10 của Task 1 + 11 tham số bảng biên + 6 test đơn).

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/quarters.py tests/test_quarters.py
git commit -m "feat(quarters): label_quarters cho tang session va q90

Cung so hoc voi indicator Pine: hShift = (hour+6)%24 dich 18:00 NY ve 0
nen chu ky ngay chay 18:00->18:00. cycle_id tang session la so ngay giao
dich, tang q90 la day_num*4 + i_sess.

trading_day tinh bang so hoc LICH tren gio treo tuong naive chu khong
tru 24 gio tuyet doi tren timestamp tz-aware: qua bien DST cua New York
phep tru tuyet doi cho ra 23:00 hoac 01:00 thay vi nua dem.

anchor_offset ton tai chi de mo hinh null dung (spec 4.1).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: `aggregate_cycles` — bảng chu kỳ, và luật loại chu kỳ thiếu bar

**Files:**
- Create: `rsi_fvg/quarter_stats.py`
- Create: `tests/test_quarter_stats.py`

**Interfaces:**
- Consumes: `rsi_fvg.quarters.label_quarters`, `QuarterLabels`, `TIERS`; `rsi_fvg.bars.Bars`; `epoch_for_ny` (conftest)
- Produces:
  - `MIN_BARS_PER_QUARTER = 3`
  - `aggregate_cycles(bars: Bars, labels: QuarterLabels, min_bars: int = MIN_BARS_PER_QUARTER) -> pd.DataFrame` — index `cycle_id`, cột `q1_open q1_high q1_low q1_close q1_n` … `q4_*`. **`q1` = Q1 của lý thuyết = `q_index` 0.**

- [ ] **Step 1: Viết test đỏ**

Tạo `tests/test_quarter_stats.py`:

```python
import numpy as np
import pandas as pd
import pytest

from conftest import epoch_for_ny, make_bars
from rsi_fvg.quarter_stats import MIN_BARS_PER_QUARTER, aggregate_cycles
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
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarter_stats.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'rsi_fvg.quarter_stats'`

- [ ] **Step 3: Cài `aggregate_cycles`**

Tạo `rsi_fvg/quarter_stats.py`:

```python
"""Sáu phép đo tiền đề của Quarterly Theory, cộng bộ máy permutation.

Spec: docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md §4.

Mọi thống kê nhận vào BẢNG CHU KỲ (một dòng mỗi chu kỳ, cột q1_*..q4_*) và trả
về dict tên->số, để bộ chạy permutation so lưới thật với lưới null một cách đồng
nhất mà không cần biết thống kê đó đo gì.

Đánh số: cột `q1_` là Q1 CỦA LÝ THUYẾT, tức `q_index` 0. Nếu đặt `q0_` thì mọi
công thức sẽ đọc lệch một bậc so với spec.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .bars import Bars
from .quarters import QuarterLabels

MIN_BARS_PER_QUARTER = 3
_FIELDS = ("open", "high", "low", "close", "n")


def aggregate_cycles(bars: Bars, labels: QuarterLabels,
                     min_bars: int = MIN_BARS_PER_QUARTER) -> pd.DataFrame:
    """Gộp bar thành một dòng mỗi chu kỳ với OHLC của cả bốn quarter.

    Loại CẢ chu kỳ nếu bất kỳ quarter nào thiếu hoặc có ít hơn `min_bars` bar
    (spec §4.2). Luật này phải áp y nguyên cho lưới thật và mọi lưới null — chỉ
    áp một bên thì cỡ mẫu lệch và phép so sánh vô nghĩa.

    `first`/`last` cho open/close là đúng vì `bars` theo thứ tự thời gian và
    groupby giữ thứ tự trong nhóm.
    """
    df = pd.DataFrame({
        "cycle_id": labels.cycle_id,
        "q": labels.q_index,
        "open": bars.open, "high": bars.high,
        "low": bars.low, "close": bars.close,
    })
    agg = df.groupby(["cycle_id", "q"], sort=True).agg(
        open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last"), n=("close", "size"),
    )
    wide = agg.unstack("q")
    wide.columns = [f"q{int(q) + 1}_{field}" for field, q in wide.columns]
    wide = wide.reindex(columns=[f"q{q}_{f}" for q in (1, 2, 3, 4) for f in _FIELDS])

    keep = np.ones(len(wide), dtype=bool)
    for q in (1, 2, 3, 4):
        n = wide[f"q{q}_n"].to_numpy(dtype="float64")
        keep &= np.isfinite(n) & (n >= min_bars)
    return wide.loc[keep]
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarter_stats.py -q`
Expected: PASS — 5 test.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/quarter_stats.py tests/test_quarter_stats.py
git commit -m "feat(quarter_stats): aggregate_cycles + luat loai chu ky thieu bar

Mot dong moi chu ky, cot q1_*..q4_* voi q1 = Q1 CUA LY THUYET (q_index 0).
Dat q0_ se lam moi cong thuc doc lech mot bac so voi spec.

Loai ca chu ky khi bat ky quarter nao thieu hoac co it hon 3 bar (spec
4.2). Luat ap y nguyen cho luoi that va moi luoi null - chi ap mot ben
thi co mau lech va phep so sanh vo nghia.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Phép đo ① ② ③ — sweep, range theo quarter, displacement theo quarter

Từ task này trở đi, test chỉ cần **dựng DataFrame bằng tay** — không cần bar, không cần số học thời gian.

**Files:**
- Modify: `rsi_fvg/quarter_stats.py`
- Modify: `tests/test_quarter_stats.py`

**Interfaces:**
- Consumes: bảng chu kỳ của Task 3
- Produces:
  - `stat_sweep(w) -> dict[str, float]` — khoá `sweep_rate`, `n`
  - `stat_range_by_index(w) -> dict[str, float]` — khoá `range_q1`..`range_q4`, `range_q1_ratio`, `n`
  - `stat_displacement_by_index(w) -> dict[str, float]` — khoá `disp_q1`..`disp_q4`, `disp_q3_ratio`, `n`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `tests/test_quarter_stats.py`:

```python
from rsi_fvg.quarter_stats import (stat_displacement_by_index, stat_range_by_index,
                                   stat_sweep)


def _wide(rows: list[dict]) -> pd.DataFrame:
    """Bảng chu kỳ dựng tay. Thiếu cột nào thì điền giá trị trung tính."""
    base = {}
    for q in (1, 2, 3, 4):
        base |= {f"q{q}_open": 100.0, f"q{q}_high": 101.0,
                 f"q{q}_low": 99.0, f"q{q}_close": 100.0, f"q{q}_n": 10.0}
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
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarter_stats.py -q -k "sweep or range_by or displacement or empty"`
Expected: FAIL — `ImportError: cannot import name 'stat_sweep'`

- [ ] **Step 3: Cài ba thống kê**

Thêm vào `rsi_fvg/quarter_stats.py`:

```python
QUARTERS = (1, 2, 3, 4)


def _mean_or_nan(x: np.ndarray) -> float:
    return float(np.mean(x)) if x.size else float("nan")


def stat_sweep(w: pd.DataFrame) -> dict[str, float]:
    """① Tỷ lệ chu kỳ mà Q2 vượt ra ngoài range của Q1 (Defining Range).

    So sánh là > và <, không phải >= và <=: chạm đúng biên không phải sweep.
    """
    up = w["q2_high"].to_numpy() > w["q1_high"].to_numpy()
    dn = w["q2_low"].to_numpy() < w["q1_low"].to_numpy()
    return {"sweep_rate": _mean_or_nan(up | dn), "n": float(len(w))}


def stat_range_by_index(w: pd.DataFrame) -> dict[str, float]:
    """② Range trung bình theo chỉ số quarter. Lý thuyết nói Q1 nhỏ nhất."""
    out: dict[str, float] = {}
    for q in QUARTERS:
        r = (w[f"q{q}_high"] - w[f"q{q}_low"]).to_numpy()
        out[f"range_q{q}"] = _mean_or_nan(r)
    mean_all = float(np.mean([out[f"range_q{q}"] for q in QUARTERS]))
    out["range_q1_ratio"] = (out["range_q1"] / mean_all
                             if mean_all and np.isfinite(mean_all) else float("nan"))
    out["n"] = float(len(w))
    return out


def stat_displacement_by_index(w: pd.DataFrame) -> dict[str, float]:
    """③ |close - open| trung bình theo chỉ số quarter. Lý thuyết nói Q3 lớn nhất."""
    out: dict[str, float] = {}
    for q in QUARTERS:
        d = np.abs((w[f"q{q}_close"] - w[f"q{q}_open"]).to_numpy())
        out[f"disp_q{q}"] = _mean_or_nan(d)
    mean_all = float(np.mean([out[f"disp_q{q}"] for q in QUARTERS]))
    out["disp_q3_ratio"] = (out["disp_q3"] / mean_all
                            if mean_all and np.isfinite(mean_all) else float("nan"))
    out["n"] = float(len(w))
    return out
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarter_stats.py -q`
Expected: PASS — 10 test.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/quarter_stats.py tests/test_quarter_stats.py
git commit -m "feat(quarter_stats): phep do 1, 2, 3 - sweep va range/displacement theo quarter

Sweep dung > va < chu khong >= <=: cham dung bien khong phai sweep.
Bang rong tra NaN thay vi crash, vi luoi null co the loai het chu ky.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: Phép đo ④ ⑤ — Q1 dự báo Q2, và True Open

**Files:**
- Modify: `rsi_fvg/quarter_stats.py`
- Modify: `tests/test_quarter_stats.py`

**Interfaces:**
- Consumes: bảng chu kỳ của Task 3
- Produces:
  - `stat_q1_predicts_q2(w) -> dict[str, float]` — khoá `spearman_r1_r2`, `n`
  - `stat_true_open(w) -> dict[str, float]` — khoá `true_open_persistence`, `n`, `ties`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `tests/test_quarter_stats.py`:

```python
from rsi_fvg.quarter_stats import stat_q1_predicts_q2, stat_true_open


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
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarter_stats.py -q -k "spearman or true_open"`
Expected: FAIL — `ImportError: cannot import name 'stat_q1_predicts_q2'`

- [ ] **Step 3: Cài hai thống kê**

Thêm vào `rsi_fvg/quarter_stats.py`:

```python
def stat_q1_predicts_q2(w: pd.DataFrame) -> dict[str, float]:
    """④ Spearman(range Q1, range Q2). Lý thuyết dự đoán ÂM.

    "Q1 dictates the quarters which follow": Q1 hẹp báo Q2 giãn, Q1 đã giãn báo
    Q2 co. Dùng Spearman chứ không Pearson vì range có đuôi dày và ta chỉ quan
    tâm quan hệ đơn điệu. `pandas.Series.corr` có sẵn method này, không cần scipy.
    """
    if len(w) < 2:
        return {"spearman_r1_r2": float("nan"), "n": float(len(w))}
    r1 = w["q1_high"] - w["q1_low"]
    r2 = w["q2_high"] - w["q2_low"]
    rho = r1.corr(r2, method="spearman")
    return {"spearman_r1_r2": float(rho), "n": float(len(w))}


def stat_true_open(w: pd.DataFrame) -> dict[str, float]:
    """⑤ True Open = open của bar đầu Q2 (spec §2.4 của spec indicator).

    Đo P(cuối chu kỳ cùng phía True Open với lúc bắt đầu Q3). Trên 0.5 là dấu
    hiệu bền hướng, dưới 0.5 là hồi quy về trung bình — lệch khỏi 0.5 theo hướng
    nào cũng là thông tin.

    Hoà (giá bằng đúng True Open) bị LOẠI, không gán về một phía (spec §4.2).
    """
    to = w["q2_open"].to_numpy()
    a = w["q3_open"].to_numpy() - to
    b = w["q4_close"].to_numpy() - to
    keep = (a != 0) & (b != 0)
    same = np.sign(a[keep]) == np.sign(b[keep])
    return {"true_open_persistence": _mean_or_nan(same),
            "n": float(keep.sum()), "ties": float((~keep).sum())}
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarter_stats.py -q`
Expected: PASS — 15 test.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/quarter_stats.py tests/test_quarter_stats.py
git commit -m "feat(quarter_stats): phep do 4 va 5 - Spearman Q1/Q2 va True Open

Spearman thay Pearson vi range co duoi day va ta chi quan tam quan he don
dieu. pandas.Series.corr co san method spearman, khong can scipy.

True Open: hoa bi LOAI chu khong gan ve mot phia (spec 4.2). np.sign(0)
la 0 nen neu khong loai thi hoa se roi vao nhanh 'khac phia' mot cach
tuy y.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: Phép đo ⑥ — sweep rồi reclaim, Q3 có đi ngược không

Đây là phép đo **quyết định** của §7. Nó cũng là chỗ spec để hở một trường hợp mà plan phải chốt.

**Files:**
- Modify: `rsi_fvg/quarter_stats.py`
- Modify: `tests/test_quarter_stats.py`

**Interfaces:**
- Consumes: bảng chu kỳ của Task 3
- Produces: `stat_reclaim_q3(w) -> dict[str, float]` — khoá `reclaim_up_p_q3_down`, `n_up`, `reclaim_dn_p_q3_up`, `n_dn`, `reclaim_pooled_against`, `n_pooled`, `n_both_sides`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `tests/test_quarter_stats.py`:

```python
from rsi_fvg.quarter_stats import stat_reclaim_q3

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
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarter_stats.py -q -k reclaim`
Expected: FAIL — `ImportError: cannot import name 'stat_reclaim_q3'`

- [ ] **Step 3: Cài `stat_reclaim_q3`**

Thêm vào `rsi_fvg/quarter_stats.py`:

```python
def stat_reclaim_q3(w: pd.DataFrame) -> dict[str, float]:
    """⑥ Sau khi Q2 sweep biên Q1 rồi ĐÓNG LẠI bên trong, Q3 có đi ngược không.

    Đây là thesis sẽ thành luật vào lệnh ở Phase 2, và `reclaim_pooled_against`
    là con số duy nhất mà luật kết luận §7 dùng.

      Sweep lên  + reclaim: q2_high > q1_high VÀ q2_close < q1_high -> P(Q3 giảm)
      Sweep xuống + reclaim: q2_low  < q1_low  VÀ q2_close > q1_low  -> P(Q3 tăng)
      Pooled: gộp hai tập, P(Q3 đi NGƯỢC hướng sweep)

    Hai luật loại, cả hai đều có ý:
      - Hoà bị loại (spec §4.2): q2_close bằng đúng biên, hoặc Q3 đóng bằng mở.
        Dùng < và > thay cho <= và >= là cách loại hoà ở biên.
      - Chu kỳ sweep CẢ HAI phía bị loại khỏi cả ba con số. Spec không nói tới
        trường hợp này; lý thuyết không đưa ra kỳ vọng hướng nào cho nó, và đưa
        vào pooled sẽ đếm một chu kỳ hai lần với hai kỳ vọng trái nhau.
    """
    q1h = w["q1_high"].to_numpy()
    q1l = w["q1_low"].to_numpy()
    q2h = w["q2_high"].to_numpy()
    q2l = w["q2_low"].to_numpy()
    q2c = w["q2_close"].to_numpy()
    q3_dir = np.sign(w["q3_close"].to_numpy() - w["q3_open"].to_numpy())

    swept_up = (q2h > q1h) & (q2c < q1h)
    swept_dn = (q2l < q1l) & (q2c > q1l)
    both = swept_up & swept_dn
    live = q3_dir != 0                       # Q3 phẳng là hoà, loại
    up = swept_up & ~both & live
    dn = swept_dn & ~both & live

    against_up = q3_dir[up] < 0
    against_dn = q3_dir[dn] > 0
    pooled = np.concatenate([against_up, against_dn])
    return {
        "reclaim_up_p_q3_down": _mean_or_nan(against_up), "n_up": float(up.sum()),
        "reclaim_dn_p_q3_up": _mean_or_nan(against_dn), "n_dn": float(dn.sum()),
        "reclaim_pooled_against": _mean_or_nan(pooled), "n_pooled": float(pooled.size),
        "n_both_sides": float(both.sum()),
    }
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarter_stats.py -q`
Expected: PASS — 21 test.

- [ ] **Step 5: Commit**

```bash
git add rsi_fvg/quarter_stats.py tests/test_quarter_stats.py
git commit -m "feat(quarter_stats): phep do 6 - reclaim roi Q3 di nguoc

Thesis se thanh luat vao lenh o Phase 2, va reclaim_pooled_against la con
so duy nhat luat ket luan section 7 dung.

Hai luat loai: hoa (q2_close dung bien, hoac Q3 dong bang mo) va chu ky
sweep CA HAI phia. Truong hop hai phia spec khong noi toi - ly thuyet
khong co ky vong huong nao cho no, va dua vao pooled se dem mot chu ky
hai lan voi hai ky vong trai nhau.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: Bộ máy permutation — sinh offset, chạy lưới, tính percentile

**Files:**
- Modify: `rsi_fvg/quarter_stats.py`
- Modify: `tests/test_quarter_stats.py`

**Interfaces:**
- Consumes: `TIERS`, `label_quarters` (Task 2); `aggregate_cycles` (Task 3); sáu thống kê (Task 4–6)
- Produces:
  - `OFFSET_EXCLUDE = 600`
  - `STATS: dict[str, callable]` — sáu thống kê theo tên
  - `make_offsets(tier, bar_seconds, shifts, seed) -> np.ndarray`
  - `run_grid(bars, tier, anchor_offset=0, min_bars=MIN_BARS_PER_QUARTER) -> dict[str, float]` — khoá dạng `"<tên stat>.<tên đại lượng>"`
  - `percentile_of(real: float, null: np.ndarray) -> float`
  - `run_null(bars, tier, offsets, min_bars=...) -> pd.DataFrame` — một dòng mỗi offset

- [ ] **Step 1: Viết test đỏ**

Thêm vào `tests/test_quarter_stats.py`:

```python
from rsi_fvg.quarter_stats import (OFFSET_EXCLUDE, STATS, make_offsets,
                                   percentile_of, run_grid, run_null)


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
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `python -m pytest tests/test_quarter_stats.py -q -k "offset or run_grid or percentile or run_null"`
Expected: FAIL — `ImportError: cannot import name 'OFFSET_EXCLUDE'`

- [ ] **Step 3: Cài bộ máy permutation**

Thêm vào `rsi_fvg/quarter_stats.py`. Import thêm `from .quarters import TIERS, label_quarters` ở đầu file.

```python
OFFSET_EXCLUDE = 600

STATS = {
    "sweep": stat_sweep,
    "range_by_index": stat_range_by_index,
    "displacement_by_index": stat_displacement_by_index,
    "q1_predicts_q2": stat_q1_predicts_q2,
    "true_open": stat_true_open,
    "reclaim_q3": stat_reclaim_q3,
}


def make_offsets(tier: str, bar_seconds: int, shifts: int, seed: int) -> np.ndarray:
    """Offset neo cho mô hình null (spec §4.1).

    Ba quyết định, cả ba đều có lý do:

    1. SNAP về bội số `bar_seconds`. Lưới thật có biên trùng bar chính xác
       (18:00, 19:30 đều là bội của 5 phút). Nếu lưới giả rơi giữa nến thì nó bị
       handicap về hình học, và lưới thật trông tốt hơn CHỈ VÌ nó căn lề — một
       bias nghiêng về phía lý thuyết.
    2. Lấy từ [0, 4L) tức TRỌN chu kỳ, không phải [0, L). Dịch đúng L không đổi
       biên mà chỉ ĐỔI TÊN quarter, và ①②③⑥ đều phụ thuộc chỉ số quarter nên
       phép đổi tên đó là thông tin.
    3. Loại lân cận 0 để lưới giả không trùng lưới thật.

    Số offset khả dụng là (4L / bar_seconds) trừ lân cận 0, nên tầng q90 chỉ có
    69 lưới null dù xin bao nhiêu. Hàm trả về ít hơn `shifts` khi hết mốc — KHÔNG
    lặp lại mốc, vì mốc trùng sẽ làm phân phối null hẹp giả tạo.
    """
    cycle = 4 * TIERS[tier]
    grid = np.arange(0, cycle, bar_seconds, dtype="int64")
    ok = (grid >= OFFSET_EXCLUDE) & (grid <= cycle - OFFSET_EXCLUDE)
    candidates = grid[ok]
    if candidates.size <= shifts:
        return candidates
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(candidates, size=shifts, replace=False))


def run_grid(bars: Bars, tier: str, anchor_offset: int = 0,
             min_bars: int = MIN_BARS_PER_QUARTER) -> dict[str, float]:
    """Chạy cả sáu thống kê trên một lưới. Khoá dạng "<stat>.<đại lượng>"."""
    labels = label_quarters(bars.time, tier, anchor_offset)
    w = aggregate_cycles(bars, labels, min_bars)
    out: dict[str, float] = {}
    for name, fn in STATS.items():
        for key, value in fn(w).items():
            out[f"{name}.{key}"] = value
    return out


def run_null(bars: Bars, tier: str, offsets: np.ndarray,
             min_bars: int = MIN_BARS_PER_QUARTER) -> pd.DataFrame:
    """Một dòng mỗi lưới null."""
    rows = []
    for off in np.asarray(offsets, dtype="int64"):
        row = {"anchor_offset": int(off)}
        row.update(run_grid(bars, tier, int(off), min_bars))
        rows.append(row)
    return pd.DataFrame(rows)


def percentile_of(real: float, null: np.ndarray) -> float:
    """Phần trăm lưới null có giá trị NHỎ HƠN lưới thật.

    100 nghĩa là lưới thật cao hơn mọi lưới null. NaN của null bị bỏ (một lưới
    null có thể loại hết chu kỳ và cho NaN); NaN của `real` cho NaN.
    """
    null = np.asarray(null, dtype="float64")
    null = null[np.isfinite(null)]
    if null.size == 0 or not np.isfinite(real):
        return float("nan")
    return 100.0 * float(np.mean(null < real))
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `python -m pytest tests/test_quarter_stats.py -q`
Expected: PASS — 29 test.

- [ ] **Step 5: Chạy cả suite**

Run: `python -m pytest -q`
Expected: toàn bộ PASS.

- [ ] **Step 6: Commit**

```bash
git add rsi_fvg/quarter_stats.py tests/test_quarter_stats.py
git commit -m "feat(quarter_stats): bo may permutation - offset, run_grid, percentile

make_offsets SNAP ve boi so bar_seconds: luoi that co bien trung bar nen
luoi gia roi giua nen se bi handicap hinh hoc va luoi that trong tot hon
chi vi can le (spec 4.1). Lay tu [0, 4L) tron chu ky vi dich dung L chi
doi ten quarter, ma 1/2/3/6 deu phu thuoc chi so quarter.

Tran thuc cua tang q90 la 69 luoi null (21600/300 = 72 moc tru lan can
0), khong phai 200. Ham tra ve it hon yeu cau chu KHONG lap moc - moc
trung se lam phan phoi null hep gia tao.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: CLI `scripts/study_quarters.py` — cổng chặn, permutation, phán quyết §7

**Files:**
- Create: `scripts/study_quarters.py`

**Interfaces:**
- Consumes: mọi thứ của Task 1–7; `rsi_fvg.data.mt5_loader.load_or_fetch`; `rsi_fvg.bars.Bars.from_dataframe`
- Produces: `results/quarters_study/<YYYY-MM-DD>/stats.csv` và `summary.md`; mã thoát 0/1/2

- [ ] **Step 1: Viết script**

```python
"""Đo tiền đề Quarterly Theory: lưới thời gian có cấu trúc thật, hay chỉ là hình
học của việc chia bốn?

Spec: docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md

Usage:
  python scripts/study_quarters.py
  python scripts/study_quarters.py --tf M5 --shifts 200 --seed 20260909
  python scripts/study_quarters.py --tiers session          # chỉ một tầng

Mã thoát: 0 nghiên cứu chạy xong; 1 cổng chặn timezone fail; 2 không đủ dữ liệu.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from rsi_fvg.bars import Bars  # noqa: E402
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.quarter_stats import (STATS, make_offsets, percentile_of,  # noqa: E402
                                   run_grid, run_null)
from rsi_fvg.quarters import TIERS, verify_server_tz  # noqa: E402

TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600}

# Con số duy nhất mà luật kết luận §7 dùng, và ngưỡng của nó.
VERDICT_KEY = "reclaim_q3.reclaim_pooled_against"
VERDICT_THRESHOLD = 95.0


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbol", default="XAUUSDc")
    p.add_argument("--tf", default="M5", choices=sorted(TF_SECONDS))
    p.add_argument("--tiers", nargs="+", default=["session", "q90"],
                   choices=sorted(TIERS))
    p.add_argument("--shifts", type=int, default=200,
                   help="số lưới null xin; tầng q90 chỉ có 69 mốc khả dụng")
    p.add_argument("--seed", type=int, default=20260909)
    p.add_argument("--data-dir", type=Path, default=ROOT / "data")
    p.add_argument("--out-dir", type=Path, default=None)
    return p.parse_args(argv)


def load_bars(symbol: str, tf: str, data_dir: Path) -> Bars:
    df = load_or_fetch(symbol, tf, data_dir)
    return Bars.from_dataframe(df)


def gate_timezone(bars: Bars, bar_seconds: int) -> None:
    """Cổng chặn §3.2. Fail thì thoát 1 và KHÔNG chạy nghiên cứu."""
    chk = verify_server_tz(bars.time, bar_seconds)
    print("--- cong chan timezone (spec 3.2) ---")
    print(f"  mo dau tuan  : {chk.weekly_open_mode!r}  ok={chk.weekly_ok}")
    print(f"    phan phoi  : {chk.weekly_open_counts}")
    print(f"  ket khe ngay : {chk.daily_gap_end_mode!r}  ok={chk.daily_ok}")
    print(f"    phan phoi  : {chk.daily_gap_end_counts}")
    for note in chk.notes:
        print(f"  ghi chu: {note}")
    if not chk.ok:
        print("\nFAIL: gia dinh 'dong ho server = EET' khong dung voi du lieu nay.")
        print("Moi bien quarter la mot moc gio New York, nen nghien cuu se do sai")
        print("hoan toan. Khong chay tiep. Xem spec section 2 va 3.2.")
        sys.exit(1)
    print("  PASS\n")


def study_tier(bars: Bars, tier: str, bar_seconds: int,
               shifts: int, seed: int) -> pd.DataFrame:
    real = run_grid(bars, tier)
    offsets = make_offsets(tier, bar_seconds, shifts, seed)
    if len(offsets) < shifts:
        print(f"  [{tier}] chi co {len(offsets)} moc neo kha dung (xin {shifts}). "
              f"Chu ky {4 * TIERS[tier]} s / bar {bar_seconds} s gioi han so luoi null.")
    nulls = run_null(bars, tier, offsets)

    rows = []
    for key, real_value in real.items():
        col = nulls[key].to_numpy(dtype="float64") if key in nulls else np.array([])
        finite = col[np.isfinite(col)]
        rows.append({
            "tier": tier, "quantity": key, "real": real_value,
            "null_mean": float(finite.mean()) if finite.size else float("nan"),
            "null_p05": float(np.percentile(finite, 5)) if finite.size else float("nan"),
            "null_p50": float(np.percentile(finite, 50)) if finite.size else float("nan"),
            "null_p95": float(np.percentile(finite, 95)) if finite.size else float("nan"),
            "real_percentile": percentile_of(real_value, col),
            "n_nulls": int(finite.size),
        })
    return pd.DataFrame(rows)


def verdict(stats: pd.DataFrame) -> tuple[bool, str]:
    """Luật §7, tính bằng máy — không để người đọc tự kết luận."""
    rows = stats[stats["quantity"] == VERDICT_KEY]
    lines = ["## Phan quyet section 7", ""]
    passed = False
    for _, r in rows.iterrows():
        hit = bool(np.isfinite(r["real_percentile"])
                   and r["real_percentile"] > VERDICT_THRESHOLD)
        passed = passed or hit
        lines.append(f"- tang **{r['tier']}**: real={r['real']:.4f}, "
                     f"percentile={r['real_percentile']:.1f}, "
                     f"nulls={r['n_nulls']} -> {'VUOT' if hit else 'khong vuot'} "
                     f"nguong {VERDICT_THRESHOLD}")
    lines += ["", (
        "**Phase 2 duoc phep viet spec.** Thong ke 6 pooled vuot percentile 95 "
        "cua null o it nhat mot tang." if passed else
        "**Phase 2 KHONG duoc phep viet spec.** Thong ke 6 pooled khong vuot "
        "percentile 95 o tang nao. Cac phep do 1-5 du dep cung khong mo cong "
        "nay (spec section 7)."
    ), "", (
        "Luu y da ghi trong spec section 7: luat nay chay 2 kiem dinh o muc 95% "
        "nen sai so toan ho khoang 10%, khong phai 5%. Nguong de nay duoc chon "
        "co y thuc va khong duoc siet hay noi sau khi thay so."
    )]
    return passed, "\n".join(lines)


def main(argv=None) -> int:
    args = parse_args(argv)
    bar_seconds = TF_SECONDS[args.tf]
    bars = load_bars(args.symbol, args.tf, args.data_dir)
    print(f"{args.symbol} {args.tf}: {len(bars)} bar")
    if len(bars) < 1000:
        print("FAIL: qua it bar de do bat cu thu gi.")
        return 2

    gate_timezone(bars, bar_seconds)

    parts = [study_tier(bars, t, bar_seconds, args.shifts, args.seed)
             for t in args.tiers]
    stats = pd.concat(parts, ignore_index=True)

    out_dir = args.out_dir or (ROOT / "results" / "quarters_study" / date.today().isoformat())
    out_dir.mkdir(parents=True, exist_ok=True)
    stats.to_csv(out_dir / "stats.csv", index=False)

    passed, verdict_md = verdict(stats)
    # KHONG dung stats.to_markdown: no doi `tabulate`, khong co trong
    # requirements.txt (da kiem). to_string trong khoi ``` cho ket qua doc duoc
    # ma khong them dependency.
    head = ["# Quarterly Theory - nghien cuu tien de", "",
            f"- symbol: {args.symbol}  timeframe: {args.tf}  bars: {len(bars)}",
            f"- tiers: {', '.join(args.tiers)}  shifts xin: {args.shifts}  seed: {args.seed}",
            "- spec: docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md",
            "", "## Bang thong ke", "",
            "```", stats.to_string(index=False), "```", ""]
    (out_dir / "summary.md").write_text("\n".join(head) + verdict_md + "\n",
                                        encoding="utf-8")
    print(verdict_md)
    print(f"\nket qua: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke test hai hàm thuần của script**

Không thêm test file mới cho script (repo không test `scripts/` nào). Kiểm bằng cách chạy trực tiếp với `--out-dir` vào thư mục tạm và một chuỗi bar tổng hợp là quá vòng vo; thay vào đó kiểm hai hàm thuần của script bằng interpreter:

Run:
```bash
python -c "
import sys; sys.path.insert(0,'scripts'); sys.path.insert(0,'.')
from study_quarters import parse_args, verdict, VERDICT_KEY
import pandas as pd, numpy as np
a = parse_args(['--tf','M15','--tiers','session'])
assert a.tf=='M15' and a.tiers==['session'] and a.shifts==200
df = pd.DataFrame([{'tier':'session','quantity':VERDICT_KEY,'real':0.6,'real_percentile':97.0,'n_nulls':200}])
ok, md = verdict(df); assert ok and 'duoc phep' in md
df2 = df.assign(real_percentile=[50.0]); ok2, md2 = verdict(df2); assert not ok2 and 'KHONG duoc phep' in md2
print('smoke ok')
"
```
Expected: in ra `smoke ok`.

- [ ] **Step 3: Chạy cả suite để chắc script không phá import nào**

Run: `python -m pytest -q`
Expected: toàn bộ PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/study_quarters.py
git commit -m "feat(scripts): study_quarters CLI - cong chan tz, permutation, phan quyet

Cong chan verify_server_tz chay TRUOC va thoat 1 khi fail: moi bien
quarter la mot moc gio New York nen gia dinh EET sai thi nghien cuu do
sai hoan toan.

Phan quyet section 7 tinh BANG MAY chu khong de nguoi doc tu ket luan,
va in ca ghi chu ve sai so toan ho ~10% voi 2 kiem dinh o muc 95%.

Khong dung to_markdown vi tabulate khong co trong requirements.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 9: Chạy trên dữ liệu thật, README, báo số

**Files:**
- Modify: `README.md`
- Tạo (kết quả, commit được): `results/quarters_study/<hôm nay>/stats.csv`, `summary.md`

**Interfaces:**
- Consumes: toàn bộ Task 1–8
- Produces: không có

- [ ] **Step 1: Chạy cổng chặn trước, một mình**

Run:
```bash
python -c "
import sys; sys.path.insert(0,'.')
from pathlib import Path
from rsi_fvg.bars import Bars
from rsi_fvg.data.mt5_loader import load_or_fetch
from rsi_fvg.quarters import verify_server_tz
b = Bars.from_dataframe(load_or_fetch('XAUUSDc','M5',Path('data')))
c = verify_server_tz(b.time, 300)
print('weekly:', c.weekly_open_mode, c.weekly_ok)
print('  ', dict(list(c.weekly_open_counts.items())[:6]))
print('daily :', c.daily_gap_end_mode, c.daily_ok)
print('  ', dict(list(c.daily_gap_end_counts.items())[:6]))
print('ok    :', c.ok, c.notes)
"
```

Đây là bước **có thể fail và fail là kết quả hợp lệ**. Ba khả năng:

1. `ok=True` → chạy tiếp Step 2.
2. `weekly_ok=False` và mode lệch **đúng một giờ** khỏi cửa sổ (ví dụ `"Sun 19:00"` hoặc `"Sun 16:00"`) → giả định EET sai. **Dừng, báo lại, không tự sửa `SERVER_TZ` để cho pass.** Đổi timezone cho khớp là hợp lý hoá kết quả; đúng quy trình là báo con số thật và để người chốt.
3. `weekly_ok=False` với mode hỗn loạn, hoặc `server_to_ny` raise `AmbiguousTimeError`/`NonExistentTimeError` → dữ liệu có vấn đề sâu hơn timezone. Dừng, báo lại kèm thông báo lỗi nguyên văn.

- [ ] **Step 2: Chạy nghiên cứu đầy đủ**

Run: `python scripts/study_quarters.py --tf M5`
Expected: cổng chặn PASS, in bảng thống kê cả hai tầng, in phán quyết §7, ghi vào `results/quarters_study/<hôm nay>/`.

Nếu chạy quá 10 phút thì giảm `--shifts 50` để xem kết quả trước, rồi chạy lại đủ 200.

- [ ] **Step 3: Đọc kết quả và báo số, KHÔNG diễn giải quá dữ liệu**

Báo lại: mode của cổng chặn; `n` chu kỳ dùng được mỗi tầng và số chu kỳ bị loại; sáu percentile; số `n_nulls` thật của mỗi tầng (nhớ tầng q90 chỉ có 69); và phán quyết §7 mà script đã tính.

Ba điều **phải** nói kèm nếu phán quyết là PASS, vì spec §8 đã ghi và chúng không được biến mất khỏi báo cáo:

- Nghiên cứu này **không tính cost**. Spread XAUUSDc trong `config/default.yaml` là 260 points = 0,26 USD. Một edge nhỏ hơn spread là vô dụng dù percentile đẹp đến đâu.
- **Confound của mốc 18:00** (spec §8.2): khe nghỉ hằng ngày của broker kết thúc đúng 18:00 NY, trùng mốc neo chu kỳ ngày. Hiệu ứng ở tầng session có thể đến từ microstructure lúc mở lại chứ không từ lý thuyết. Tầng q90 ít bị hơn.
- Percentile ở tầng q90 chỉ có **69 lưới null**, nên độ phân giải là ~1,45% và ngưỡng p95 là giá trị thứ 65 — dùng được nhưng thô.

- [ ] **Step 4: Thêm mục vào `README.md`**

Chèn ngay trước mục `## Setup (Windows, Python 3.13)`:

```markdown
## Quarterly Theory — nghiên cứu tiền đề

    python scripts/study_quarters.py --tf M5      # -> results/quarters_study/<ngày>/

Đo xem lưới thời gian của Quarterly Theory (ICT) có cấu trúc thật trên XAUUSDc hay chỉ là hình học của việc chia bốn: sáu phép đo, mỗi phép so với tối đa 200 lưới neo lệch (anchor-shift permutation). `rsi_fvg/quarters.py` convert đồng hồ server sang giờ New York — **bắt buộc với lý thuyết này**, vì mọi biên quarter là một mốc giờ NY và loader gán nhãn giờ server là UTC không convert (xem mục Timestamps). Script chạy một cổng chặn kiểm giả định "server = EET" bằng dữ liệu và thoát 1 nếu fail. Spec, luật kết luận và giới hạn: `docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md`.
```

- [ ] **Step 5: Commit**

```bash
git add README.md results/quarters_study
git commit -m "study: chay nghien cuu tien de Quarterly Theory tren XAUUSDc M5

Ket qua trong results/quarters_study/. README them mot muc.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Self-review: đối chiếu plan với spec

| Mục spec | Task |
|---|---|
| §1 Mục tiêu | 8 (phán quyết), 9 (chạy) |
| §2 Vấn đề timezone, offset chỉ 6 hoặc 7 | 1 (`server_to_ny` + test bốn mốc DST) |
| §3.1 `server_to_ny`, raise trên ambiguous/nonexistent | 1 |
| §3.2 `verify_server_tz`, hai kiểm định, cổng chặn | 1 (hàm), 8 (cổng trong CLI), 9 Step 1 (chạy thật) |
| §3.3 `label_quarters`, hai tầng, `trading_day`, `anchor_offset` | 2 |
| §4.1 Null model, snap về bar interval, loại lân cận 0, `[0,4L)` | 7 |
| §4.2 Sáu phép đo | 4 (①②③), 5 (④⑤), 6 (⑥) |
| §4.2 Loại chu kỳ thiếu bar, áp cho cả null | 3 |
| §4.2 Ràng buộc hoà | 5 (⑤), 6 (⑥) |
| §4.3 `stats.csv` + `summary.md` | 8 |
| §5 Bảy nhóm test | 1 (test 1,2,5,6), 2 (test 1,3,4), 7 (test 7) |
| §6 Cỡ mẫu | 9 Step 3 (báo `n` thật) |
| §7 Luật kết luận tính bằng máy | 8 (`verdict`) |
| §8 Giới hạn | 9 Step 3 (bắt buộc báo kèm) |

**Một mục spec không có task riêng, có ý:** §6 (cỡ mẫu) là con số ước lượng để đọc kết quả, không phải thứ để cài — Task 9 báo `n` thật thay vì hardcode ước lượng.

**Tên dùng xuyên plan, kiểm nhất quán:**
`SERVER_TZ` `NY_TZ` `WEEK_GAP_SECONDS` `DOW` `WEEKLY_OPEN_OK` `DAILY_GAP_END_OK` `server_to_ny` `TzCheck` `verify_server_tz` · `TIERS` `NS_PER_DAY` `QuarterLabels` `label_quarters` · `MIN_BARS_PER_QUARTER` `_FIELDS` `QUARTERS` `_mean_or_nan` `aggregate_cycles` · `stat_sweep` `stat_range_by_index` `stat_displacement_by_index` `stat_q1_predicts_q2` `stat_true_open` `stat_reclaim_q3` · `OFFSET_EXCLUDE` `STATS` `make_offsets` `run_grid` `run_null` `percentile_of` · `TF_SECONDS` `VERDICT_KEY` `VERDICT_THRESHOLD` `parse_args` `load_bars` `gate_timezone` `study_tier` `verdict` `main` · trong conftest: `epoch_for_ny` `mk_epoch_ny`

Cột bảng chu kỳ dùng `q1_`..`q4_` ở mọi task, không chỗ nào dùng `q0_`.
