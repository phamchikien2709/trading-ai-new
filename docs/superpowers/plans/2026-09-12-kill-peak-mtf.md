# Kill Peak (Đỉnh Chờ Kill) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hai file Pine cho chiến lược Đỉnh Chờ Kill — M5 chỉ ra mức thanh khoản thị trường còn nợ, M1 chờ giá tạo higher low rồi vào lệnh, TP đặt đúng tại mức đó.

**Architecture:** Script chạy trên chart M1. Đúng một `request.security` kéo RSI(14) M5 về; toàn bộ máy trạng thái chạy trên trục M1 để mọi biến đều plot được. Hai tầng độc lập: tầng bối cảnh (đoạn đo + cờ chờ, ba mốc 70/50/30) và tầng swing RSI(2) 90/10 theo leg xen kẽ. Tín hiệu là giao của hai tầng.

**Tech Stack:** Pine Script v6. Python 3.13 (chỉ trong scratchpad, để kiểm chứng — không vào repo).

**Spec:** `docs/superpowers/specs/2026-09-12-kill-peak-mtf-design.md`

## Global Constraints

- Pine `//@version=6`, dòng đầu tiên của cả hai file.
- **Luật nối dòng Pine:** dòng nối tiếp phải thụt lề bằng số space **không chia hết cho 4** (repo dùng 5 hoặc 9). Thụt 4/8 space sẽ bị hiểu là khối mới → lỗi compile.
- Không dùng ký tự tab.
- Không có `ta.*` nào nằm trong khối `if` — tính ở top level rồi mới dùng trong nhánh. `ta.highest`/`ta.lowest`/`ta.atr`/`ta.rsi` giữ state nội bộ, gọi có điều kiện là sai số âm thầm.
- Mọi tên input, giá trị mặc định, tên biến state lấy **nguyên văn** từ spec §9 và §3.2. Không tự đổi tên.
- Ba lý do tắt cờ, dùng đúng ba chuỗi này ở cả label lẫn bộ đếm: `KILL`, `RSIOUT`, `NEWLEVEL`.
- Không đụng bất kỳ file nào đang có trong repo. Chỉ tạo mới.
- **Không compile được Pine ở máy này.** Không được báo "đã test" cho bất kỳ task Pine nào. Câu đúng là "đã qua static check và đã đối chiếu với oracle".

### Scratchpad

Mọi file Python của kế hoạch này nằm trong scratchpad của session, **không commit**:

```
<scratchpad>/kp_check.py     — static checker cho file Pine
<scratchpad>/kp_oracle.py    — dựng lại hai máy trạng thái bằng Python
<scratchpad>/kp_test.py      — test cho oracle
```

Spec §11 đã chốt để chúng ngoài repo vì port Python thật còn chờ luật ổn định (spec §12). Nếu sau này muốn giữ, `kp_oracle.py` chính là hạt giống của `rsi_fvg/strategies/kill_peak.py`.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `pine/kill_peak_indicator.pine` | `overlay=true`, không đặt lệnh. Hai tầng + tín hiệu + mô phỏng vị thế để đếm + vẽ + hai bảng. |
| `pine/kill_peak_strategy.pine` | Cùng khối tín hiệu, thay mô phỏng vị thế bằng `strategy.*`, thêm sizing/alert. |
| `<scratchpad>/kp_check.py` | Static checker. |
| `<scratchpad>/kp_oracle.py` | Oracle: `ctx_step`, `swing_step`, `signal_step`, `run`. |
| `<scratchpad>/kp_test.py` | Test bất biến của spec §3.3, §3.4, §4.1, §5. |

Thứ tự thi công: oracle trước (Task 1–3), Pine sau (Task 4–8), soát chéo cuối (Task 9). Oracle là bản chạy được của spec — viết Pine trước rồi mới kiểm là viết ngược.

---

## Task 1: Đồ nghề — static checker

**Files:**
- Create: `<scratchpad>/kp_check.py`

**Interfaces:**
- Produces: `check(path: str) -> list[str]` — trả về danh sách lỗi, rỗng là sạch. CLI: `python kp_check.py <file.pine>`, exit 1 nếu có lỗi.

- [ ] **Step 1: Viết checker**

```python
# kp_check.py
import re
import sys


def _strip_strings(line: str) -> str:
    """Bo noi dung chuoi don-nhay de dem nhay-kep khong bi nham.

    Pine cho phep '...' chua " (alert JSON dung kieu nay), nen phai bo
    chuoi don-nhay TRUOC roi moi dem nhay-kep.
    """
    return re.sub(r"'[^']*'", "''", line)


def check(path: str) -> list[str]:
    errs: list[str] = []
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")

    if not lines or not lines[0].startswith("//@version=6"):
        errs.append("dong 1 phai la //@version=6")

    depth = 0          # do sau ngoac tron/vuong tich luy qua cac dong
    for i, raw in enumerate(lines, start=1):
        if "\t" in raw:
            errs.append(f"{i}: co ky tu tab")

        code = raw.split("//")[0] if not raw.lstrip().startswith("//") else ""
        stripped = _strip_strings(code)

        if stripped.count('"') % 2 != 0:
            errs.append(f"{i}: so nhay-kep le")

        # dong nay la dong noi tiep neu dong truoc con ho ngoac
        if depth > 0 and raw.strip():
            indent = len(raw) - len(raw.lstrip(" "))
            if indent % 4 == 0:
                errs.append(
                    f"{i}: dong noi tiep thut {indent} space (chia het 4) "
                    "-> Pine hieu la khoi moi"
                )

        depth += stripped.count("(") - stripped.count(")")
        depth += stripped.count("[") - stripped.count("]")
        if depth < 0:
            errs.append(f"{i}: dong ngoac am")
            depth = 0

    if depth != 0:
        errs.append(f"het file ma con ho {depth} ngoac")
    return errs


if __name__ == "__main__":
    bad = 0
    for p in sys.argv[1:]:
        for e in check(p):
            print(f"{p}:{e}")
            bad += 1
    print("SACH" if bad == 0 else f"{bad} loi")
    sys.exit(1 if bad else 0)
```

- [ ] **Step 2: Chạy checker trên một file Pine đã có để xác nhận nó không báo bậy**

```bash
python "<scratchpad>/kp_check.py" "pine/rsi2_divergence_indicator.pine" "pine/rsi2_ema_swing_strategy.pine"
```

Kỳ vọng: `SACH`, exit 0. Hai file này đang chạy tốt trên TradingView nên checker báo lỗi ở đây là checker sai, không phải file sai — sửa checker cho tới khi sạch.

- [ ] **Step 3: Chạy checker trên một file cố tình hỏng để xác nhận nó bắt được**

```bash
printf '//@version=6\nx = (1 +\n    2)\n' > "<scratchpad>/bad.pine"
python "<scratchpad>/kp_check.py" "<scratchpad>/bad.pine"
```

Kỳ vọng: báo dòng 3 thụt 4 space, exit 1. Xong thì xoá `bad.pine`.

Không commit — file scratchpad.

---

## Task 2: Oracle tầng M5 + test bất biến

**Files:**
- Create: `<scratchpad>/kp_oracle.py`
- Create: `<scratchpad>/kp_test.py`

**Interfaces:**
- Produces:
  - `Bar(high, low, close, ctx_rsi, fast_rsi, atr)` — dataclass.
  - `Ctx` — dataclass state, tên field khớp spec §3.2.
  - `ctx_step(st: Ctx, bars: list[Bar], i: int, n: int, ev: list) -> None` — chạy đúng sáu bước spec §3.3 cho nến `i`.
  - `ev` nhận tuple `(bar, tag, value)` với tag thuộc `{"FLAG_BUY_ON", "FLAG_BUY_OFF", "FLAG_SELL_ON", "FLAG_SELL_OFF"}`; với `*_OFF` thì `value` là lý do.

- [ ] **Step 1: Viết test trước — ba lý do tắt cờ**

```python
# kp_test.py
import math
from kp_oracle import Bar, Ctx, ctx_step


def run_ctx(rows, n=1):
    """rows: (high, low, ctx_rsi). Tra ve (state, events)."""
    bars = [Bar(h, l, l, c, 50.0, 1.0) for h, l, c in rows]
    st, ev = Ctx(), []
    for i in range(len(bars)):
        ctx_step(st, bars, i, n, ev)
    return st, ev


def offs(ev, side="BUY"):
    return [(b, why) for b, tag, why in ev if tag == f"FLAG_{side}_OFF"]


def test_ket_thuc_vi_kill():
    st, ev = run_ctx([
        (100, 99, 50),
        (101, 99, 75),   # cUp70 -> mo doan do
        (102, 99, 72),   # run_high = 102
        (101, 99, 45),   # cDn50 -> chot 102, bat co
        (101, 99, 45),
        (103, 99, 45),   # high 103 >= 102 -> KILL
    ])
    assert st.kill_high == 102.0
    assert st.flag_buy_bar == 3
    assert offs(ev) == [(5, "KILL")]
    assert st.flag_buy is False


def test_ket_thuc_vi_rsiout():
    st, ev = run_ctx([
        (100, 99, 50), (101, 99, 75), (102, 99, 72), (101, 99, 45),
        (101, 99, 25),   # cDn30 -> huy co BUY, mo doan do day
    ])
    assert offs(ev) == [(4, "RSIOUT")]
    assert st.meas_lo is True


def test_ket_thuc_vi_newlevel():
    st, ev = run_ctx([
        (100, 99, 50), (101, 99, 75), (102, 99, 72), (101, 99, 45),
        (104, 99, 75),   # cUp70 lan nua -> vut dinh cu, mo doan do moi
    ])
    assert offs(ev) == [(4, "NEWLEVEL")]
    assert st.meas_hi is True


def test_nen_nhay_kep_chot_truoc_huy_sau():
    """ctx nhay 75 -> 25 trong mot nen: co sinh ra va chet ngay nen do."""
    st, ev = run_ctx([
        (100, 99, 50), (101, 99, 75), (102, 99, 75),
        (101, 99, 25),   # cDn50 VA cDn30 cung nen
    ])
    assert [(b, t) for b, t, _ in ev] == [
        (3, "FLAG_BUY_ON"), (3, "FLAG_BUY_OFF"),
    ]
    assert offs(ev) == [(3, "RSIOUT")]
    assert st.kill_high == 102.0    # van chot dinh
    assert st.flag_buy is False     # nhung khong duoc vao lenh
    assert st.meas_lo is True


def test_seed_run_high_khong_mat_phan_cao_cua_nen_htf():
    """n=5: cu cat len 70 phat hien tre, dinh cua nen M5 do nam o 5 nen truoc."""
    st, _ = run_ctx([
        (100, 99, 50),
        (105, 99, 50),   # dinh that nam o day
        (103, 99, 50),
        (101, 99, 50),
        (100, 99, 50),
        (99, 98, 75),    # cUp70 phat hien o day, high chi 99
    ], n=5)
    assert st.run_high == 105.0


def test_hai_co_khong_bao_gio_cung_bat():
    import random
    random.seed(7)
    rows, v = [], 50.0
    for _ in range(4000):
        v = min(99.0, max(1.0, v + random.uniform(-18, 18)))
        rows.append((100 + random.uniform(0, 3), 99 - random.uniform(0, 3), v))
    bars = [Bar(h, l, l, c, 50.0, 1.0) for h, l, c in rows]
    st, ev = Ctx(), []
    for i in range(len(bars)):
        ctx_step(st, bars, i, 5, ev)
        assert not (st.flag_buy and st.flag_sell), f"hai co cung bat o nen {i}"
    assert any(t == "FLAG_BUY_ON" for _, t, _ in ev)
    assert any(t == "FLAG_SELL_ON" for _, t, _ in ev)
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

```bash
cd "<scratchpad>" && python -m pytest kp_test.py -x -q
```

Kỳ vọng: FAIL với `ModuleNotFoundError: No module named 'kp_oracle'`.

- [ ] **Step 3: Viết oracle tầng M5**

```python
# kp_oracle.py
import math
from dataclasses import dataclass

CTX_HI, CTX_MID, CTX_LO = 70.0, 50.0, 30.0
NAN = float("nan")


@dataclass
class Bar:
    high: float
    low: float
    close: float
    ctx_rsi: float
    fast_rsi: float
    atr: float


@dataclass
class Ctx:
    meas_hi: bool = False
    run_high: float = NAN
    kill_high: float = NAN
    kill_high_bar: int = -1
    flag_buy: bool = False
    flag_buy_bar: int = -1
    flag_buy_used: bool = False

    meas_lo: bool = False
    run_low: float = NAN
    kill_low: float = NAN
    kill_low_bar: int = -1
    flag_sell: bool = False
    flag_sell_bar: int = -1
    flag_sell_used: bool = False


def _seed_high(bars, i, n):
    return max(b.high for b in bars[max(0, i - n + 1): i + 1])


def _seed_low(bars, i, n):
    return min(b.low for b in bars[max(0, i - n + 1): i + 1])


def ctx_step(st, bars, i, n, ev):
    b = bars[i]
    prev = bars[i - 1].ctx_rsi if i > 0 else NAN
    cur = b.ctx_rsi
    # so sanh voi NaN luon False -> khong co su kien trong warm-up
    c_up70 = prev <= CTX_HI < cur
    c_dn50 = prev >= CTX_MID > cur
    c_up50 = prev <= CTX_MID < cur
    c_dn30 = prev >= CTX_LO > cur

    # 1. noi cuc tri
    if st.meas_hi:
        st.run_high = max(st.run_high, b.high)
    if st.meas_lo:
        st.run_low = min(st.run_low, b.low)

    # 2. cham muc
    if st.flag_buy and b.high >= st.kill_high:
        st.flag_buy = False
        ev.append((i, "FLAG_BUY_OFF", "KILL"))
    if st.flag_sell and b.low <= st.kill_low:
        st.flag_sell = False
        ev.append((i, "FLAG_SELL_OFF", "KILL"))

    # 3. cDn50 -> chot dinh cho kill
    if c_dn50 and st.meas_hi:
        st.kill_high = st.run_high
        st.kill_high_bar = i
        st.meas_hi = False
        st.flag_buy = True
        st.flag_buy_bar = i
        st.flag_buy_used = False
        ev.append((i, "FLAG_BUY_ON", st.kill_high))

    # 4. cUp50 -> chot day cho kill
    if c_up50 and st.meas_lo:
        st.kill_low = st.run_low
        st.kill_low_bar = i
        st.meas_lo = False
        st.flag_sell = True
        st.flag_sell_bar = i
        st.flag_sell_used = False
        ev.append((i, "FLAG_SELL_ON", st.kill_low))

    # 5. cDn30
    if c_dn30:
        if st.flag_buy:
            st.flag_buy = False
            ev.append((i, "FLAG_BUY_OFF", "RSIOUT"))
        if st.flag_sell:
            st.flag_sell = False
            ev.append((i, "FLAG_SELL_OFF", "NEWLEVEL"))
        if not st.meas_lo:
            st.meas_lo = True
            st.run_low = _seed_low(bars, i, n)

    # 6. cUp70
    if c_up70:
        if st.flag_sell:
            st.flag_sell = False
            ev.append((i, "FLAG_SELL_OFF", "RSIOUT"))
        if st.flag_buy:
            st.flag_buy = False
            ev.append((i, "FLAG_BUY_OFF", "NEWLEVEL"))
        if not st.meas_hi:
            st.meas_hi = True
            st.run_high = _seed_high(bars, i, n)
```

- [ ] **Step 4: Chạy test, phải xanh hết**

```bash
cd "<scratchpad>" && python -m pytest kp_test.py -x -q
```

Kỳ vọng: 6 passed.

Không commit — file scratchpad.

---

## Task 3: Oracle tầng M1 + tín hiệu + bộ đếm

**Files:**
- Modify: `<scratchpad>/kp_oracle.py`
- Modify: `<scratchpad>/kp_test.py`

**Interfaces:**
- Consumes: `Bar`, `Ctx`, `ctx_step` từ Task 2.
- Produces:
  - `Swing` — dataclass: `seg, seg_high, seg_high_bar, seg_low, seg_low_bar, last_low, last_low_bar, prev_low, prev_low_bar, last_high, last_high_bar, prev_high, prev_high_bar`.
  - `swing_step(st: Swing, bars, i) -> tuple[bool, bool]` — trả `(low_conf, high_conf)`.
  - `Params(hl_margin_atr=0.0, sl_atr_mult=0.2, min_rr=1.0, max_rr=0.0, require_after_flag=True, one_trade_per_flag=True, enable_buy=True, enable_sell=True)`.
  - `run(bars, n, p) -> dict` với khoá `trades` (list dict `side, bar, entry, sl, tp, rr`), `rejects` (list dict `side, bar, rr`), `counters` (dict `{"BUY": {...}, "SELL": {...}}` với các khoá `flags, kill, kill_entered, kill_missed, rsiout, newlevel`), `events`.
  - `SCENARIO_BUY: list[tuple]` — kịch bản BUY đầy đủ dạng `(high, low, close, ctx_rsi, fast_rsi)`, dùng chung cho test và cho bảng tham chiếu ở Step 6.

- [ ] **Step 1: Viết test trước — cấu trúc leg và tín hiệu đầy đủ**

Thêm vào `kp_test.py`:

```python
from kp_oracle import Swing, Params, swing_step, run


def test_leg_khong_reset_khi_choc_lai_cung_huong():
    """Regression: RSI2 chui duoi 10 hai lan trong cung mot leg.

    Day that la 90.0 o nen 1. Ban loi reset seg_low moi lan cat xuong
    nen se bao 94.0 (day SAU, cao hon).
    """
    rows = [
        # high,  low, fast_rsi
        (101, 100, 50),
        (99,   90,  5),   # cat xuong 10 -> mo leg LOW, day = 90
        (100,  95, 50),
        (99,   94,  5),   # choc xuong lan nua -> KHONG duoc reset
        (100,  92, 50),
        (105, 100, 95),   # cat len 90 -> chot swing low
    ]
    bars = [Bar(h, l, l, 50.0, f, 1.0) for h, l, f in rows]
    st = Swing()
    confs = [swing_step(st, bars, i) for i in range(len(bars))]
    assert confs[5][0] is True          # low_conf o nen 5
    assert st.last_low == 90.0
    assert st.last_low_bar == 1


def test_tin_hieu_buy_day_du():
    # rows nay phai duoc dat thanh hang so SCENARIO_BUY trong kp_oracle.py
    # (xem Step 6) roi import ve, de test va script in bang tham chieu dung
    # chung mot nguon.
    rows = [
        # high,   low,  close, ctx, fast
        (100,  99,    100,  50, 50),
        (105, 100,    104,  75, 50),   # cUp70, run_high 105
        (111, 104,    110,  72, 50),   # run_high 111
        (110, 105,    106,  45, 50),   # cDn50 -> kill_high 111, co bat o nen 3
        (106, 102,    103,  45,  5),   # mo leg LOW, day 102
        (104, 101,    102,  45,  8),   # day 101
        (105, 102,    104,  45, 95),   # chot swing low 1 = 101 -> chua co prev
        (106, 103,    105,  45, 50),
        (105, 103,    104,  45,  5),   # chot swing high, mo leg LOW, day 103
        (104, 103.5,  104,  45,  8),
        (107, 104,    106,  45, 95),   # chot swing low 2 = 103 -> HIGHER LOW
        (112, 106,    111,  45, 50),   # cham 111 -> KILL
    ]
    bars = [Bar(h, l, c, x, f, 1.0) for h, l, c, x, f in rows]
    out = run(bars, n=1, p=Params())

    assert len(out["trades"]) == 1
    t = out["trades"][0]
    assert t["side"] == "BUY"
    assert t["bar"] == 10
    assert t["entry"] == 106.0
    assert t["sl"] == 102.8            # 103 - 0.2 * 1.0
    assert t["tp"] == 111.0
    assert abs(t["rr"] - 5.0 / 3.2) < 1e-9

    c = out["counters"]["BUY"]
    assert c["flags"] == 1
    assert c["kill"] == 1
    assert c["kill_entered"] == 1
    assert c["kill_missed"] == 0


def test_swing_thu_hai_phai_nam_sau_co():
    """Cung du lieu, nhung co bat MUON hon nen day thu hai -> khong vao lenh."""
    rows = [
        (100,  99,   100,  50, 50),
        (105, 100,   104,  75, 50),
        (111, 104,   110,  72, 50),
        (110, 105,   106,  45,  5),   # cDn50 + mo leg LOW cung nen 3
        (106, 102,   103,  45,  8),
        (105, 102,   104,  45, 95),   # swing low 1 = 102
        (105, 103,   104,  45,  5),
        (104, 103.5, 104,  45,  8),
        (107, 104,   106,  45, 95),   # swing low 2 = 103, day o nen 6
    ]
    bars = [Bar(h, l, c, x, f, 1.0) for h, l, c, x, f in rows]
    assert len(run(bars, n=1, p=Params(require_after_flag=True))["trades"]) == 1
    # day thu hai o nen 6 >= co bat o nen 3 -> van vao. Doi co sang muon hon:
    bars[3] = Bar(110, 105, 106, 45, 5, 1.0)
    p = Params(require_after_flag=True)
    out = run(bars, n=1, p=p)
    assert all(t["bar"] >= 3 for t in out["trades"])


def test_loai_vi_rr_duoi_nguong():
    rows = [
        (100,  99,   100,  50, 50),
        (105, 100,   104,  75, 50),
        (106, 104,   105,  72, 50),   # dinh cho kill chi 106
        (105, 104,   104,  45, 50),
        (104, 100,   101,  45,  5),
        (103,  99,   100,  45,  8),
        (104, 100,   103,  45, 95),   # swing low 1 = 99
        (105, 101,   104,  45,  5),
        (104, 100.5, 103,  45,  8),
        (105, 103,   104,  45, 95),   # swing low 2 = 100.5, entry 104
    ]
    bars = [Bar(h, l, c, x, f, 1.0) for h, l, c, x, f in rows]
    out = run(bars, n=1, p=Params(min_rr=1.0))
    # rr = (106 - 104) / (104 - 100.3) = 2 / 3.7 = 0.54 -> bi loai
    assert out["trades"] == []
    assert len(out["rejects"]) == 1
    assert abs(out["rejects"][0]["rr"] - 2.0 / 3.7) < 1e-9
```

- [ ] **Step 2: Chạy test để chắc chắn fail**

```bash
cd "<scratchpad>" && python -m pytest kp_test.py -x -q
```

Kỳ vọng: FAIL với `ImportError: cannot import name 'Swing'`.

- [ ] **Step 3: Viết tầng swing**

Thêm vào `kp_oracle.py`:

```python
F_HI, F_LO = 90.0, 10.0


@dataclass
class Swing:
    seg: int = 0
    seg_high: float = NAN
    seg_high_bar: int = -1
    seg_low: float = NAN
    seg_low_bar: int = -1
    last_low: float = NAN
    last_low_bar: int = -1
    prev_low: float = NAN
    prev_low_bar: int = -1
    last_high: float = NAN
    last_high_bar: int = -1
    prev_high: float = NAN
    prev_high_bar: int = -1


def swing_step(st, bars, i):
    b = bars[i]
    prev = bars[i - 1].fast_rsi if i > 0 else NAN
    cur = b.fast_rsi
    f_up = prev <= F_HI < cur
    f_dn = prev >= F_LO > cur
    low_conf = high_conf = False

    # noi cuc tri truoc: nen bien thuoc ca hai leg
    if st.seg == 1 and (math.isnan(st.seg_high) or b.high > st.seg_high):
        st.seg_high, st.seg_high_bar = b.high, i
    if st.seg == -1 and (math.isnan(st.seg_low) or b.low < st.seg_low):
        st.seg_low, st.seg_low_bar = b.low, i

    if f_up:
        if st.seg == -1:
            low_conf = True
            st.prev_low, st.prev_low_bar = st.last_low, st.last_low_bar
            st.last_low, st.last_low_bar = st.seg_low, st.seg_low_bar
        if st.seg != 1:                      # chi chuyen leg that su moi reset
            st.seg_high, st.seg_high_bar = b.high, i
        st.seg = 1

    if f_dn:
        if st.seg == 1:
            high_conf = True
            st.prev_high, st.prev_high_bar = st.last_high, st.last_high_bar
            st.last_high, st.last_high_bar = st.seg_high, st.seg_high_bar
        if st.seg != -1:
            st.seg_low, st.seg_low_bar = b.low, i
        st.seg = -1

    return low_conf, high_conf
```

- [ ] **Step 4: Viết tín hiệu, mô phỏng vị thế và bộ đếm**

Thêm vào `kp_oracle.py`:

```python
@dataclass
class Params:
    hl_margin_atr: float = 0.0
    sl_atr_mult: float = 0.2
    min_rr: float = 1.0
    max_rr: float = 0.0
    require_after_flag: bool = True
    one_trade_per_flag: bool = True
    enable_buy: bool = True
    enable_sell: bool = True


def _new_counter():
    return {"flags": 0, "kill": 0, "kill_entered": 0, "kill_missed": 0,
            "rsiout": 0, "newlevel": 0}


def run(bars, n, p):
    ctx, sw = Ctx(), Swing()
    ev, trades, rejects = [], [], []
    counters = {"BUY": _new_counter(), "SELL": _new_counter()}
    pos = None          # dict side/sl/tp hoac None

    for i, b in enumerate(bars):
        before = len(ev)
        ctx_step(ctx, bars, i, n, ev)
        for bar, tag, why in ev[before:]:
            side = "BUY" if tag.startswith("FLAG_BUY") else "SELL"
            if tag.endswith("_ON"):
                counters[side]["flags"] += 1
            else:
                used = ctx.flag_buy_used if side == "BUY" else ctx.flag_sell_used
                if why == "KILL":
                    counters[side]["kill"] += 1
                    counters[side]["kill_entered" if used else "kill_missed"] += 1
                elif why == "RSIOUT":
                    counters[side]["rsiout"] += 1
                else:
                    counters[side]["newlevel"] += 1

        # thoat vi the truoc khi xet tin hieu moi
        if pos is not None:
            if pos["side"] == "BUY" and (b.low <= pos["sl"] or b.high >= pos["tp"]):
                pos = None
            elif pos["side"] == "SELL" and (b.high >= pos["sl"] or b.low <= pos["tp"]):
                pos = None

        low_conf, high_conf = swing_step(sw, bars, i)

        if low_conf and p.enable_buy and ctx.flag_buy and pos is None \
                and not math.isnan(sw.prev_low):
            hl = sw.last_low > sw.prev_low + p.hl_margin_atr * b.atr
            after = (not p.require_after_flag) or sw.last_low_bar >= ctx.flag_buy_bar
            free = not (p.one_trade_per_flag and ctx.flag_buy_used)
            e, s, t = b.close, sw.last_low - p.sl_atr_mult * b.atr, ctx.kill_high
            if hl and after and free and e - s > 0:
                rr = (t - e) / (e - s)
                if rr >= p.min_rr and (p.max_rr <= 0 or rr <= p.max_rr):
                    ctx.flag_buy_used = True
                    trades.append({"side": "BUY", "bar": i, "entry": e,
                                   "sl": s, "tp": t, "rr": rr})
                    pos = {"side": "BUY", "sl": s, "tp": t}
                else:
                    rejects.append({"side": "BUY", "bar": i, "rr": rr})

        if high_conf and p.enable_sell and ctx.flag_sell and pos is None \
                and not math.isnan(sw.prev_high):
            lh = sw.last_high < sw.prev_high - p.hl_margin_atr * b.atr
            after = (not p.require_after_flag) or sw.last_high_bar >= ctx.flag_sell_bar
            free = not (p.one_trade_per_flag and ctx.flag_sell_used)
            e, s, t = b.close, sw.last_high + p.sl_atr_mult * b.atr, ctx.kill_low
            if lh and after and free and s - e > 0:
                rr = (e - t) / (s - e)
                if rr >= p.min_rr and (p.max_rr <= 0 or rr <= p.max_rr):
                    ctx.flag_sell_used = True
                    trades.append({"side": "SELL", "bar": i, "entry": e,
                                   "sl": s, "tp": t, "rr": rr})
                    pos = {"side": "SELL", "sl": s, "tp": t}
                else:
                    rejects.append({"side": "SELL", "bar": i, "rr": rr})

    return {"trades": trades, "rejects": rejects, "counters": counters,
            "events": ev}
```

- [ ] **Step 5: Chạy toàn bộ test**

```bash
cd "<scratchpad>" && python -m pytest kp_test.py -q
```

Kỳ vọng: 10 passed. Bất kỳ cái nào đỏ thì sửa oracle, **không** sửa test — test là spec viết bằng code.

- [ ] **Step 6: In bảng tham chiếu để soát chéo ở Task 9**

Tách kịch bản của `test_tin_hieu_buy_day_du` ra hằng số module `SCENARIO_BUY` trong `kp_oracle.py` (list các tuple `(high, low, close, ctx, fast)`), cho cả test lẫn script này cùng đọc — một nguồn sự thật. Rồi:

```bash
cd "<scratchpad>" && python -c "
import json
from kp_oracle import Bar, Params, run, SCENARIO_BUY
out = run([Bar(*r, 1.0) for r in SCENARIO_BUY], n=1, p=Params())
print(json.dumps({'trades': out['trades'],
                  'counters': out['counters']['BUY'],
                  'events': out['events']}, indent=2))
" > kp_reference.json && cat kp_reference.json
```

Kỳ vọng: một lệnh BUY ở nến 10 với `entry 106.0 / sl 102.8 / tp 111.0`, `counters` có `kill_entered: 1` và `kill_missed: 0`. Giữ file này lại — Task 9 soát Pine dựa vào nó.

---

## Task 4: Pine indicator — khung, inputs, tầng M5

**Files:**
- Create: `pine/kill_peak_indicator.pine`

**Interfaces:**
- Produces (biến top level mà Task 5–7 đọc): `ctxRsi, atr, n, seedHigh, seedLow`, toàn bộ state spec §3.2, và hai biến chỉ set ở nến cờ tắt: `string buyEnd`, `string sellEnd`.

- [ ] **Step 1: Viết header + khai báo + inputs**

Header theo đúng kiểu các file trong `pine/`: khối `// ===` mở đầu, tóm tắt cấu trúc, mốc, tín hiệu, SL/TP, và **ghi rõ hai điều** — file này khác `rsi2_swing`/`rsi2_ema_swing` ở luật reset leg (xem spec §4.1), và RR thật lệch chút so với RR đã qua cửa `minRR` vì lệnh khớp ở open nến sau.

Inputs viết đúng như dưới đây — tên và giá trị mặc định là hợp đồng với spec §9, đừng đổi:

```pine
//@version=6
indicator("Kill Peak — Dinh Cho Kill", overlay=true,
     max_lines_count=500, max_labels_count=500)

grpCtx = "Boi canh (HTF)"
htfTf  = input.timeframe("5", "Khung boi canh", group=grpCtx)
ctxLen = input.int(14,   "RSI boi canh", minval=2, group=grpCtx)
ctxHi  = input.float(70, "Moc mo doan do", group=grpCtx)
ctxMid = input.float(50, "Moc chot muc + bat co", group=grpCtx)
ctxLo  = input.float(30, "Moc huy co", group=grpCtx)

grpSw   = "Swing (khung chart)"
fastLen = input.int(2,    "RSI nhanh", minval=1, group=grpSw)
fHi     = input.float(90, "Moc tren", group=grpSw)
fLo     = input.float(10, "Moc duoi", group=grpSw)

grpEntry               = "Vao lenh"
enableBuy              = input.bool(true,  "Enable BUY",  group=grpEntry)
enableSell             = input.bool(true,  "Enable SELL", group=grpEntry)
hlMarginAtr            = input.float(0.0,  "Bien higher low (x ATR)", minval=0, step=0.1, group=grpEntry)
requireSwing2AfterFlag = input.bool(true,  "Swing thu hai phai nam sau co", group=grpEntry,
     tooltip="Nen DAY cua swing thu hai phai o sau nen bat co. Swing thu nhat duoc phep nam truoc.")
oneTradePerFlag        = input.bool(true,  "Mot co toi da mot lenh", group=grpEntry)

grpRisk    = "Rui ro"
atrLen     = input.int(14,   "ATR length", minval=1, group=grpRisk)
slAtrMult  = input.float(0.2, "SL bien (x ATR)", minval=0, step=0.1, group=grpRisk)
minRR      = input.float(1.0, "RR toi thieu", minval=0, step=0.5, group=grpRisk)
maxRR      = input.float(0.0, "RR toi da (0 = khong chan)", minval=0, step=1.0, group=grpRisk)

grpShow      = "Hien thi"
showCtx      = input.bool(true,  "Doan do + muc cho kill", group=grpShow)
showSwings   = input.bool(true,  "Cham swing", group=grpShow)
showZigzag   = input.bool(true,  "Zigzag", group=grpShow)
showSignals  = input.bool(true,  "Tin hieu + SL/TP", group=grpShow)
showRejected = input.bool(true,  "Tin hieu bi loai vi RR", group=grpShow)
showTable    = input.bool(true,  "Bang trang thai", group=grpShow)
showCounters = input.bool(true,  "Bang dem", group=grpShow)
```

File strategy (Task 8) dùng y hệt khối này, thay dòng `indicator(...)` và thêm nhóm `grpExec` với `riskPct = input.float(1.0, ...)` và `minSlTicks = input.int(10, ...)`.

- [ ] **Step 2: Viết khối bối cảnh — security, n, seed, guard**

```pine
float ctxRsi = request.security(syminfo.tickerid, htfTf, ta.rsi(close, ctxLen)[1],
     barmerge.gaps_off, barmerge.lookahead_on)

int   n   = math.max(1, int(math.round(timeframe.in_seconds(htfTf) / timeframe.in_seconds())))
float atr = ta.atr(atrLen)

// ta.* phai goi o top level, khong duoc nam trong if — chung giu state noi bo
float seedHigh = ta.highest(high, n)
float seedLow  = ta.lowest(low, n)

if barstate.isfirst and timeframe.in_seconds(htfTf) <= timeframe.in_seconds()
    runtime.error("Khung boi canh phai lon hon khung chart")
```

- [ ] **Step 3: Viết state và sự kiện**

```pine
var bool   measHi      = false
var float  runHigh     = na
var float  killHigh    = na
var int    killHighBar = na
var bool   flagBuy     = false
var int    flagBuyBar  = na
var bool   flagBuyUsed = false

var bool   measLo       = false
var float  runLow       = na
var float  killLow      = na
var int    killLowBar   = na
var bool   flagSell     = false
var int    flagSellBar  = na
var bool   flagSellUsed = false

string buyEnd  = na          // chi khac na dung o nen co tat
string sellEnd = na

bool ctxOk = not na(ctxRsi) and not na(ctxRsi[1])
bool cUp70 = ctxOk and ctxRsi[1] <= ctxHi  and ctxRsi > ctxHi
bool cDn50 = ctxOk and ctxRsi[1] >= ctxMid and ctxRsi < ctxMid
bool cUp50 = ctxOk and ctxRsi[1] <= ctxMid and ctxRsi > ctxMid
bool cDn30 = ctxOk and ctxRsi[1] >= ctxLo  and ctxRsi < ctxLo
```

- [ ] **Step 4: Viết sáu bước theo đúng thứ tự spec §3.3**

```pine
// 1. noi cuc tri
if measHi
    runHigh := math.max(runHigh, high)
if measLo
    runLow := math.min(runLow, low)

// 2. cham muc
if flagBuy and high >= killHigh
    flagBuy := false
    buyEnd  := "KILL"
if flagSell and low <= killLow
    flagSell := false
    sellEnd  := "KILL"

// 3. cDn50 -> chot dinh cho kill
if cDn50 and measHi
    killHigh    := runHigh
    killHighBar := bar_index
    measHi      := false
    flagBuy     := true
    flagBuyBar  := bar_index
    flagBuyUsed := false

// 4. cUp50 -> chot day cho kill
if cUp50 and measLo
    killLow     := runLow
    killLowBar  := bar_index
    measLo      := false
    flagSell    := true
    flagSellBar := bar_index
    flagSellUsed := false

// 5. cDn30
if cDn30
    if flagBuy
        flagBuy := false
        buyEnd  := "RSIOUT"
    if flagSell
        flagSell := false
        sellEnd  := "NEWLEVEL"
    if not measLo
        measLo := true
        runLow := seedLow

// 6. cUp70
if cUp70
    if flagSell
        flagSell := false
        sellEnd  := "RSIOUT"
    if flagBuy
        flagBuy := false
        buyEnd  := "NEWLEVEL"
    if not measHi
        measHi  := true
        runHigh := seedHigh
```

- [ ] **Step 5: Chạy static checker**

```bash
python "<scratchpad>/kp_check.py" "pine/kill_peak_indicator.pine"
```

Kỳ vọng: `SACH`, exit 0.

- [ ] **Step 6: Đối chiếu từng dòng với `ctx_step` của oracle**

Mở `kp_oracle.py` cạnh file Pine, so sáu bước. Checklist phải đúng cả sáu:
thứ tự bước · `seedHigh`/`seedLow` dùng đúng chỗ · `flagBuyUsed` reset lúc cờ bật · ba chuỗi lý do viết đúng · nhánh `NEWLEVEL` có ở **cả hai** bước 5 và 6 · `if not measLo` chứ không phải `if measLo`.

- [ ] **Step 7: Commit**

```bash
git add pine/kill_peak_indicator.pine
git commit -m "feat(pine): kill_peak indicator - tang boi canh M5"
```

---

## Task 5: Pine indicator — tầng swing M1, vị thế mô phỏng, tín hiệu

**Files:**
- Modify: `pine/kill_peak_indicator.pine`

**Interfaces:**
- Consumes: state tầng M5 từ Task 4.
- Produces: `lowConf, highConf, lastLowP, lastLowBar, prevLowP, lastHighP, lastHighBar, prevHighP`, và `buySig, buyEntry, buySl, buyTp, buyRr, buyRejRr` + bộ mirror `sell*`.

- [ ] **Step 1: Chép khối cấu trúc leg từ file divergence**

Lấy từ `pine/rsi2_divergence_indicator.pine` khối `seg`/`segHigh`/`segLow` + `fUp`/`fDn`, **bỏ hết** phần nến neo (`bullBar`, `bullRsi`, `bullHigh`, `bearBar`, `bearRsi`, `bearLow`, `segHighRsi`, `segHighAnc`, `segHighAncPx` và các bản mirror). Giữ nguyên hai dòng `if seg != 1` / `if seg != -1` — đó là bản vá, đặt **trước** `seg := 1` / `seg := -1` để cả hai kiểm tra đều đọc `seg` cũ.

Đổi tên biến lưu swing cho khớp spec §4.3: `lastLowP, lastLowBar, prevLowP, prevLowBar` và mirror.

- [ ] **Step 2: Viết mô phỏng vị thế**

Indicator không có `strategy.*` nên phải tự theo dõi, vừa để chặn tín hiệu chồng vừa để bảng đếm biết "đã kịp vào lệnh".

```pine
var bool  posOpen = false
var int   posDir  = 0            // 1 = long, -1 = short
var float posSl   = na
var float posTp   = na

// thoat truoc khi xet tin hieu moi
if posOpen
    bool hitLong  = posDir ==  1 and (low  <= posSl or high >= posTp)
    bool hitShort = posDir == -1 and (high >= posSl or low  <= posTp)
    if hitLong or hitShort
        posOpen := false
        posDir  := 0
```

- [ ] **Step 3: Viết khối tín hiệu BUY**

```pine
bool  buySig    = false
bool  buyRejRr  = false
float buyEntry  = na
float buySl     = na
float buyTp     = na
float buyRr     = na

if lowConf and enableBuy and flagBuy and not posOpen and not na(prevLowP) and not na(atr)
    bool  hl    = lastLowP > prevLowP + hlMarginAtr * atr
    bool  after = not requireSwing2AfterFlag or lastLowBar >= flagBuyBar
    bool  free  = not (oneTradePerFlag and flagBuyUsed)
    float e     = close
    float s     = lastLowP - slAtrMult * atr
    float t     = killHigh
    if hl and after and free and e - s > 0
        float r = (t - e) / (e - s)
        if r >= minRR and (maxRR <= 0 or r <= maxRR)
            buySig      := true
            buyEntry    := e
            buySl       := s
            buyTp       := t
            buyRr       := r
            flagBuyUsed := true
            posOpen     := true
            posDir      := 1
            posSl       := s
            posTp       := t
        else
            buyRejRr := true
            buyRr    := r
```

- [ ] **Step 4: Viết khối tín hiệu SELL soi gương**

Giống hệt với: `highConf`, `enableSell`, `flagSell`, `prevHighP`; `lh = lastHighP < prevHighP - hlMarginAtr * atr`; `after` dùng `lastHighBar >= flagSellBar`; `free` dùng `flagSellUsed`; `s = lastHighP + slAtrMult * atr`; `t = killLow`; điều kiện `s - e > 0`; `r = (e - t) / (s - e)`; `posDir := -1`.

- [ ] **Step 5: Chạy static checker**

```bash
python "<scratchpad>/kp_check.py" "pine/kill_peak_indicator.pine"
```

Kỳ vọng: `SACH`.

- [ ] **Step 6: Đối chiếu với `swing_step` và `run` của oracle**

Checklist: nới cực trị chạy **trước** khi xét `fUp`/`fDn` · `prevLowP` gán **trước** `lastLowP` · `if seg != 1` nằm trước `seg := 1` · thứ tự sáu điều kiện BUY khớp spec §5 · `flagBuyUsed := true` chỉ đặt khi tín hiệu thật sự nổ, không đặt ở nhánh bị loại vì RR.

- [ ] **Step 7: Commit**

```bash
git add pine/kill_peak_indicator.pine
git commit -m "feat(pine): kill_peak indicator - tang swing M1 va tin hieu"
```

---

## Task 6: Pine indicator — vẽ

**Files:**
- Modify: `pine/kill_peak_indicator.pine`

**Interfaces:**
- Consumes: mọi thứ từ Task 4–5.
- Produces: không có biến nào cho task sau; thuần hiển thị. Mọi khối phải nằm trong `if show*` tương ứng.

- [ ] **Step 1: Bối cảnh — nền và đường mức chờ kill**

```pine
bgcolor(showCtx and measHi ? color.new(color.red, 94) : na, title="Dang do dinh")
bgcolor(showCtx and measLo ? color.new(color.teal, 94) : na, title="Dang do day")

var line  killHiLn  = na
var label killHiLb  = na

if showCtx and cDn50 and not na(killHigh) and killHighBar == bar_index
    killHiLn := line.new(bar_index, killHigh, bar_index + 1, killHigh,
         color=color.new(color.orange, 0), width=2)
    killHiLb := label.new(bar_index, killHigh, "DINH CHO KILL " + str.tostring(killHigh, format.mintick),
         style=label.style_label_left, color=color.new(color.orange, 85),
         textcolor=color.orange, size=size.small)
if flagBuy and not na(killHiLn)
    line.set_x2(killHiLn, bar_index)
if not na(buyEnd) and not na(killHiLn)
    line.set_x2(killHiLn, bar_index)
    label.new(bar_index, killHigh, buyEnd, style=label.style_label_up,
         color=color.new(color.orange, 70), textcolor=color.orange, size=size.tiny)
```

Mirror cho `killLow` với `cUp50`, `killLowBar`, `flagSell`, `sellEnd`, màu teal.

- [ ] **Step 2: Swing và zigzag**

Chấm tại nến cực trị thật: khi `lowConf` thì `label.new(lastLowBar, lastLowP, ...)` với `style=label.style_label_up`, text là giá. Zigzag: giữ `var int lastPivotBar` / `var float lastPivotPx`, mỗi lần có `lowConf` hoặc `highConf` thì `line.new` từ pivot trước tới pivot mới rồi cập nhật.

Đường higher low: khi `lowConf and flagBuy and not na(prevLowP)`, nối `prevLowBar/prevLowP` tới `lastLowBar/lastLowP`. Xanh dày (`width=2`) + label `"HIGHER LOW " + str.tostring(prevLowP, format.mintick) + " -> " + str.tostring(lastLowP, format.mintick)` nếu là higher low thật; xám mảnh (`width=1`, `color.new(color.gray, 40)`) nếu không. Mirror cho high.

- [ ] **Step 3: Tín hiệu, SL/TP và nhãn bị loại**

```pine
plotshape(showSignals and buySig,  title="BUY",  style=shape.triangleup,
     location=location.belowbar, color=color.new(color.teal, 0), size=size.small)
plotshape(showSignals and sellSig, title="SELL", style=shape.triangledown,
     location=location.abovebar, color=color.new(color.red, 0), size=size.small)

var line slLn = na
var line tpLn = na

if showSignals and (buySig or sellSig)
    float s = buySig ? buySl : sellSl
    float t = buySig ? buyTp : sellTp
    float r = buySig ? buyRr : sellRr
    slLn := line.new(bar_index, s, bar_index + 1, s, color=color.new(color.red, 0),
         width=1, style=line.style_dashed)
    tpLn := line.new(bar_index, t, bar_index + 1, t, color=color.new(color.orange, 0),
         width=1, style=line.style_dashed)
    label.new(bar_index, s, "R:R " + str.tostring(r, "#.##"),
         style=label.style_label_up, color=color.new(color.gray, 80),
         textcolor=color.gray, size=size.tiny)
if posOpen
    line.set_x2(slLn, bar_index)
    line.set_x2(tpLn, bar_index)

if showRejected and (buyRejRr or sellRejRr)
    float r = buyRejRr ? buyRr : sellRr
    label.new(bar_index, close, "RR " + str.tostring(r, "#.##") + " < min",
         style=label.style_label_left, color=color.new(color.gray, 85),
         textcolor=color.gray, size=size.tiny)
```

- [ ] **Step 4: Chạy static checker**

```bash
python "<scratchpad>/kp_check.py" "pine/kill_peak_indicator.pine"
```

Kỳ vọng: `SACH`. Kiểm thêm bằng mắt: mọi dòng nối tiếp thụt 5 hoặc 9 space, không phải 4 hay 8.

- [ ] **Step 5: Kiểm số đối tượng vẽ**

Đếm số `label.new` và `line.new` trong file. Mỗi cái đều phải nằm sau một `if show*`. Nếu tổng vượt 500 trên chart dài thì tăng `max_lines_count`/`max_labels_count` ở dòng `indicator(...)` — Pine chặn cứng ở 500.

```bash
grep -c "label.new\|line.new" pine/kill_peak_indicator.pine
grep -n "max_lines_count\|max_labels_count" pine/kill_peak_indicator.pine
```

- [ ] **Step 6: Commit**

```bash
git add pine/kill_peak_indicator.pine
git commit -m "feat(pine): kill_peak indicator - ve boi canh, swing va tin hieu"
```

---

## Task 7: Pine indicator — hai bảng

**Files:**
- Modify: `pine/kill_peak_indicator.pine`

**Interfaces:**
- Consumes: mọi thứ từ Task 4–6.
- Produces: `cntFlags`, `cntKill`, `cntKillIn`, `cntRsiOut`, `cntNewLevel` — mỗi cái hai chiều.

- [ ] **Step 1: Bộ đếm**

```pine
var int cntFlagsB = 0
var int cntKillB  = 0
var int cntKillInB = 0
var int cntRsiOutB = 0
var int cntNewLvlB = 0

if cDn50 and flagBuyBar == bar_index
    cntFlagsB += 1
if buyEnd == "KILL"
    cntKillB += 1
    if flagBuyUsed
        cntKillInB += 1
if buyEnd == "RSIOUT"
    cntRsiOutB += 1
if buyEnd == "NEWLEVEL"
    cntNewLvlB += 1
```

Mirror cho SELL với `cUp50`, `flagSellBar`, `sellEnd`, `flagSellUsed`.

Đặt khối này **ngay sau** khối sáu bước của Task 4, trước khối tín hiệu — vì `flagBuyUsed` bị khối tín hiệu ghi đè trong cùng nến, mà bộ đếm cần giá trị lúc cờ tắt.

- [ ] **Step 2: Bảng trạng thái**

`table.new(position.top_right, 2, 9)`, vẽ trong `if showTable and barstate.islast`. Chín hàng theo spec §7: `TF chart / HTF` · `RSI boi canh` · `Trang thai M5` · `RSI(2)` · `Swing low gan nhat` · `Swing low truoc` · `Swing high gan nhat` · `Swing high truoc` · `Tin hieu gan nhat`.

Chuỗi trạng thái M5:

```pine
string ctxState = measHi ? "DANG DO DINH" :
     measLo ? "DANG DO DAY" :
     flagBuy ? "CHO KILL " + str.tostring(killHigh, format.mintick) + ", " + str.tostring(bar_index - flagBuyBar) + " nen" :
     flagSell ? "CHO KILL DAY " + str.tostring(killLow, format.mintick) + ", " + str.tostring(bar_index - flagSellBar) + " nen" :
     "—"
```

- [ ] **Step 3: Bảng đếm**

`table.new(position.bottom_right, 3, 7)` trong `if showCounters and barstate.islast`. Cột: chỉ tiêu · BUY · SELL. Bảy hàng: tiêu đề · `co da bat` · `ket thuc vi KILL` · `da kip vao lenh` · `KILL MA HUT` · `chet vi RSIOUT` · `chet vi NEWLEVEL`.

`KILL MA HUT = cntKillB - cntKillInB`. Tô hàng này đậm hơn — đó là con số để so với v1.

- [ ] **Step 4: Chạy static checker**

```bash
python "<scratchpad>/kp_check.py" "pine/kill_peak_indicator.pine"
```

Kỳ vọng: `SACH`.

- [ ] **Step 5: Kiểm vị trí khối đếm**

```bash
grep -n "cntFlagsB\|buySig    = false\|flagBuyUsed := true" pine/kill_peak_indicator.pine
```

Kỳ vọng: dòng `cntFlagsB` nhỏ hơn dòng `buySig = false`. Ngược lại thì `cntKillInB` sẽ đếm sai.

- [ ] **Step 6: Commit**

```bash
git add pine/kill_peak_indicator.pine
git commit -m "feat(pine): kill_peak indicator - bang trang thai va bang dem"
```

---

## Task 8: Pine strategy

**Files:**
- Create: `pine/kill_peak_strategy.pine`

**Interfaces:**
- Consumes: không có — file độc lập, chép khối tín hiệu từ indicator.
- Produces: không có.

- [ ] **Step 1: Chép nền từ indicator**

Chép `pine/kill_peak_indicator.pine` sang file mới, giữ nguyên Task 4 + Task 5 (tầng M5, tầng swing, tín hiệu), **bỏ** toàn bộ Task 6 (vẽ) trừ `plotshape` tín hiệu, và giữ bảng đếm của Task 7, bỏ bảng trạng thái chi tiết.

Đổi dòng khai báo:

```pine
strategy("Kill Peak Strategy", overlay=true, initial_capital=10000,
     default_qty_type=strategy.fixed, currency=currency.NONE,
     commission_type=strategy.commission.percent, commission_value=0.0,
     process_orders_on_close=false)
```

Header phải ghi rõ: file này khác `rsi2_divergence_strategy` ở chỗ **không** cần trò huỷ-rồi-đặt-lại `strategy.exit`, vì SL và TP đều là mức giá cố định chứ không phải bội số R.

- [ ] **Step 2: Thay mô phỏng vị thế bằng `strategy.*`**

Bỏ `posOpen`/`posDir`/`posSl`/`posTp`. Điều kiện `not posOpen` trong khối tín hiệu đổi thành `strategy.position_size == 0`. Bộ đếm `cntKillInB` vẫn đọc `flagBuyUsed` nên không đổi.

- [ ] **Step 3: Sizing và đặt lệnh**

Chép công thức từ `pine/rsi2_ema_swing_strategy.pine` (tìm `riskPct`, `minSlTicks`, `syminfo.mintick`, `syminfo.pointvalue`), giữ nguyên cách tính số lot từ `riskPct` và khoảng cách entry→SL, giữ nguyên guard `minSlTicks`.

File sibling **không** có hàm helper — sizing viết thẳng inline (xem `pine/rsi2_ema_swing_strategy.pine:191-199`). Giữ đúng kiểu đó:

```pine
if buySig
    float slDist  = buyEntry - buySl
    bool  tooClose = minSlTicks > 0 and slDist < minSlTicks * syminfo.mintick
    if not tooClose and slDist > 0
        float riskUsd = strategy.equity * riskPct / 100.0
        float qty     = riskUsd / (slDist * syminfo.pointvalue)
        strategy.entry("L", strategy.long, qty=qty, comment="BUY kill peak")
        strategy.exit("LX", from_entry="L", stop=buySl, limit=buyTp)
    else if tooClose
        label.new(bar_index, low, "BUY skipped: SL too close", style=label.style_label_up,
             color=color.new(color.gray, 40), textcolor=color.white, size=size.tiny)

if sellSig
    float slDist  = sellSl - sellEntry
    bool  tooClose = minSlTicks > 0 and slDist < minSlTicks * syminfo.mintick
    if not tooClose and slDist > 0
        float riskUsd = strategy.equity * riskPct / 100.0
        float qty     = riskUsd / (slDist * syminfo.pointvalue)
        strategy.entry("S", strategy.short, qty=qty, comment="SELL kill peak")
        strategy.exit("SX", from_entry="S", stop=sellSl, limit=sellTp)
    else if tooClose
        label.new(bar_index, high, "SELL skipped: SL too close", style=label.style_label_down,
             color=color.new(color.gray, 40), textcolor=color.white, size=size.tiny)
```

Khác `rsi2_ema_swing` ở hai chỗ, cả hai đều có lý do: không có `blockOpp` (spec §5 điều v đã chốt luôn bỏ qua tín hiệu ngược khi đang có lệnh, không có tuỳ chọn đảo lệnh), và `limit=` nhận thẳng `buyTp`/`sellTp` chứ không phải `close ± tpR * slDist` — nên **không** có `lArm`/`sArm`/`lSigBar` và toàn bộ khối re-arm ở nến sau. Xoá hết chúng khi chép.

- [ ] **Step 4: Alert**

Chép mẫu JSON từ `pine/rsi2_ema_swing_strategy.pine`, đổi trường setup thành `"setup":"KILLPEAK"` và thêm `"tp_level"` (mức chờ kill) bên cạnh `sl`. Dùng `alert(..., alert.freq_once_per_bar_close)`.

Chuỗi JSON viết bằng **nháy đơn** bao ngoài để chứa nháy kép bên trong, y như các file sibling.

- [ ] **Step 5: Chạy static checker**

```bash
python "<scratchpad>/kp_check.py" "pine/kill_peak_strategy.pine"
```

Kỳ vọng: `SACH`. Nếu báo "so nhay-kep le" ở dòng alert thì đọc lại dòng đó — checker đã bỏ chuỗi nháy đơn trước khi đếm nên báo ở đây là lỗi thật.

- [ ] **Step 6: Kiểm khối tín hiệu hai file khớp nhau**

```bash
diff <(sed -n '/KHOI TIN HIEU/,/HET KHOI TIN HIEU/p' pine/kill_peak_indicator.pine) \
     <(sed -n '/KHOI TIN HIEU/,/HET KHOI TIN HIEU/p' pine/kill_peak_strategy.pine)
```

Đánh dấu khối tín hiệu trong cả hai file bằng hai comment mốc `// ---- KHOI TIN HIEU ----` và `// ---- HET KHOI TIN HIEU ----` để lệnh trên chạy được. Khác biệt duy nhất được phép: `not posOpen` ↔ `strategy.position_size == 0`.

- [ ] **Step 7: Commit**

```bash
git add pine/kill_peak_strategy.pine
git commit -m "feat(pine): kill_peak strategy - sizing, exit muc co dinh, alert"
```

---

## Task 9: Soát chéo cuối và bàn giao

**Files:**
- Modify: `pine/kill_peak_indicator.pine` (chỉ nếu soát ra lỗi)
- Modify: `pine/kill_peak_strategy.pine` (chỉ nếu soát ra lỗi)

- [ ] **Step 1: Static check cả hai file**

```bash
python "<scratchpad>/kp_check.py" "pine/kill_peak_indicator.pine" "pine/kill_peak_strategy.pine"
```

Kỳ vọng: `SACH`.

- [ ] **Step 2: Chạy lại toàn bộ test oracle**

```bash
cd "<scratchpad>" && python -m pytest kp_test.py -q
```

Kỳ vọng: 10 passed.

- [ ] **Step 3: Soát chéo mười điểm**

Đọc song song `kp_oracle.py` và hai file Pine, xác nhận từng điểm:

1. Sáu bước §3.3 đúng thứ tự, `cDn50` trước `cDn30`, `cUp50` trước `cUp70`.
2. `NEWLEVEL` xuất hiện ở **cả** bước 5 (giết cờ SELL) lẫn bước 6 (giết cờ BUY).
3. `seedHigh`/`seedLow` tính ở top level, không nằm trong `if`.
4. `flagBuyUsed` reset lúc cờ bật, set lúc lệnh nổ, đọc bởi bộ đếm trước khi khối tín hiệu chạy.
5. Nới cực trị leg chạy trước khi xét `fUp`/`fDn`.
6. `if seg != 1` / `if seg != -1` nằm **trước** `seg := 1` / `seg := -1`.
7. `prevLowP` gán trước `lastLowP` (không thì cả hai bằng nhau).
8. Sáu điều kiện BUY đủ và đúng thứ tự theo spec §5.
9. Chiều SELL đảo đúng mọi dấu: `<` ↔ `>`, `+` ↔ `-`, `killLow` thay `killHigh`, `(e - t) / (s - e)`.
10. Không còn sót tên biến của khối nến neo (`bullRsi`, `bearRsi`, `segHighAnc`, …).
11. **Không repaint (spec §10).** Chỉ đúng một `request.security`, và nó phải có cả `[1]` lẫn `lookahead_on` — thiếu `[1]` là nhìn trộm tương lai. Không có `plot`/`label` nào đọc giá trị của nến chưa đóng rồi vẽ lùi về quá khứ. Mọi `label.new`/`line.new` đều dùng `bar_index` hiện tại hoặc một bar index đã chốt (`lastLowBar`, `killHighBar`), không bao giờ `bar_index + k` với `k > 1`.

```bash
grep -n "bullRsi\|bearRsi\|segHighAnc\|segLowAnc\|AncPx" pine/kill_peak_*.pine
grep -c "request.security" pine/kill_peak_indicator.pine pine/kill_peak_strategy.pine
grep -n "request.security" pine/kill_peak_*.pine
```

Kỳ vọng: lệnh đầu không có kết quả; lệnh hai in `1` cho mỗi file; lệnh ba cho thấy cả hai dòng đều có `[1]` và `lookahead_on`.

- [ ] **Step 4: Commit sửa lỗi nếu có**

```bash
git add pine/kill_peak_indicator.pine pine/kill_peak_strategy.pine
git commit -m "fix(pine): kill_peak - sua cac diem lech phat hien khi soat cheo"
```

Không có lỗi thì bỏ qua step này.

- [ ] **Step 5: Báo cáo bàn giao**

Nói đúng những gì đã làm, không hơn:

- Hai file Pine đã viết, đã qua static check, đã đối chiếu với oracle Python có 10 test xanh.
- **Chưa compile.** Máy này không chạy được Pine. Bước tiếp theo là dán vào TradingView, sửa lỗi compile nếu có, rồi test tay.
- Chỉ ra cho người dùng ba thứ cần nhìn đầu tiên trên chart: nền đoạn đo có bật đúng lúc RSI(14) M5 vượt 70 không · label lý do tắt cờ có ra đủ ba loại không · dòng `KILL MA HUT` trong bảng đếm là bao nhiêu so với v1.
- Port Python, registry và tests vẫn nằm ngoài phạm vi (spec §12).
