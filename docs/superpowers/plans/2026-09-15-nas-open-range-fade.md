# NAS Open Range Fade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một indicator TradingView đánh dấu cú phá range hỏng của hai phiên NAS100 mở lúc 07:00 và 19:00 UTC+7.

**Architecture:** Hai file: một oracle Python dựng lại máy trạng thái, và một file Pine. Rủi ro số một là **thứ tự sáu bước trong một nến** — đặc biệt bước cập nhật mốc phải nằm CUỐI, nếu không một nến phá mà bản thân là nến đỏ sẽ tự lấy close của chính mình làm mốc. Vì Pine không compile được ở máy này, oracle được viết **trước** và bị mutation testing soi, rồi file Pine đối chiếu tay với nó.

**Tech Stack:** Pine Script v6; Python 3 + pytest cho oracle.

**Spec:** `docs/superpowers/specs/2026-09-15-nas-open-range-fade-design.md`

## Global Constraints

Đọc hết trước khi bắt đầu bất kì task nào.

- **KHÔNG COMPILE ĐƯỢC PINE Ở MÁY NÀY.** Không bao giờ viết "đã test", "đã chạy", "verified", "works" về code Pine. Chỉ được nói "qua checker tĩnh", "đối chiếu với oracle", "đọc tay".
- **Thụt dòng nối tiếp trong Pine phải KHÔNG chia hết cho 4.** Repo dùng 5, 9, 13. Thụt 4 hoặc 8 bị Pine đọc thành khối mới — không báo lỗi, chỉ đổi hành vi. Đây là *dòng nối tiếp*; thân khối ở 4/8/12 là bình thường.
- **Không gọi `ta.*` bên trong `if`** — chúng giữ state nội bộ, gọi trong nhánh điều kiện là sai âm thầm.
- **Không dùng `line.new(`.** Trần cứng 500 và khi tràn thì cái cũ nhất lặng lẽ biến mất — `kill_peak` đã mắc. Dùng `plot(..., style=plot.style_linebr)`.
- **`box` ĐƯỢC dùng** (spec §5.1 cho phép, người dùng yêu cầu range dạng box) và phải khai `max_boxes_count=500` tường minh.
- **Định dạng số trong alert là `"0.#####"`, KHÔNG phải `"#.#####"`.** Cái sau rụng số 0 đứng đầu (`DecimalFormat` của Java) nên sinh JSON hỏng trên instrument dưới 1.0.
- **Không đặt tên biến trùng nhau ở hai khối `if` anh em.** Pine v6 có thể từ chối khai báo lại ở scope anh em. Dùng tiền tố `u`/`d` cho mọi biến cục bộ của hai chiều.
- **Windows: xoá `__pycache__` trước mỗi lần chạy pytest.** Lệnh: `rm -rf __pycache__ tests/__pycache__ tests/pine_oracles/__pycache__ rsi_fvg/__pycache__`. Bytecode cũ đã gây chạy xanh giả trong repo này.
- **MỐC TEST: `416 passed, 2 failed`.** Hai ca đỏ là `tests/test_mt5_loader.py` — **lỗi MÔI TRƯỜNG, không phải lỗi code**: terminal MT5 đang chạy nên guard skip không kích hoạt, nhưng `symbol_info('XAUUSDc')` trả `None`. **Đừng sửa chúng, đừng tính chúng vào kết quả của mình.** Nếu số ca đỏ tăng quá 2, hoặc có ca đỏ ở file khác, DỪNG và báo.
- **`tests/pine_indent.py` và `tests/pine_blocks.py` KHÔNG tồn tại trên nhánh này.** Chúng nằm trên `feat/rsi-trend-pullback` chưa merge. Checker thụt dòng phải chạy TAY bằng lệnh awk trong Task 2. Đừng đi tìm chúng, đừng viết lại chúng — ngoài phạm vi.
- **Dùng công cụ Write cho nội dung file.** Heredoc bash trên máy này vỡ khi nội dung có nháy; chỉ khối `python - <<'PYEOF'` thuần Python là tin được.
- **Commit message:** tiếng Việt không dấu, ASCII, viết vào file `.txt` trong scratchpad rồi `git commit -F <file>`. Dòng cuối đúng nguyên văn:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- **Nhánh:** `feat/nas-open-range-fade`, tách từ `master`. Không merge, không push.
- **Nếu một bước trong kế hoạch này mâu thuẫn với thực tế, DỪNG và báo — không tự sửa test cho khớp code.** Ở năm dự án trước, mỗi dự án đều có ít nhất một chỗ kế hoạch sai; mỗi lần người thi công báo lên đúng, và đó là hành vi mong muốn.

### Ánh xạ tên — dùng xuyên suốt

| khái niệm | Pine | oracle |
|---|---|---|
| biên trên / dưới của range | `rangeHigh` / `rangeLow` | `rh` / `rl` |
| cú phá lên mới có được tính | `upEligible` | `up_el` |
| đang chờ xuyên mốc, chiều lên | `upArmed` | `up_armed` |
| mốc của chiều lên | `upLevel` | `up_level` |
| nến phá của chiều lên | `upBar` | `up_bar` |
| close nến đỏ gần nhất | `lastDownClose` | `last_dn` |
| close nến xanh gần nhất | `lastUpClose` | `last_up` |

---

## Cấu trúc file

| File | Trách nhiệm | Task |
|---|---|---|
| `tests/pine_oracles/orfade_oracle.py` | `Bar`, `Signal`, `run()` — bản gốc của máy trạng thái | 1 |
| `tests/pine_oracles/test_orfade_oracle.py` | 13 test + mutation | 1 |
| `pine/nas_open_range_fade.pine` | indicator đánh dấu | 2 |

Chỉ hai task. Không có bản strategy (spec §9), nên **không có cặp chép nào** và không cần guard chống trôi.

---

## Task 1: Oracle Python và test

Oracle được viết **trước** file Pine, để Task 2 có bản đối chiếu sẵn.

Oracle **nhận sẵn nhãn phiên và nhãn cửa sổ** thay vì tự tính múi giờ. Lý do (spec §10.1): múi giờ là việc của `hour(time, tz)` trong Pine, không phải thứ đang có rủi ro. Thứ có rủi ro là máy trạng thái và thứ tự trong nến — oracle chỉ mô hình đúng những thứ đó.

**Files:**
- Create: `tests/pine_oracles/orfade_oracle.py`
- Create: `tests/pine_oracles/test_orfade_oracle.py`

**Interfaces:**
- Produces: `Bar = namedtuple("Bar", "o h l c")`
- Produces: `Signal = namedtuple("Signal", "direction bar level close wait session")`
- Produces: hằng `SELL = "SELL"`, `BUY = "BUY"`
- Produces: `run(bars, session, in_window, min_range_bars=30, enable_up=True, enable_down=True) -> list[Signal]`
  - `session[i]`: giá trị bất kì (thường là chuỗi) hoặc `None`. **Đổi giá trị nghĩa là phiên mới.**
  - `in_window[i]`: bool — nến này có nằm trong cửa sổ gom range không.
- Task 2 dùng `run` làm bản gốc để đối chiếu từng dòng.

**Một quyết định oracle phải ghi vào docstring:** `enable_up`/`enable_down` **chỉ chặn việc PHÁT tín hiệu**, không đổi trạng thái. Setup vẫn arm và vẫn bị tiêu thụ y hệt khi cờ tắt. Nhờ vậy hai cờ là bộ lọc hiển thị thuần tuý và không tạo ra một máy trạng thái thứ hai. Giống `rsi_trend_pullback` §2.7.

- [ ] **Step 1: Viết test đầu tiên — ca BÁN đầy đủ**

Tạo `tests/pine_oracles/test_orfade_oracle.py`:

```python
"""Test cho orfade_oracle — fade cu pha range phien.

Spec: docs/superpowers/specs/2026-09-15-nas-open-range-fade-design.md

Oracle nhan san nhan phien va nhan cua so: mui gio la viec cua hour(time, tz)
trong Pine, khong phai thu dang co rui ro. Thu co rui ro la MAY TRANG THAI va
THU TU sau buoc trong mot nen.

Moi test dung min_range_bars=2 cho gon; mac dinh that la 30.
"""
from orfade_oracle import BUY, SELL, Bar, run


def mk(rows, sess="S1", n_window=2):
    """rows la list (o, h, l, c). n_window nen dau tien nam trong cua so gom."""
    bars = [Bar(*r) for r in rows]
    session = [sess] * len(rows)
    in_window = [i < n_window for i in range(len(rows))]
    return bars, session, in_window


def test_ban_day_du():
    """Cua so: nen 0-1 -> rh=110, rl=90.

    nen 3 do, close 102        -> last_dn = 102
    nen 4 dong 112 > 110       -> pha len, arm o muc 102
    nen 6 dong 101 < 102       -> TIN HIEU BAN, cho = 6 - 4 = 2
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (100, 104, 99, 103),      # 2 xanh, trong range
        (106, 107, 101, 102),     # 3 DO  -> last_dn = 102
        (103, 115, 102, 112),     # 4 pha len
        (112, 113, 108, 109),     # 5 do, ve trong range
        (109, 110, 100, 101),     # 6 do, xuyen muc -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    s = got[0]
    assert s.direction == SELL
    assert s.bar == 6
    assert s.level == 102
    assert s.close == 101
    assert s.wait == 2
    assert s.session == "S1"
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf tests/pine_oracles/__pycache__ && python -m pytest tests/pine_oracles/test_orfade_oracle.py -q
```

Kỳ vọng: FAIL, `ModuleNotFoundError: No module named 'orfade_oracle'`.

(Import trần `from orfade_oracle import ...` chạy được vì pytest thêm thư mục chứa file test vào `sys.path` — `tests/pine_oracles/test_momexp_oracle.py` đã dùng đúng cách này.)

- [ ] **Step 3: Viết oracle**

Tạo `tests/pine_oracles/orfade_oracle.py`:

```python
"""Fade cu pha range cua phien: gom range gio dau, cho pha, roi cho xuyen nguoc.

Spec: docs/superpowers/specs/2026-09-15-nas-open-range-fade-design.md

Ban goc de doi chieu voi pine/nas_open_range_fade.pine.

RUI RO SO MOT CUA FILE PINE LA THU TU TRONG MOT NEN. Sau buoc phai chay dung
thu tu nay:

    1. gom range / chot range
    2. kiem tin hieu        -> ban, disarm
    3. cap nhat eligible    (neu nen nay dong TRONG range)
    4. kiem pha LEN         -> arm
    5. kiem pha XUONG       -> arm
    6. cap nhat last_dn / last_up TU NEN NAY

Buoc 6 phai CUOI CUNG. Neu no chay truoc buoc 4 thi mot nen pha ma ban than no
la nen do se tu lay close cua chinh minh lam moc — pattern van chay, van ve, va
sai am tham.

Oracle nhan san `session` va `in_window` thay vi tu tinh mui gio: mui gio la
viec cua hour(time, tz) trong Pine, khong phai thu dang co rui ro.

`enable_up` / `enable_down` CHI chan viec PHAT tin hieu, khong doi trang thai.
Setup van arm va van bi tieu thu y het khi co tat. Nho vay hai co la bo loc hien
thi thuan tuy va khong tao ra mot may trang thai thu hai.
"""
from collections import namedtuple

Bar = namedtuple("Bar", "o h l c")
Signal = namedtuple("Signal", "direction bar level close wait session")

SELL = "SELL"
BUY = "BUY"

_NO_SESSION = object()


def run(bars, session, in_window, min_range_bars=30,
        enable_up=True, enable_down=True):
    """Tra ve danh sach Signal theo thu tu thoi gian.

    `session[i]` doi gia tri nghia la phien moi: xoa sach moi trang thai.
    `session[i] is None` nghia la nen chua thuoc phien nao — bo qua.
    """
    out = []
    cur = _NO_SESSION
    rh = rl = None
    n_win = 0
    finalized = False
    range_ok = False
    up_el = dn_el = False
    up_armed = dn_armed = False
    up_level = dn_level = None
    up_bar = dn_bar = None
    last_dn = last_up = None

    for i, bar in enumerate(bars):
        s = session[i]

        if s != cur:                       # phien moi: xoa sach (spec 3.7)
            cur = s
            rh = rl = None
            n_win = 0
            finalized = False
            range_ok = False
            up_el = dn_el = False
            up_armed = dn_armed = False
            up_level = dn_level = None
            up_bar = dn_bar = None
            last_dn = last_up = None

        if s is None:
            continue

        # ---- 1. gom range / chot range
        if in_window[i]:
            rh = bar.h if rh is None else max(rh, bar.h)
            rl = bar.l if rl is None else min(rl, bar.l)
            n_win += 1
            continue

        if not finalized:
            finalized = True
            range_ok = n_win >= min_range_bars
            up_el = dn_el = range_ok
            last_dn = last_up = None       # diem xoa thu hai (spec 3.3)

        if not range_ok:
            continue

        # ---- 2. tin hieu
        if up_armed and bar.c < up_level:
            if enable_up:
                out.append(Signal(SELL, i, up_level, bar.c, i - up_bar, s))
            up_armed = False
        if dn_armed and bar.c > dn_level:
            if enable_down:
                out.append(Signal(BUY, i, dn_level, bar.c, i - dn_bar, s))
            dn_armed = False

        # ---- 3. eligible: chi khi dong TRONG range
        if rl <= bar.c <= rh:
            up_el = dn_el = True

        # ---- 4. pha LEN
        if bar.c > rh and up_el and last_dn is not None and last_dn < rh:
            up_level = last_dn
            up_bar = i
            up_armed = True
            up_el = False

        # ---- 5. pha XUONG
        if bar.c < rl and dn_el and last_up is not None and last_up > rl:
            dn_level = last_up
            dn_bar = i
            dn_armed = True
            dn_el = False

        # ---- 6. cap nhat moc TU NEN NAY — phai CUOI CUNG
        if bar.c < bar.o:
            last_dn = bar.c
        elif bar.c > bar.o:
            last_up = bar.c

    return out
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf tests/pine_oracles/__pycache__ && python -m pytest tests/pine_oracles/test_orfade_oracle.py -q
```

Kỳ vọng: `1 passed`.

- [ ] **Step 5: Viết mười hai test còn lại**

Thêm vào cuối `tests/pine_oracles/test_orfade_oracle.py`:

```python
def test_moc_la_nen_do_CUOI_CUNG_truoc_cu_pha():
    """Hai nen do truoc cu pha; cai sau thang.

    nen 2 do close 101, nen 3 do close 103 -> moc phai la 103.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (106, 107, 100, 101),     # 2 DO -> last_dn = 101
        (104, 105, 99, 103),      # 3 DO -> last_dn = 103
        (103, 115, 102, 112),     # 4 pha len -> arm o 103
        (112, 113, 100, 102),     # 5 do, 102 < 103 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].level == 103
    assert got[0].wait == 1


def test_nen_pha_la_nen_do_khong_tu_lay_minh_lam_moc():
    """Buoc 6 phai CUOI CUNG.

    nen 3 vua la nen DO vua dong tren bien (112 > 110). Moc phai la 102 (tu nen
    2), khong phai 112 (cua chinh no).

    Neu buoc 6 chay truoc buoc 4: moc = 112, va nen 4 (close 105) se xuyen ngay
    -> tin hieu o nen 4, muc 112, cho 1. Ban dung cho tin hieu o nen 5, muc 102,
    cho 2.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (105, 106, 100, 102),     # 2 DO -> last_dn = 102
        (115, 116, 111, 112),     # 3 DO va dong tren bien -> pha, arm o 102
        (112, 113, 104, 105),     # 4 do, 105 khong duoi 102; ve trong range
        (105, 106, 100, 101),     # 5 do, 101 < 102 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].bar == 5
    assert got[0].level == 102
    assert got[0].wait == 2


def test_phai_dong_trong_range_truoc_khi_tinh_cu_pha_moi():
    """Spec 3.2. Sau cu pha o nen 3, cac nen 4 va 5 van o tren bien nen KHONG
    duoc tinh la cu pha moi — moc giu nguyen 102.

    Neu bo dieu kien eligible: nen 5 se arm lai o muc 113 (last_dn cua nen 4),
    va nen 6 (close 105) xuyen ngay -> tin hieu o nen 6, muc 113, cho 1.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (105, 106, 100, 102),     # 2 DO -> last_dn = 102
        (103, 115, 102, 112),     # 3 pha len -> arm o 102, el = False
        (114, 116, 111, 113),     # 4 DO, van tren bien -> last_dn = 113
        (113, 115, 112, 114),     # 5 xanh, van tren bien -> khong arm lai
        (114, 115, 104, 105),     # 6 do, ve trong range -> el = True
        (105, 106, 100, 101),     # 7 do, 101 < 102 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].bar == 7
    assert got[0].level == 102
    assert got[0].wait == 4


def test_nen_dong_o_bien_kia_khong_bat_lai_eligible():
    """Spec 3.2 cau cuoi: dong DUOI rangeLow la o NGOAI range, khong phai trong.

    Ca nay doi moc phai nam DUOI rangeLow. Neu moc o gan bien tren nhu thuong
    le thi nen dong duoi rangeLow se xuyen moc va ban tin hieu NGAY, va trang
    thai eligible khong con quan sat duoc — mot test viet kieu do se pass vi ly
    do sai.

    moc = 85, duoi rl = 90. Nen 4 dong 88: duoi rl nhung TREN moc nen khong ban.
    Neu 88 bat lai up_el thi nen 5 arm lai o 88 va nen 6 (dong 86) ban voi
    cho = 1. Ban dung: khong arm lai, nen 7 (dong 84) moi ban, moc 85, cho = 4.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (95, 96, 84, 85),         # 2 DO, dong DUOI rl -> last_dn = 85
        (85, 115, 84, 112),       # 3 pha len -> arm o 85, up_el = False
        (112, 113, 87, 88),       # 4 DO, duoi rl nhung TREN moc -> khong ban
        (88, 115, 87, 112),       # 5 pha len lan hai -> KHONG duoc arm lai
        (112, 113, 85, 86),       # 6 do, 86 khong duoi 85
        (86, 87, 83, 84),         # 7 do, 84 < 85 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].bar == 7
    assert got[0].level == 85
    assert got[0].wait == 4


def test_moc_tren_bien_thi_khong_arm():
    """Spec 3.4 ve cuoi. Nen 2 la nen DO dong tren bien (112 > 110) nhung luc do
    last_dn con None nen khong arm. Sau buoc 6, last_dn = 112 > rangeHigh.

    Nen 3 dong tren bien lan nua: up_el van True (chua tung arm), nhung
    112 < 110 sai -> KHONG arm. Nen 4 dong 101, neu da arm o 112 thi no da ban.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (115, 116, 111, 112),     # 2 DO tren bien, last_dn con None -> khong arm
        (112, 114, 111, 113),     # 3 xanh tren bien, last_dn = 112 > 110 -> chan
        (113, 114, 100, 101),     # 4 neu da arm o 112 thi day da ban
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert got == []


def test_khong_co_nen_do_nao_thi_khong_arm():
    """last_dn con None thi cu pha khong arm duoc."""
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (100, 104, 99, 103),      # 2 xanh
        (103, 115, 102, 112),     # 3 pha len, last_dn = None -> khong arm
        (112, 113, 100, 101),     # 4 khong co gi de xuyen
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert got == []


def test_mua_guong_qua_bien_duoi():
    """Chieu xuong soi guong: nen xanh cuoi truoc cu pha xuong lam moc.

    nen 2 xanh close 99  -> last_up = 99
    nen 3 dong 86 < 90   -> pha xuong, arm o 99
    nen 4 dong 100 > 99  -> TIN HIEU MUA, cho = 1
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (95, 100, 94, 99),        # 2 XANH -> last_up = 99
        (95, 96, 85, 86),         # 3 pha xuong -> arm o 99
        (86, 102, 85, 100),       # 4 xanh, 100 > 99 -> MUA
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    b = got[0]
    assert b.direction == BUY
    assert b.bar == 4
    assert b.level == 99
    assert b.close == 100
    assert b.wait == 1


def test_phien_moi_xoa_sach_trang_thai():
    """Spec 3.7. Setup dang armed o cuoi phien 1 KHONG duoc song sang phien 2.

    Neu trang thai ro ri: nen 6 dong 49 < muc cu 102 -> mot tin hieu BAN gia.
    """
    bars = [Bar(100, 110, 90, 105), Bar(105, 108, 95, 100),
            Bar(105, 106, 100, 102), Bar(103, 115, 102, 112),
            Bar(50, 60, 40, 55), Bar(55, 58, 45, 50),
            Bar(50, 52, 48, 49)]
    session = ["S1", "S1", "S1", "S1", "S2", "S2", "S2"]
    in_window = [True, True, False, False, True, True, False]

    got = run(bars, session, in_window, min_range_bars=2)

    assert got == []


def test_cua_so_qua_it_nen_thi_phien_do_chet():
    """Spec 2.4. min_range_bars = 2 nhung cua so chi co 1 nen."""
    bars = [Bar(100, 110, 90, 105), Bar(105, 106, 100, 102),
            Bar(103, 115, 102, 112), Bar(112, 113, 100, 101)]
    session = ["S1"] * 4
    in_window = [True, False, False, False]

    got = run(bars, session, in_window, min_range_bars=2)

    assert got == []


def test_doji_khong_phai_do_cung_khong_phai_xanh():
    """Spec 3.3. Nen 3 co close == open nen khong cap nhat moc nao.

    Moc phai la 102 (tu nen 2), khong phai 103 (tu nen doji).
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (105, 106, 100, 102),     # 2 DO -> last_dn = 102
        (103, 104, 102, 103),     # 3 DOJI -> khong doi moc nao
        (103, 115, 102, 112),     # 4 pha len -> arm o 102
        (112, 113, 102, 103),     # 5 do, 103 khong duoi 102
        (103, 104, 100, 101),     # 6 do, 101 < 102 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].level == 102
    assert got[0].bar == 6


def test_dong_cua_dung_bang_moc_khong_ban():
    """Luat la `<` chat. Nen 5 dong dung 102 -> khong ban; nen 6 dong 101 -> ban."""
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (105, 106, 100, 102),     # 2 DO -> last_dn = 102
        (103, 115, 102, 112),     # 3 pha len -> arm o 102
        (112, 113, 101, 102),     # 4 dong DUNG BANG moc -> khong ban
        (102, 103, 100, 101),     # 5 dong 101 < 102 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].bar == 5


def test_tat_mot_chieu_khong_anh_huong_chieu_kia():
    """Hai co chi chan viec PHAT tin hieu, khong doi trang thai."""
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (106, 107, 101, 102),     # 2 DO -> last_dn = 102
        (103, 115, 102, 112),     # 3 pha len -> arm o 102
        (112, 113, 100, 101),     # 4 do, 101 < 102 -> BAN (neu bat)
    ])

    assert run(bars, sess, win, min_range_bars=2, enable_up=False) == []
    assert len(run(bars, sess, win, min_range_bars=2, enable_down=False)) == 1
```

- [ ] **Step 6: Chạy toàn bộ test của oracle**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf tests/pine_oracles/__pycache__ && python -m pytest tests/pine_oracles/test_orfade_oracle.py -q
```

Kỳ vọng: `13 passed`.

- [ ] **Step 7: Mutation testing — sáu đột biến, tất cả PHẢI chết**

Chạy từng đột biến trên **bản sao** của oracle trong scratchpad (hoặc sửa rồi khôi phục — nếu làm cách sau thì phải xác nhận `git diff` sạch sau đó). Với mỗi con, chạy `python -m pytest tests/pine_oracles/test_orfade_oracle.py -q` và ghi kết quả:

| # | đột biến | sửa gì |
|---|---|---|
| M1 | bước 6 chạy trước bước 4 | chuyển khối `if bar.c < bar.o: ... elif ...` lên ngay trước khối "pha LEN" |
| M2 | bỏ điều kiện eligible | xoá `and up_el` khỏi điều kiện phá lên |
| M3 | bỏ vế mốc phải dưới biên | xoá `and last_dn < rh` |
| M4 | so sánh lỏng ở tín hiệu | `bar.c < up_level` → `bar.c <= up_level` |
| M5 | nến ở biên kia bật lại eligible | `if rl <= bar.c <= rh:` → `if bar.c <= rh:` |
| M6 | bỏ xoá trạng thái ở phiên mới | xoá thân khối `if s != cur:` trừ dòng `cur = s` |

**Con nào SỐNG SÓT là thiếu test, không phải "chấp nhận được".** Viết thêm test cho tới khi nó chết, rồi chạy lại cả sáu.

**Toàn bộ code của Task 1 đã được CHẠY THẬT trước khi plan này được viết ra:** 13 test xanh, và cả sáu đột biến trên đều chết. Nếu bạn gõ đúng thì không cần thêm test nào. Nếu một con sống sót thì gần như chắc chắn bạn gõ lệch một chỗ — đọc lại trước khi báo.

- [ ] **Step 8: Chạy cả suite**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf __pycache__ tests/__pycache__ tests/pine_oracles/__pycache__ rsi_fvg/__pycache__ && python -m pytest -q
```

Kỳ vọng: `429 passed, 2 failed` (416 mốc + 13 test mới; hai ca đỏ là MT5 môi trường).

- [ ] **Step 9: Commit**

```bash
git add tests/pine_oracles/orfade_oracle.py tests/pine_oracles/test_orfade_oracle.py
git commit -F <scratchpad>/msg-task1.txt
```

Message phải nói rõ: oracle nhận sẵn nhãn phiên/cửa sổ và vì sao, và rằng sáu đột biến đều chết.

---

## Task 2: File indicator Pine

**Files:**
- Create: `pine/nas_open_range_fade.pine`

**Interfaces:**
- Consumes: `run()` của Task 1 làm bản đối chiếu (đọc tay, không chạy được).
- Produces: không gì — đây là task cuối, không có bản strategy.

- [ ] **Step 1: Viết file**

Tạo `pine/nas_open_range_fade.pine`:

```pine
//@version=6
// =============================================================================
//  NAS Open Range Fade — indicator danh dau (khong dat lenh)
//
//  Hai phien moi ngay mo luc 07:00 va 19:00 gio UTC+7. Gio dau tien cua moi
//  phien tao mot range. Khi gia dong cua vuot ra khoi range roi QUAY LAI xuyen
//  qua moc cua cay nen nguoc chieu cuoi cung truoc cu pha, do la dau hieu cu
//  pha da hong.
//
//  Day la setup DAO CHIEU, khong phai setup di theo cu pha: pha len ma hong thi
//  tin hieu la BAN.
//
//  SAU BUOC TRONG MOT NEN, DUNG THU TU NAY — day la cho chiu luc:
//    1. gom range / chot range
//    2. kiem tin hieu        -> ban, disarm
//    3. cap nhat eligible    (chi khi nen nay dong TRONG range)
//    4. kiem pha LEN         -> arm
//    5. kiem pha XUONG       -> arm
//    6. cap nhat lastDownClose / lastUpClose TU NEN NAY
//
//  Buoc 6 PHAI cuoi cung. Neu no chay truoc buoc 4 thi mot nen pha ma ban than
//  no la nen do se tu lay close cua chinh minh lam moc — pattern van chay, van
//  ve, va sai am tham.
//
//  CU PHA LA MOT SU KIEN, KHONG PHAI MOT MUC: phai co nen dong cua TRONG range
//  roi moi tinh cu pha tiep theo (bien upEligible). Neu chi so muc thi moi nen
//  o tren bien deu la "pha" va moc bi ghi de lien tuc — moc duoi theo gia thay
//  vi dung yen.
//
//  KHONG DUNG request.security DE LAY CAY H1. Nen H1 cua TradingView neo theo
//  phien cua san, khong neo theo 07:00 UTC+7, nen "cay H1 mo luc 07:00" rat co
//  the khong ton tai nhu mot nen H1 — no roi vao giua hai nen. Khi do
//  request.security van tra ve mot gia tri, chi la gia tri cua mot cay khac:
//  khong loi, khong canh bao, chi la mot range sai. Range o day duoc gom truc
//  tiep tu nen 1m.
//
//  CHI CHAY TREN KHUNG M1. Tren khung khac, file ve mot nhan canh bao va khong
//  sinh tin hieu nao. Im lang chay sai tren khung khac la che do hong te hon
//  nhieu so voi tu choi chay.
//
//  MOC 07:00 VA 19:00 TROI SO VOI PHIEN MY MOI NAM HAI LAN: UTC+7 khong co DST
//  con My thi co. 19:00 UTC+7 la 08:00 ET mua he nhung 07:00 ET mua dong. Cung
//  mot setup do hai thu khac nhau tuy mua — khi doc ket qua gop nhieu nam thi
//  day la bien gay nhieu.
//
//  BOX BI PINE CHAN CUNG 500. Hai box moi ngay tuc khoang 250 phien, nua nam
//  lich su; cu hon thi box lang le bien mat khoi chart. Tran nay CHI anh huong
//  phan VE: may trang thai doc rangeHigh/rangeLow la bien float, khong doc doi
//  tuong box. Mui ten tin hieu dung plotshape — khong co tran.
//
//  Kiem chung: may trang thai duoc dung lai bang Python o
//  tests/pine_oracles/orfade_oracle.py voi 13 test va 6 dot bien deu chet.
//  Pine KHONG compile duoc o may viet ra file nay. Phan VE va BANG khong co
//  test, chi soat tay.
// =============================================================================
indicator("NAS Open Range Fade", overlay=true,
     max_boxes_count=500, max_labels_count=500)

// ---------------------------------------------------------------- inputs
grpSess      = "Phien"
tzName       = input.string("Asia/Bangkok", "Mui gio", group=grpSess)
sess1Hour    = input.int(7,  "Gio mo phien 1", minval=0, maxval=23, group=grpSess)
sess2Hour    = input.int(19, "Gio mo phien 2", minval=0, maxval=23, group=grpSess)
rangeMinutes = input.int(60, "Do dai cua so gom range (phut)", minval=1, group=grpSess)
minRangeBars = input.int(30, "So nen 1m toi thieu trong cua so", minval=1, group=grpSess)

grpDir     = "Chieu"
enableUp   = input.bool(true, "Bat chieu BAN (pha len hong)", group=grpDir)
enableDown = input.bool(true, "Bat chieu MUA (pha xuong hong)", group=grpDir)

grpShow     = "Hien thi"
showBox     = input.bool(true, "Box range", group=grpShow)
showLevel   = input.bool(true, "Moc dang cho", group=grpShow)
showSignals = input.bool(true, "Mui ten tin hieu", group=grpShow)
showTable   = input.bool(true, "Bang trang thai", group=grpShow)
boxTransp   = input.int(85, "Do trong cua box", minval=0, maxval=100, group=grpShow)

// ---------------------------------------------------------------- phien
bool isM1 = timeframe.period == "1"

int mins = hour(time, tzName) * 60 + minute(time, tzName)
int win1 = sess1Hour * 60
int win2 = sess2Hour * 60

bool inWin1 = mins >= win1 and mins < win1 + rangeMinutes
bool inWin2 = mins >= win2 and mins < win2 + rangeMinutes
bool inWin  = inWin1 or inWin2

// Phien moi = vua BUOC VAO mot cua so gom ma nen truoc chua o trong do.
// nz(..., false) can thiet: tren nen dau chart `inWin1[1]` la na, va `na` trong
// ngu canh boolean lam ca bieu thuc thanh falsy — phien dau tien se bi bo qua.
bool newSess = (inWin1 and not nz(inWin1[1], false))
     or (inWin2 and not nz(inWin2[1], false))

// ---------------------------------------------------------------- trang thai
var string sessName      = na
var int    winStartBar   = na
var float  rangeHigh     = na
var float  rangeLow      = na
var int    nWin          = 0
var bool   finalized     = false
var bool   rangeOk       = false
var bool   upEligible    = false
var bool   dnEligible    = false
var bool   upArmed       = false
var bool   dnArmed       = false
var float  upLevel       = na
var float  dnLevel       = na
var int    upBar         = na
var int    dnBar         = na
var float  lastDownClose = na
var float  lastUpClose   = na
var box    rangeBox      = na

var string lastSigDir   = na
var float  lastSigLevel = na
var float  lastSigClose = na
var int    lastSigWait  = na

bool  upSig    = false
bool  dnSig    = false
float sigLevel = na
int   sigWait  = na

// ---------------------------------------------------------------- may trang thai
// Ca khoi gac bang barstate.isconfirmed: `nWin := nWin + 1` KHONG idempotent,
// nen chay lai trong cung mot nen se dem sai so nen cua cua so.
if isM1 and barstate.isconfirmed

    // 0. phien moi thi xoa sach
    if newSess
        sessName      := inWin1 ? str.tostring(sess1Hour) + ":00" : str.tostring(sess2Hour) + ":00"
        winStartBar   := bar_index
        rangeHigh     := na
        rangeLow      := na
        nWin          := 0
        finalized     := false
        rangeOk       := false
        upEligible    := false
        dnEligible    := false
        upArmed       := false
        dnArmed       := false
        upLevel       := na
        dnLevel       := na
        upBar         := na
        dnBar         := na
        lastDownClose := na
        lastUpClose   := na
        rangeBox      := na

    // 1a. gom range
    if inWin
        rangeHigh := na(rangeHigh) ? high : math.max(rangeHigh, high)
        rangeLow  := na(rangeLow)  ? low  : math.min(rangeLow,  low)
        nWin      := nWin + 1

    // 1b. chot range — nen dau tien ngoai cua so
    if not inWin and not finalized
        finalized     := true
        rangeOk       := nWin >= minRangeBars
        upEligible    := rangeOk
        dnEligible    := rangeOk
        lastDownClose := na
        lastUpClose   := na
        if showBox and rangeOk
            rangeBox := box.new(winStartBar, rangeHigh, bar_index, rangeLow,
                 border_color=color.new(color.gray, 20),
                 bgcolor=color.new(color.gray, boxTransp))

    if not inWin and rangeOk
        // 2. tin hieu
        if upArmed and close < upLevel
            if enableUp
                upSig    := true
                sigLevel := upLevel
                sigWait  := bar_index - upBar
            upArmed := false
        if dnArmed and close > dnLevel
            if enableDown
                dnSig    := true
                sigLevel := dnLevel
                sigWait  := bar_index - dnBar
            dnArmed := false

        // 3. eligible — CHI khi dong TRONG range
        if close >= rangeLow and close <= rangeHigh
            upEligible := true
            dnEligible := true

        // 4. pha LEN
        if close > rangeHigh and upEligible and not na(lastDownClose) and lastDownClose < rangeHigh
            upLevel    := lastDownClose
            upBar      := bar_index
            upArmed    := true
            upEligible := false

        // 5. pha XUONG
        if close < rangeLow and dnEligible and not na(lastUpClose) and lastUpClose > rangeLow
            dnLevel    := lastUpClose
            dnBar      := bar_index
            dnArmed    := true
            dnEligible := false

        // 6. cap nhat moc TU NEN NAY — PHAI CUOI CUNG
        if close < open
            lastDownClose := close
        else if close > open
            lastUpClose := close

    // noi dai box sang phai suot phien
    if showBox and not na(rangeBox)
        box.set_right(rangeBox, bar_index)

    if upSig or dnSig
        lastSigDir   := upSig ? "BAN" : "MUA"
        lastSigLevel := sigLevel
        lastSigClose := close
        lastSigWait  := sigWait

// ---------------------------------------------------------------- ve
plot(showLevel and upArmed ? upLevel : na, "Moc chieu BAN",
     color=color.new(color.red, 0), style=plot.style_linebr, linewidth=1)
plot(showLevel and dnArmed ? dnLevel : na, "Moc chieu MUA",
     color=color.new(color.teal, 0), style=plot.style_linebr, linewidth=1)

plotshape(showSignals and upSig, title="BAN", style=shape.triangledown,
     location=location.abovebar, color=color.new(color.red, 0),
     size=size.small, text="S")
plotshape(showSignals and dnSig, title="MUA", style=shape.triangleup,
     location=location.belowbar, color=color.new(color.teal, 0),
     size=size.small, text="B")

if barstate.islast and not isM1
    label.new(bar_index, high,
         "NAS Open Range Fade chi chay tren khung M1.\nKhung hien tai: "
         + timeframe.period + " — khong sinh tin hieu nao.",
         style=label.style_label_down, color=color.new(color.orange, 10),
         textcolor=color.white, size=size.normal)

// ---------------------------------------------------------------- bang
f_armTxt(armed, lvl, brk) =>
    armed ? "ARMED @ " + str.tostring(lvl, format.mintick)
         + "  (" + str.tostring(bar_index - brk) + " nen)" : "READY"

var table tbl = na
if showTable and barstate.islast and isM1
    if na(tbl)
        tbl := table.new(position.top_right, 2, 5, border_width=1)
    table.cell(tbl, 0, 0, "phien", text_size=size.small)
    table.cell(tbl, 1, 0, na(sessName) ? "—" : sessName + "  (" + str.tostring(nWin) + " nen)", text_size=size.small)
    table.cell(tbl, 0, 1, "range", text_size=size.small)
    table.cell(tbl, 1, 1, rangeOk ? str.tostring(rangeHigh, format.mintick) + " / " + str.tostring(rangeLow, format.mintick) : "—", text_size=size.small)
    table.cell(tbl, 0, 2, "chieu BAN", text_size=size.small)
    table.cell(tbl, 1, 2, f_armTxt(upArmed, upLevel, upBar), text_size=size.small)
    table.cell(tbl, 0, 3, "chieu MUA", text_size=size.small)
    table.cell(tbl, 1, 3, f_armTxt(dnArmed, dnLevel, dnBar), text_size=size.small)
    table.cell(tbl, 0, 4, "tin hieu cuoi", text_size=size.small)
    table.cell(tbl, 1, 4, na(lastSigDir) ? "—" : lastSigDir + " " + str.tostring(lastSigClose, format.mintick) + "  cho " + str.tostring(lastSigWait), text_size=size.small)

// ---------------------------------------------------------------- alert
if upSig
    alert('{"symbol":"' + syminfo.ticker + '","tf":"' + timeframe.period + '","direction":"SELL","setup":"ORFADE"' + ',"level":' + str.tostring(sigLevel, "0.#####") + ',"range_high":' + str.tostring(rangeHigh, "0.#####") + ',"range_low":' + str.tostring(rangeLow, "0.#####") + ',"close":' + str.tostring(close, "0.#####") + ',"session":"' + sessName + '","wait":' + str.tostring(sigWait) + '}', alert.freq_once_per_bar_close)
if dnSig
    alert('{"symbol":"' + syminfo.ticker + '","tf":"' + timeframe.period + '","direction":"BUY","setup":"ORFADE"' + ',"level":' + str.tostring(sigLevel, "0.#####") + ',"range_high":' + str.tostring(rangeHigh, "0.#####") + ',"range_low":' + str.tostring(rangeLow, "0.#####") + ',"close":' + str.tostring(close, "0.#####") + ',"session":"' + sessName + '","wait":' + str.tostring(sigWait) + '}', alert.freq_once_per_bar_close)
```

- [ ] **Step 2: Checker tĩnh — thụt dòng nối tiếp**

```bash
awk 'match($0,/^ +/){n=RLENGTH; l=$0; sub(/^ +/,"",l); if (l ~ /^(and |or |\+ |color=|style=|location=|textcolor=|size=|group=|minval=|maxval=|tooltip=|border_color=|bgcolor=|max_boxes_count=)/) print NR": indent "n" -> "(n%4==0?"*** LOI ***":"ok")}' pine/nas_open_range_fade.pine
```

Kỳ vọng: mọi dòng in ra đều `ok`. Một dòng `*** LOI ***` nghĩa là thụt chia hết cho 4 — Pine sẽ đọc dòng đó thành khối mới, không báo lỗi, chỉ đổi hành vi.

**Lệnh này đã được chạy thật trên `pine/rsi_failure_swing_indicator.pine` và cho 16 dòng, tất cả indent 5 hoặc 9.** Nếu nó in ra hàng trăm dòng thì bộ lọc sai chứ không phải file sai — báo lên, đừng sửa file. (Ở dự án `momentum_expansion`, một lệnh awk sai bộ lọc đã báo 137 "vi phạm" trên một file hoàn toàn sạch.)

- [ ] **Step 3: Checker tĩnh — ba luật còn lại**

```bash
grep -n "line\.new(" pine/nas_open_range_fade.pine ; echo "--- het (trong = sach) ---"
grep -n '"#\.#####"' pine/nas_open_range_fade.pine ; echo "--- het (trong = sach) ---"
awk '/^[ \t]+.*(hour|minute)\(time/{print NR": "$0}' pine/nas_open_range_fade.pine ; echo "--- het (trong = sach) ---"
```

Cả ba phải không in ra dòng nào. Lệnh thứ ba kiểm `hour(time, tz)`/`minute(time, tz)` nằm ở top level chứ không trong khối thụt — file này không dùng `ta.*` nào, nên đây là thứ tương đương cần canh.

**Lệnh `line.new(` có dấu ngoặc mở là cố ý.** Bản không ngoặc khớp cả dòng comment giải thích luật cấm; dấu ngoặc phân biệt lời gọi thật với văn bản.

- [ ] **Step 4: Đối chiếu tay với oracle — ca `test_ban_day_du`**

Lần theo file Pine bằng tay trên đúng dữ liệu của test đầu tiên ở Task 1. Giả định: nến 0–1 trong cửa sổ, nến 2–6 ngoài cửa sổ, `minRangeBars = 2`.

| nến | o,h,l,c | b1 gom/chốt | b2 tín hiệu | b3 eligible | b4 phá lên | b6 mốc |
|---|---|---|---|---|---|---|
| 0 | 100,110,90,105 | rh=110, rl=90, nWin=1 | — | — | — | — |
| 1 | 105,108,95,100 | rh=110, rl=90, nWin=2 | — | — | — | — |
| 2 | 100,104,99,103 | **chốt**: rangeOk, el=true, mốc=na | chưa armed | 103 trong range | 103>110 sai | xanh → lastUp=103 |
| 3 | 106,107,101,102 | — | chưa armed | 102 trong range | 102>110 sai | **đỏ → lastDown=102** |
| 4 | 103,115,102,112 | — | chưa armed | 112 ngoài | **ARM @102**, upBar=4 | xanh → lastUp=112 |
| 5 | 112,113,108,109 | — | 109<102 sai | 109 trong range | 109>110 sai | đỏ → lastDown=109 |
| 6 | 109,110,100,101 | — | **101<102 → BÁN** | — | — | đỏ → lastDown=101 |

Tại nến 6: `sigLevel=102`, `sigWait = 6 − 4 = 2`.

Khớp từng số với `test_ban_day_du`. **Lệch một số nào là DỪNG và báo** — nhiều khả năng file Pine sai thứ tự bước, không phải test sai.

- [ ] **Step 5: Đối chiếu tay — ca `test_nen_pha_la_nen_do_khong_tu_lay_minh_lam_moc`**

Ca này là ca bắt lỗi thứ tự, phải lần riêng:

| nến | o,h,l,c | b4 phá lên | b6 mốc |
|---|---|---|---|
| 2 | 105,106,100,102 | 102>110 sai | đỏ → lastDown=102 |
| 3 | 115,116,111,112 | 112>110 ✓, lastDown=**102** < 110 ✓ → **ARM @102** | đỏ (112<115) → lastDown=112 |
| 4 | 112,113,104,105 | — | 105<102 sai; 105 trong range → el=true; đỏ → lastDown=105 |
| 5 | 105,106,100,101 | — | **101<102 → BÁN**, upBar=3, wait=2 |

Nến 3 vừa là nến **đỏ** vừa đóng cửa **trên biên**. Nếu bước 6 nằm trước bước 4 trong file Pine thì `upLevel` sẽ là **112** (close của chính nó), và tín hiệu bắn ở nến 4 với `wait=1` thay vì nến 5 với `wait=2`. Đọc lại đúng thứ tự hai khối đó trong file trước khi đi tiếp.

- [ ] **Step 6: Chạy cả suite**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf __pycache__ tests/__pycache__ tests/pine_oracles/__pycache__ rsi_fvg/__pycache__ && python -m pytest -q
```

Kỳ vọng: `429 passed, 2 failed` — **không đổi** so với Task 1. Task này không thêm test Python nào.

- [ ] **Step 7: Commit**

```bash
git add pine/nas_open_range_fade.pine
git commit -F <scratchpad>/msg-task2.txt
```

Message phải nói rõ: **chưa compile**, đã qua checker tĩnh nào, và đã đối chiếu tay hai ca nào với oracle.

---

## Self-Review

**1. Spec coverage** — soi từng mục của spec, chỉ ra task nào làm:

| spec | task |
|---|---|
| §2.1 cửa sổ `[07:00, 08:00)` và `[19:00, 20:00)` | Task 2 (`inWin1`/`inWin2`, `rangeMinutes`) |
| §2.2 gom từ nến 1m, không `request.security` | Task 2 (không có lời gọi nào) |
| §2.3 chart phải M1, nhãn cảnh báo, không sinh tín hiệu | Task 2 (`isM1` gác cả khối; nhãn ở `barstate.islast`) |
| §2.4 `minRangeBars` | Task 1 (tham số), Task 2 (input) |
| §2.5 múi giờ `Asia/Bangkok` | Task 2 (`tzName`) |
| §3.1 ba biến mỗi chiều | Task 1, Task 2 |
| §3.2 cú phá là sự kiện, `upEligible` | Task 1 (M2, M5), Task 2 |
| §3.3 mốc = nến đỏ cuối cùng, hai điểm xoá | Task 1 (M1, test doji), Task 2 |
| §3.4 ba điều kiện arm, vế `< rangeHigh`, ghi đè mốc | Task 1 (M3), Task 2 |
| §3.5 thứ tự sáu bước | Task 1 (M1), Task 2 Step 5 |
| §3.6 hai chiều độc lập | Task 1 (test mua gương), Task 2 |
| §3.7 phiên mới xoá sạch | Task 1 (M6), Task 2 |
| §4 không repaint, `barstate.isconfirmed` | Task 2 — **không có test tự động**, xem hạn chế |
| §5.1 box, `max_boxes_count=500` | Task 2 |
| §5.2 không `line.new(` | Task 2 Step 3 |
| §5.3 mọi lệnh vẽ gác bằng biến trạng thái | Task 2 — soát tay |
| §6 alert, `"0.#####"`, `wait` và `session` | Task 2 Step 3 (grep), Task 2 |
| §7 bảng trạng thái | Task 2 |
| §8 input | Task 2 |
| §9 những gì cố ý không làm | không task nào — đúng, đó là danh sách phủ định |
| §10.1 oracle trong version control | Task 1 |
| §10.2 mutation testing, sáu đột biến | Task 1 Step 7 |
| §10.3 checker tĩnh | Task 2 Step 2, Step 3 |
| §10.4 `test_pine_indent.py` chưa có trên nhánh này | Global Constraints — chạy tay, ngoài phạm vi |
| §11 rủi ro đã biết | ghi trong header file Pine (Task 2) |

**2. Placeholder scan** — không có "TBD", "TODO", "tương tự Task N", hay bước nào mô tả mà không có code. Hai chỗ ghi `<scratchpad>` là đường dẫn thật mà người thi công tự điền theo môi trường phiên của họ.

**3. Type consistency** — `Bar(o, h, l, c)` và `Signal(direction, bar, level, close, wait, session)` khai ở Task 1 và dùng đúng tên đó trong cả 13 test. Tên biến Pine (`rangeHigh`, `rangeLow`, `upEligible`, `upArmed`, `upLevel`, `upBar`, `lastDownClose`, `lastUpClose`) khớp bảng ánh xạ ở đầu plan và khớp oracle theo đúng ánh xạ đó.

### Ba hạn chế đã biết của chính kế hoạch này

1. **`barstate.isconfirmed` không có test tự động.** Oracle không mô hình khái niệm "nến đã đóng" — nó chạy trên chuỗi nến đã đóng sẵn, nên nó không phân biệt được bản có gác và bản không gác. Chỗ này chỉ được soát tay. Chấp nhận được vì trên nến lịch sử `barstate.isconfirmed` luôn đúng.

2. **Phần vẽ, bảng và alert không có test nào.** Giống mọi file Pine khác trong repo. Bất biến "mọi lệnh vẽ gác bằng biến trạng thái, không lệnh nào tính lại điều kiện" (§5.3) chỉ được soát tay — và đó chính là lỗi mà `kill_peak` đã mắc một lần.

3. **Logic tính `newSess` không có test tự động.** Oracle nhận sẵn nhãn phiên, nên phép chuyển từ `hour(time, tz)` sang nhãn ấy — gồm cả cái bẫy `nz(inWin1[1], false)` ở nến đầu chart — nằm hoàn toàn trong Pine và chỉ được đọc tay. Đây là đánh đổi có chủ ý của spec §10.1 (múi giờ không phải thứ đang có rủi ro), nhưng nó để lại đúng một mảng không được máy nào canh.
