# RSI Trend Pullback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một setup TradingView theo xu hướng — RSI thủng 25 rồi hồi về 50 thì bán — gồm indicator đánh dấu và strategy để backtest.

**Architecture:** Máy trạng thái hai trạng thái cho mỗi chiều, không state phức tạp, không MTF. Rủi ro số một là **thứ tự ba bước trong một nến** (nới cực trị → tín hiệu → mở pha): đảo hai bước đầu thì TP lệch một nến, pattern vẫn chạy và sai âm thầm. Vì vậy một oracle Python được viết **trước** file Pine và bị mutation testing soi, rồi file Pine đối chiếu tay với nó.

**Tech Stack:** Pine Script v6; Python 3 + pytest cho oracle và cho guard chống trôi bản chép.

**Spec:** `docs/superpowers/specs/2026-09-15-rsi-trend-pullback-design.md`

## Global Constraints

Đọc hết trước khi bắt đầu bất kì task nào.

- **KHÔNG COMPILE ĐƯỢC PINE Ở MÁY NÀY.** Không bao giờ viết "đã test", "đã chạy", "verified", "works" về code Pine. Chỉ được nói "qua checker tĩnh", "đối chiếu với oracle", "đọc tay".
- **Thụt dòng nối tiếp trong Pine phải KHÔNG chia hết cho 4.** Repo dùng 5, 9, 13. Thụt 4 hoặc 8 bị Pine đọc thành khối mới — không báo lỗi, chỉ đổi hành vi. Đây là *dòng nối tiếp*; thân khối ở 4/8/12 là bình thường.
- **Không gọi `ta.*` bên trong `if`.** `ta.rsi` và `ta.atr` giữ state nội bộ; gọi trong nhánh điều kiện là sai âm thầm. Cả hai khai ở top level.
- **Không dùng `line.new`.** Trần cứng 500 và khi tràn thì cái cũ nhất lặng lẽ biến mất — `kill_peak` đã mắc. Dùng `plot(..., style=plot.style_linebr)`.
- **Định dạng số trong alert là `"0.#####"`, KHÔNG phải `"#.#####"`.** Cái sau rụng số 0 đứng đầu (`DecimalFormat` của Java) nên sinh `"sl":.98432` — JSON hỏng trên instrument dưới 1.0.
- **Không đặt tên biến trùng nhau ở hai khối `if` anh em.** Pine v6 có thể từ chối khai báo lại ở scope anh em, và chuyện này chưa kiểm được ở máy này. Dùng tiền tố `s`/`b` cho mọi biến cục bộ của hai chiều.
- **Windows: xoá `__pycache__` trước mỗi lần chạy pytest.** Lệnh: `rm -rf __pycache__ tests/__pycache__ rsi_fvg/__pycache__`. Hai lần ghi file liên tiếp có thể cho mtime giống hệt nhau và Python dùng lại bytecode cũ — chuyện này đã gây chạy xanh giả trong repo này.
- **MỐC TEST: `416 passed, 2 failed`.** Hai ca đỏ là `tests/test_mt5_loader.py` — **lỗi môi trường, không phải lỗi code**: terminal MT5 đang chạy nên guard skip không kích hoạt, nhưng `symbol_info('XAUUSDc')` trả None (`Terminal: Not found`). Cây làm việc sạch ở commit này và hai ca đó không liên quan gì tới việc đang làm. **Đừng sửa chúng, đừng tính chúng vào kết quả của mình.** Nếu số ca đỏ tăng quá 2, hoặc có ca đỏ ở file khác, thì DỪNG và báo.
- **Dùng công cụ Write cho nội dung file.** Heredoc bash trên máy này vỡ khi nội dung có nháy; chỉ khối `python - <<'PYEOF'` thuần Python là tin được.
- **Commit message:** tiếng Việt không dấu, ASCII, viết vào file `.txt` trong scratchpad rồi `git commit -F <file>`. Dòng cuối đúng nguyên văn:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- **Nhánh:** `feat/rsi-trend-pullback`, tách từ `master`. Không merge, không push.
- **Nếu một bước trong kế hoạch này mâu thuẫn với thực tế, DỪNG và báo — không tự sửa test cho khớp code.** Ở bốn dự án trước, mỗi dự án đều có ít nhất một chỗ kế hoạch sai; mỗi lần người thi công báo lên đúng, và đó là hành vi mong muốn.

### Ánh xạ tên — dùng xuyên suốt

| khái niệm | Pine | oracle |
|---|---|---|
| trạng thái chiều bán | `sSt` (0 IDLE, 1 SEEKING) | `s_st` |
| đáy đang theo dõi | `sLow` | `s_low` |
| nến mở pha bán | `sXBar` | `s_xbar` |
| trạng thái chiều mua | `bSt` | `b_st` |
| đỉnh đang theo dõi | `bHigh` | `b_high` |
| nến mở pha mua | `bXBar` | `b_xbar` |

---

## Cấu trúc file

| File | Trách nhiệm | Task |
|---|---|---|
| `tests/pine_oracles/rsitp_oracle.py` | `Bar`, `Signal`, `run()` — bản gốc của máy trạng thái | 1 |
| `tests/pine_oracles/test_rsitp_oracle.py` | 11 test + mutation cho oracle | 1 |
| `pine/rsi_trend_pullback_indicator.pine` | indicator đánh dấu | 2 |
| `tests/pine_blocks.py` | gom vùng `KHOI`/`HET KHOI` trong `pine/`, so từng dòng | 3 |
| `tests/test_pine_blocks.py` | pytest chạy guard đó trên toàn repo | 3 |
| `pine/rsi_trend_pullback_strategy.pine` | strategy để backtest | 4 |

Task 3 nằm **trước** Task 4 có chủ ý: guard phải tồn tại và phải xanh trên các cặp file cũ *trước khi* Task 4 tạo ra cặp mới cần canh.

---

## Task 1: Oracle Python và test

Oracle được viết **trước** file Pine, để Task 2 có bản đối chiếu sẵn.

Oracle **nhận `rsi` và `atr` đã tính sẵn** thay vì tự tính. Lý do: RSI và ATR là hàm dựng sẵn của TradingView, không phải thứ đang có rủi ro. Thứ có rủi ro là máy trạng thái, thứ tự trong nến, và số học `rr` — oracle chỉ mô hình đúng những thứ đó.

**Files:**
- Create: `tests/pine_oracles/rsitp_oracle.py`
- Create: `tests/pine_oracles/test_rsitp_oracle.py`

**Interfaces:**
- Produces: `Bar = namedtuple("Bar", "h l c")`
- Produces: `Signal = namedtuple("Signal", "direction bar entry sl tp rr wait")`
- Produces: hằng `SELL = "SELL"`, `BUY = "BUY"`
- Produces: `run(bars, rsi, atr, lo=25.0, mid=50.0, hi=75.0, sl_mult=3.0, tp_mult=1.0, enable_sell=True, enable_buy=True) -> list[Signal]`
- Task 2 và Task 4 dùng `run` làm bản gốc để đối chiếu từng dòng.

- [ ] **Step 1: Viết test đầu tiên — ca BÁN đầy đủ**

Tạo `tests/pine_oracles/test_rsitp_oracle.py`:

```python
"""Test cho rsitp_oracle — setup RSI theo xu huong.

Spec: docs/superpowers/specs/2026-09-15-rsi-trend-pullback-design.md

Oracle nhan rsi/atr da tinh san: RSI va ATR la ham dung san cua TradingView,
khong phai thu dang co rui ro. Thu co rui ro la MAY TRANG THAI, THU TU trong
mot nen, va so hoc rr.
"""
from rsitp_oracle import BUY, SELL, Bar, run


def test_ban_day_du():
    """rsi thung 25 o nen 1, hoi len 55 o nen 4.

    day theo doi = min(100, 98, 99, 101) = 98
    entry = close nen 4 = 104
    SL    = 104 + 3*2 = 110
    TP    = 98  - 1*2 = 96
    rr    = (104 - 96) / (3*2) = 8/6
    cho   = 4 - 1 = 3 nen
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(101, 98, 99),
            Bar(102, 99, 100), Bar(105, 101, 104)]
    rsi = [60.0, 20.0, 22.0, 35.0, 55.0]
    atr = [2.0] * 5

    got = run(bars, rsi, atr)

    assert len(got) == 1
    s = got[0]
    assert s.direction == SELL and s.bar == 4
    assert s.entry == 104.0
    assert s.sl == 110.0
    assert s.tp == 96.0
    assert s.rr == 8 / 6
    assert s.wait == 3
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf tests/pine_oracles/__pycache__ && python -m pytest tests/pine_oracles/test_rsitp_oracle.py -q
```

Kỳ vọng: FAIL, `ModuleNotFoundError: No module named 'rsitp_oracle'`.

(Import trần `from rsitp_oracle import ...` chạy được vì pytest thêm thư mục chứa file test vào `sys.path` — `tests/pine_oracles/test_momexp_oracle.py` đã dùng đúng cách này.)

- [ ] **Step 3: Viết oracle**

Tạo `tests/pine_oracles/rsitp_oracle.py`:

```python
"""Setup RSI theo xu huong: thung 25 roi hoi ve 50 thi ban.

Spec: docs/superpowers/specs/2026-09-15-rsi-trend-pullback-design.md

Ban goc de doi chieu voi pine/rsi_trend_pullback_indicator.pine va
pine/rsi_trend_pullback_strategy.pine.

RUI RO SO MOT CUA FILE PINE LA THU TU TRONG MOT NEN. Ba buoc phai chay dung
thu tu nay cho moi chieu:

    1. noi cuc tri dang chay   (chi khi SEEKING)
    2. kiem tin hieu           (chi khi SEEKING)
    3. mo pha moi              (chi khi IDLE)

Buoc 1 truoc buoc 2 vi dinh nghia lay day "cho toi nen entry", tuc low cua
chinh nen vao lenh phai duoc tinh vao. Dao hai buoc nay thi TP lech mot nen —
pattern van chay, van ve, va sai am tham.

Buoc 2 truoc buoc 3 de mot tin hieu vua ban khong mo lai pha ngay tren cung
mot nen.
"""
from collections import namedtuple

Bar = namedtuple("Bar", "h l c")
Signal = namedtuple("Signal", "direction bar entry sl tp rr wait")

SELL = "SELL"
BUY = "BUY"

IDLE = 0
SEEKING = 1


def run(bars, rsi, atr, lo=25.0, mid=50.0, hi=75.0,
        sl_mult=3.0, tp_mult=1.0, enable_sell=True, enable_buy=True):
    """Tra ve danh sach Signal theo thu tu thoi gian.

    `rsi[i]` hoac `atr[i]` bang None nghia la chua du lieu (warm-up): khong
    trang thai nao doi va khong tin hieu nao ban.

    Mau so cua rr la `sl_mult * atr`. Khi no bang 0 thi rr khong tinh duoc va
    TIN HIEU KHONG BAN — khong do duoc rui ro thi khong danh dau. Nhung setup
    VAN BI TIEU THU (ve IDLE), giong het khi chieu do bi tat: xem spec 2.7.
    """
    out = []
    s_st, s_low, s_xbar = IDLE, None, None
    b_st, b_high, b_xbar = IDLE, None, None

    for i, bar in enumerate(bars):
        r, a = rsi[i], atr[i]
        ok = r is not None and a is not None

        # ---------------------------------------------------------- chieu BAN
        if s_st == SEEKING and bar.l < s_low:
            s_low = bar.l

        if s_st == SEEKING and ok and r > mid:
            s_risk = sl_mult * a
            if enable_sell and s_risk > 0:
                s_entry = bar.c
                s_tp = s_low - tp_mult * a
                out.append(Signal(SELL, i, s_entry, s_entry + s_risk, s_tp,
                                  (s_entry - s_tp) / s_risk, i - s_xbar))
            s_st = IDLE

        if s_st == IDLE and ok and r < lo:
            s_st, s_low, s_xbar = SEEKING, bar.l, i

        # ---------------------------------------------------------- chieu MUA
        if b_st == SEEKING and bar.h > b_high:
            b_high = bar.h

        if b_st == SEEKING and ok and r < mid:
            b_risk = sl_mult * a
            if enable_buy and b_risk > 0:
                b_entry = bar.c
                b_tp = b_high + tp_mult * a
                out.append(Signal(BUY, i, b_entry, b_entry - b_risk, b_tp,
                                  (b_tp - b_entry) / b_risk, i - b_xbar))
            b_st = IDLE

        if b_st == IDLE and ok and r > hi:
            b_st, b_high, b_xbar = SEEKING, bar.h, i

    return out
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf tests/pine_oracles/__pycache__ && python -m pytest tests/pine_oracles/test_rsitp_oracle.py -q
```

Kỳ vọng: `1 passed`.

- [ ] **Step 5: Viết mười test còn lại**

Thêm vào cuối `tests/pine_oracles/test_rsitp_oracle.py`:

```python
def test_low_cua_chinh_nen_entry_duoc_tinh_vao_day():
    """Buoc 1 PHAI truoc buoc 2. Nen 2 vua tao day moi vua ban.

    day = min(100, 95) = 95 -> TP = 95 - 2 = 93, rr = (99-93)/6 = 1.0
    Neu buoc 1 chay SAU buoc 2 thi day van la 100 -> TP = 98, rr = 1/6.
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(100, 95, 99)]
    rsi = [60.0, 20.0, 55.0]
    atr = [2.0] * 3

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].tp == 93.0
    assert got[0].rr == 1.0


def test_day_la_min_ca_cua_so_chu_khong_phai_low_nen_entry():
    """day = min(100, 90, 97) = 90 -> TP = 88, rr = (101-88)/6 = 13/6.
    Neu chi lay low cua nen entry (97) thi TP = 95 va rr = 1.0."""
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(95, 90, 92),
            Bar(103, 97, 101)]
    rsi = [60.0, 20.0, 22.0, 55.0]
    atr = [2.0] * 4

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].tp == 88.0
    assert got[0].rr == 13 / 6


def test_thung_25_lan_nua_khong_mo_cua_so_moi():
    """Spec 2.3: cua so lien mach tu cu thung 25 DAU TIEN toi nen entry.
    RSI tut lai duoi 25 o nen 3 chi keo dai day dang theo doi.

    day = min(100, 95, 97) = 95 -> TP = 93, cho = 4 - 1 = 3.
    Neu nen 3 mo cua so moi thi day = min(97, 99) = 97, TP = 95, cho = 1.
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(99, 95, 98),
            Bar(101, 97, 99), Bar(105, 99, 103)]
    rsi = [60.0, 20.0, 40.0, 22.0, 55.0]
    atr = [2.0] * 5

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].tp == 93.0
    assert got[0].wait == 3


def test_rsi_dung_bang_muc_giua_khong_ban():
    """Luat la `>` chat. 50.0 chan; 50.5 moi ban."""
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(103, 99, 102),
            Bar(104, 100, 103)]
    rsi = [60.0, 20.0, 50.0, 50.5]
    atr = [2.0] * 4

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].bar == 3


def test_setup_bi_tieu_thu_sau_khi_ban():
    """Ban xong ve IDLE. Nen 3 co RSI 60 nhung khong con setup nao."""
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(105, 100, 104),
            Bar(108, 103, 107)]
    rsi = [60.0, 20.0, 55.0, 60.0]
    atr = [2.0] * 4

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].bar == 2


def test_mua_guong_qua_75():
    """dinh theo doi = max(200, 205) = 205
    entry = 198, SL = 198 - 6 = 192, TP = 205 + 2 = 207
    rr = (207 - 198) / 6 = 1.5, cho = 3 - 1 = 2
    """
    bars = [Bar(150, 145, 148), Bar(200, 195, 199), Bar(205, 198, 203),
            Bar(202, 196, 198)]
    rsi = [50.0, 80.0, 78.0, 45.0]
    atr = [2.0] * 4

    got = run(bars, rsi, atr)

    assert len(got) == 1
    b = got[0]
    assert b.direction == BUY and b.bar == 3
    assert b.sl == 192.0
    assert b.tp == 207.0
    assert b.rr == 1.5
    assert b.wait == 2


def test_rsi_nhay_tu_24_len_80_trong_mot_nen():
    """Khoi BAN chay TRUOC khoi MUA tren cung mot nen: ban ban ra roi pha mua
    moi mo. Hai chieu khong bao gio cung SEEKING.

    nen 2: BAN ban (day 100 -> TP 98), roi MUA mo pha voi dinh 210.
    nen 3: MUA ban, dinh = max(210, 208) = 210 -> TP = 212, cho = 1.
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(210, 102, 205),
            Bar(208, 200, 206)]
    rsi = [60.0, 24.0, 80.0, 40.0]
    atr = [2.0] * 4

    got = run(bars, rsi, atr)

    assert len(got) == 2
    assert got[0].direction == SELL and got[0].bar == 2 and got[0].tp == 98.0
    assert got[1].direction == BUY and got[1].bar == 3
    assert got[1].tp == 212.0
    assert got[1].wait == 1


def test_atr_bang_0_khong_ban_nhung_van_tieu_thu_setup():
    """Mau so cua rr bang 0 -> khong do duoc rui ro -> khong danh dau. Nhung
    setup VAN bi tieu thu, nen cu thung 25 o nen 4 mo mot cua so MOI.

    `cho == 1` la bang chung: neu setup cu con song thi cho se la 5 - 1 = 4.
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(105, 100, 104),
            Bar(108, 103, 107), Bar(103, 99, 100), Bar(104, 100, 103)]
    rsi = [60.0, 20.0, 55.0, 60.0, 20.0, 55.0]
    atr = [0.0, 0.0, 0.0, 0.0, 2.0, 2.0]

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].bar == 5
    assert got[0].wait == 1


def test_tat_mot_chieu_khong_anh_huong_chieu_kia():
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(105, 100, 104)]
    rsi = [60.0, 20.0, 55.0]
    atr = [2.0] * 3

    assert run(bars, rsi, atr, enable_sell=False) == []
    assert len(run(bars, rsi, atr, enable_buy=False)) == 1


def test_warm_up_khong_lam_gi():
    """rsi hoac atr la None thi khong trang thai nao doi."""
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(103, 99, 100),
            Bar(102, 98, 99), Bar(105, 101, 104)]
    rsi = [None, 20.0, None, 20.0, 55.0]
    atr = [None, None, 2.0, 2.0, 2.0]

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].wait == 1          # cua so mo o nen 3, khong phai nen 1
```

- [ ] **Step 6: Chạy toàn bộ test của oracle**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf tests/pine_oracles/__pycache__ && python -m pytest tests/pine_oracles/test_rsitp_oracle.py -q
```

Kỳ vọng: `11 passed`.

- [ ] **Step 7: Mutation testing — bảy đột biến, tất cả PHẢI chết**

Chạy từng đột biến bằng cách sửa bản sao của oracle trong scratchpad (hoặc sửa rồi khôi phục — nếu làm cách này thì phải xác nhận `git diff` sạch sau đó). Với mỗi con, chạy `python -m pytest tests/pine_oracles/test_rsitp_oracle.py -q` và ghi kết quả:

| # | đột biến | sửa gì |
|---|---|---|
| M1 | đảo bước 1 và bước 2 của chiều BÁN | chuyển khối `if s_st == SEEKING and bar.l < s_low` xuống dưới khối tín hiệu |
| M2 | lấy low của riêng nến entry | đổi `s_tp = s_low - tp_mult * a` thành `s_tp = bar.l - tp_mult * a` |
| M3 | `>` thành `>=` ở mốc giữa | `r > mid` → `r >= mid` |
| M4 | bỏ tiêu thụ setup | xoá dòng `s_st = IDLE` trong khối tín hiệu BÁN |
| M5 | đảo dấu ATR ở SL | `s_entry + s_risk` → `s_entry - s_risk` |
| M6 | đảo dấu ATR ở TP | `s_low - tp_mult * a` → `s_low + tp_mult * a` |
| M7 | cửa sổ mở lại khi thủng 25 lần nữa | đổi `if s_st == IDLE and ok and r < lo` thành `if ok and r < lo` |

**Con nào SỐNG SÓT là thiếu test, không phải "chấp nhận được".** Viết thêm test cho tới khi nó chết, rồi chạy lại cả bảy.

- [ ] **Step 8: Commit**

```bash
git add tests/pine_oracles/rsitp_oracle.py tests/pine_oracles/test_rsitp_oracle.py
git commit -F <scratchpad>/msg-task1.txt
```

Nội dung message (tiếng Việt không dấu): nói rõ oracle nhận rsi/atr tính sẵn và vì sao, và rằng bảy đột biến đều chết.

---

## Task 2: File indicator Pine

**Files:**
- Create: `pine/rsi_trend_pullback_indicator.pine`

**Interfaces:**
- Consumes: `run()` của Task 1 làm bản đối chiếu (đọc tay, không chạy được).
- Produces: khối bọc bởi `// ---- KHOI TIN HIEU ----` và `// ---- HET KHOI TIN HIEU ----` mà Task 4 sẽ chép nguyên văn.

- [ ] **Step 1: Viết file**

Tạo `pine/rsi_trend_pullback_indicator.pine`:

```pine
//@version=6
// =============================================================================
//  RSI Trend Pullback — indicator danh dau (khong dat lenh)
//
//  Setup THEO XU HUONG, nguoc vai voi rsi_failure_swing (bat dinh day). O kia
//  mot cu qua ban roi phan ki la tin hieu DAO CHIEU; o day mot cu qua ban la
//  bang chung xu huong giam dang manh, va cu hoi ve 50 la cho ban tiep.
//
//  May trang thai, chieu BAN (MUA soi guong qua hiLevel):
//    IDLE     rsi < loLevel                        -> SEEKING, dat sLow = low
//    SEEKING  moi nen: sLow = min(sLow, low)
//             rsi > midLevel, nen da dong          -> TIN HIEU, ve IDLE
//
//  KHONG co dieu kien huy, KHONG co han nen. Lua chon co chu y: do phan phoi
//  thoi gian cho that truoc, roi moi quyet co can han hay khong. He qua: rr
//  KHONG co chan tren, nen phai doc rr CUNG VOI so nen cho — ca hai co trong
//  bang, trong nhan va trong alert.
//
//  THU TU BA BUOC TRONG MOT NEN LA CHO CHIU LUC:
//    1. noi cuc tri  2. kiem tin hieu  3. mo pha moi
//  Buoc 1 truoc buoc 2 vi day lay "cho toi nen entry", tuc low cua chinh nen
//  vao lenh phai duoc tinh vao. Dao lai thi TP lech mot nen va sai am tham.
//
//  SO MUC, KHONG BAT CAT: luat la `rsi > midLevel` chu khong phai
//  `rsi[1] <= midLevel and rsi > midLevel`. Hai ly do — no dung chu de bai
//  ("sell tai cay nen co rsi > 50"), va no khong vo khi lo mot nen: tin hieu
//  bi gac bang barstate.isconfirmed, nen voi bat cat mot lan lo tick dong nen
//  se lam setup KET o SEEKING vinh vien. Voi so muc no chi ban muon mot nen.
//  So muc khong sinh tin hieu thua vi SEEKING chi ton tai sau khi da thay
//  rsi < loLevel.
//
//  Gia (chieu BAN):
//    entry = close nen xac nhan
//    SL    = entry + slAtrMult * ATR
//    TP    = sLow  - tpAtrMult * ATR
//    rr    = (entry - TP) / (SL - entry)
//  sLow <= low nen entry <= close, nen TP luon duoi entry va SL luon tren
//  entry. Khong can guard. Chi chan luc rsi/atr con na, va chan mau so cua rr
//  bang 0 (atr = 0) — khong do duoc rui ro thi khong danh dau.
//
//  Pane: file nay nam o PANE GIA (overlay=true) va KHONG ve RSI. Co chu y, va
//  khac rsi_failure_swing: file kia dung force_overlay (14 cho) de day doi
//  tuong sang pane gia, ma force_overlay chua bao gio compile duoc o may nay.
//  Khong co ly do gi de cuoc file moi vao cung mot thu chua kiem chung. Muon
//  nhin RSI thi bat indicator RSI dung san; bang trang thai van in RSI hien tai.
//
//  Phan ve KHONG dung mot doi tuong line nao: line.new bi chan cung 500 va khi
//  tran thi cai cu nhat LANG LE bien mat (kill_peak da mac). Dung plot voi
//  style_linebr — khong co tran nao.
//
//  Kiem chung: may trang thai duoc dung lai bang Python o
//  tests/pine_oracles/rsitp_oracle.py voi 11 test va 7 dot bien deu chet.
//  Pine KHONG compile duoc o may viet ra file nay. Phan VE va BANG khong co
//  test, chi soat tay.
//
//  Companion: pine/rsi_trend_pullback_strategy.pine chay cung khoi tin hieu
//  voi lenh; tests/test_pine_blocks.py canh hai ban khong troi khoi nhau.
// =============================================================================
indicator("RSI Trend Pullback", overlay=true, max_labels_count=500)

// ---------------------------------------------------------------- inputs
grpRsi   = "RSI"
rsiLen   = input.int(14, "RSI length", minval=2, group=grpRsi)
loLevel  = input.float(25, "Muc thung xuong (mo pha BAN)", group=grpRsi)
midLevel = input.float(50, "Muc xac nhan", group=grpRsi)
hiLevel  = input.float(75, "Muc vuot len (mo pha MUA)", group=grpRsi)

grpRisk   = "Rui ro"
atrLen    = input.int(14, "ATR length", minval=1, group=grpRisk)
slAtrMult = input.float(3.0, "SL (x ATR)", minval=0.1, step=0.5, group=grpRisk)
tpAtrMult = input.float(1.0, "TP qua cuc tri (x ATR)", minval=0, step=0.5, group=grpRisk)

grpDir     = "Chieu"
enableSell = input.bool(true, "Enable SELL", group=grpDir)
enableBuy  = input.bool(true, "Enable BUY", group=grpDir)

grpShow    = "Hien thi"
showTint   = input.bool(true, "To nen luc dang cho", group=grpShow)
showLevel  = input.bool(true, "Cuc tri dang theo doi", group=grpShow)
showSig    = input.bool(true, "Mui ten tin hieu", group=grpShow)
showLabels = input.bool(true, "Nhan chi tiet", group=grpShow)
showTable  = input.bool(true, "Bang trang thai", group=grpShow)
holdBars   = input.int(20, "Giu SL/TP bao nhieu nen", minval=1, group=grpShow)

// ---- KHOI TIN HIEU ----
// ta.* phai o top level: chung giu state noi bo, goi trong if la sai am tham
float rsi = ta.rsi(close, rsiLen)
float atr = ta.atr(atrLen)
bool  ok  = not na(rsi) and not na(atr)

// trang thai: 0 IDLE, 1 SEEKING
var int   sSt   = 0
var float sLow  = na
var int   sXBar = na
var int   bSt   = 0
var float bHigh = na
var int   bXBar = na

bool  sSig   = false
float sEntry = na
float sSl    = na
float sTp    = na
float sRr    = na
int   sWait  = na
bool  bSig   = false
float bEntry = na
float bSl    = na
float bTp    = na
float bRr    = na
int   bWait  = na

// ---- chieu BAN ----
// 1. noi cuc tri — PHAI truoc buoc 2
if sSt == 1 and low < sLow
    sLow := low

// 2. tin hieu — PHAI truoc buoc 3
if sSt == 1 and ok and rsi > midLevel and barstate.isconfirmed
    float sRisk = slAtrMult * atr
    if enableSell and sRisk > 0
        sSig   := true
        sEntry := close
        sSl    := close + sRisk
        sTp    := sLow - tpAtrMult * atr
        sRr    := (sEntry - sTp) / sRisk
        sWait  := bar_index - sXBar
    sSt := 0

// 3. mo pha
if sSt == 0 and ok and rsi < loLevel
    sSt   := 1
    sLow  := low
    sXBar := bar_index

// ---- chieu MUA (guong) ----
if bSt == 1 and high > bHigh
    bHigh := high

if bSt == 1 and ok and rsi < midLevel and barstate.isconfirmed
    float bRisk = slAtrMult * atr
    if enableBuy and bRisk > 0
        bSig   := true
        bEntry := close
        bSl    := close - bRisk
        bTp    := bHigh + tpAtrMult * atr
        bRr    := (bTp - bEntry) / bRisk
        bWait  := bar_index - bXBar
    bSt := 0

if bSt == 0 and ok and rsi > hiLevel
    bSt   := 1
    bHigh := high
    bXBar := bar_index
// ---- HET KHOI TIN HIEU ----

// ---------------------------------------------------------------- ve
color sTint = color.new(color.red, 92)
color bTint = color.new(color.teal, 92)
bgcolor(showTint ? (sSt == 1 ? sTint : bSt == 1 ? bTint : na) : na, title="Dang cho")

plot(showLevel and sSt == 1 ? sLow : na, "Day dang theo doi",
     color=color.new(color.red, 20), style=plot.style_linebr, linewidth=1)
plot(showLevel and bSt == 1 ? bHigh : na, "Dinh dang theo doi",
     color=color.new(color.teal, 20), style=plot.style_linebr, linewidth=1)

var float slPlot   = na
var float tpPlot   = na
var int   plotTill = na
var float lastRr   = na
if sSig or bSig
    slPlot   := sSig ? sSl : bSl
    tpPlot   := sSig ? sTp : bTp
    plotTill := bar_index + holdBars
    lastRr   := sSig ? sRr : bRr
if not na(plotTill) and bar_index > plotTill
    slPlot   := na
    tpPlot   := na
    plotTill := na

plot(slPlot, "SL", color=color.new(color.red, 0),
     style=plot.style_linebr, linewidth=1)
plot(tpPlot, "TP", color=color.new(color.teal, 0),
     style=plot.style_linebr, linewidth=1)

plotshape(showSig and sSig, title="SELL", style=shape.triangledown,
     location=location.abovebar, color=color.new(color.red, 0),
     size=size.small, text="S")
plotshape(showSig and bSig, title="BUY", style=shape.triangleup,
     location=location.belowbar, color=color.new(color.teal, 0),
     size=size.small, text="B")

if showLabels and sSig
    label.new(bar_index, high, "SELL  rr " + str.tostring(sRr, "0.00")
         + "\nentry " + str.tostring(sEntry, format.mintick)
         + "\nSL " + str.tostring(sSl, format.mintick)
         + "\nTP " + str.tostring(sTp, format.mintick)
         + "\ncho " + str.tostring(sWait) + " nen",
         style=label.style_label_down, color=color.new(color.red, 20),
         textcolor=color.white, size=size.small)
if showLabels and bSig
    label.new(bar_index, low, "BUY  rr " + str.tostring(bRr, "0.00")
         + "\nentry " + str.tostring(bEntry, format.mintick)
         + "\nSL " + str.tostring(bSl, format.mintick)
         + "\nTP " + str.tostring(bTp, format.mintick)
         + "\ncho " + str.tostring(bWait) + " nen",
         style=label.style_label_up, color=color.new(color.teal, 20),
         textcolor=color.white, size=size.small)

// ---------------------------------------------------------------- bang
f_st(s) =>
    s == 1 ? "dang cho" : "—"

var table tbl = na
if showTable and barstate.islast
    if na(tbl)
        tbl := table.new(position.top_right, 2, 6, border_width=1)
    table.cell(tbl, 0, 0, "RSI(" + str.tostring(rsiLen) + ") / ATR", text_size=size.small)
    table.cell(tbl, 1, 0, str.tostring(rsi, "0.#") + " / " + str.tostring(atr, format.mintick), text_size=size.small)
    table.cell(tbl, 0, 1, "BAN", text_size=size.small)
    table.cell(tbl, 1, 1, f_st(sSt), text_size=size.small)
    table.cell(tbl, 0, 2, "  day / cho", text_size=size.small)
    table.cell(tbl, 1, 2, sSt == 1 ? str.tostring(sLow, format.mintick) + " / " + str.tostring(bar_index - sXBar) : "—", text_size=size.small)
    table.cell(tbl, 0, 3, "MUA", text_size=size.small)
    table.cell(tbl, 1, 3, f_st(bSt), text_size=size.small)
    table.cell(tbl, 0, 4, "  dinh / cho", text_size=size.small)
    table.cell(tbl, 1, 4, bSt == 1 ? str.tostring(bHigh, format.mintick) + " / " + str.tostring(bar_index - bXBar) : "—", text_size=size.small)
    table.cell(tbl, 0, 5, "rr tin hieu cuoi", text_size=size.small)
    table.cell(tbl, 1, 5, na(lastRr) ? "—" : str.tostring(lastRr, "0.00"), text_size=size.small)

// ---------------------------------------------------------------- alert
if sSig
    alert('{"symbol":"' + syminfo.ticker + '","tf":"' + timeframe.period + '","direction":"SELL","setup":"RSITP"' + ',"entry":' + str.tostring(sEntry, "0.#####") + ',"sl":' + str.tostring(sSl, "0.#####") + ',"tp":' + str.tostring(sTp, "0.#####") + ',"rr":' + str.tostring(sRr, "0.###") + ',"wait":' + str.tostring(sWait) + '}', alert.freq_once_per_bar_close)
if bSig
    alert('{"symbol":"' + syminfo.ticker + '","tf":"' + timeframe.period + '","direction":"BUY","setup":"RSITP"' + ',"entry":' + str.tostring(bEntry, "0.#####") + ',"sl":' + str.tostring(bSl, "0.#####") + ',"tp":' + str.tostring(bTp, "0.#####") + ',"rr":' + str.tostring(bRr, "0.###") + ',"wait":' + str.tostring(bWait) + '}', alert.freq_once_per_bar_close)
```


- [ ] **Step 2: Checker tĩnh — thụt dòng nối tiếp**

```bash
awk 'match($0,/^ +/){n=RLENGTH; l=$0; sub(/^ +/,"",l); if (l ~ /^(and |or |\+ |color=|style=|location=|textcolor=|size=|group=|minval=|step=|tooltip=)/) print NR": indent "n" -> "(n%4==0?"*** LOI ***":"ok")}' pine/rsi_trend_pullback_indicator.pine
```

Kỳ vọng: mọi dòng in ra đều `ok`. Một dòng `*** LOI ***` nghĩa là thụt chia hết cho 4 — Pine sẽ đọc dòng đó thành khối mới, không báo lỗi, chỉ đổi hành vi.

**Lệnh này đã được chạy thật trên `pine/rsi_failure_swing_indicator.pine`: 16 dòng, 4 dòng indent 5 và 12 dòng indent 9, không dòng nào `*** LOI ***`.** Nhánh `\+ ` trong bộ lọc là bắt buộc — nó bắt các dòng nối tiếp của `label.new`, đúng chỗ dễ sai nhất; một bản trước của lệnh này bỏ sót nó. Nếu nó in ra hàng trăm dòng thì bộ lọc sai chứ không phải file sai — báo lên, đừng sửa file. (Ở dự án `momentum_expansion`, một lệnh awk sai bộ lọc đã báo 137 "vi phạm" trên một file hoàn toàn sạch.)

- [ ] **Step 3: Checker tĩnh — ba luật còn lại**

```bash
grep -n "line\.new" pine/rsi_trend_pullback_indicator.pine ; echo "--- het (trong = sach) ---"
grep -n '"#\.#####"' pine/rsi_trend_pullback_indicator.pine ; echo "--- het (trong = sach) ---"
awk '/^[ \t]+.*ta\.(rsi|atr)\(/{print NR": "$0}' pine/rsi_trend_pullback_indicator.pine ; echo "--- het (trong = sach) ---"
```

Cả ba phải không in ra dòng nào: không `line.new`, không `"#.#####"`, không `ta.*` nằm trong khối thụt.

- [ ] **Step 4: Đối chiếu tay với oracle — ca `test_ban_day_du`**

Lần theo file Pine bằng tay trên đúng dữ liệu của test đầu tiên ở Task 1:

| nến | rsi | low | close | sau bước 1 | bước 2 | sau bước 3 |
|---|---|---|---|---|---|---|
| 0 | 60 | 105 | 108 | — (IDLE) | — | IDLE (60 < 25 sai) |
| 1 | 20 | 100 | 101 | — (IDLE) | — | SEEKING, `sLow=100`, `sXBar=1` |
| 2 | 22 | 98 | 99 | `sLow=98` | 22 > 50 sai | — |
| 3 | 35 | 99 | 100 | 99 < 98 sai | 35 > 50 sai | — |
| 4 | 55 | 101 | 104 | 101 < 98 sai | **BẮN** | — |

Tại nến 4: `sEntry=104`, `sSl=104+3×2=110`, `sTp=98−1×2=96`, `sRr=(104−96)/6=1.3333`, `sWait=4−1=3`.

Khớp từng số với `test_ban_day_du`. **Lệch một số nào là DỪNG và báo** — nhiều khả năng file Pine sai thứ tự bước, không phải test sai.

- [ ] **Step 5: Đối chiếu tay — ca `test_low_cua_chinh_nen_entry_duoc_tinh_vao_day`**

Ca này là ca bắt lỗi thứ tự, nên phải lần riêng:

| nến | rsi | low | close | sau bước 1 | bước 2 |
|---|---|---|---|---|---|
| 1 | 20 | 100 | 101 | — | — |
| 2 | 55 | 95 | 99 | `sLow=95` | **BẮN**, `sTp=95−2=93` |

Nếu trong file Pine khối `if sSt == 1 and low < sLow` nằm **sau** khối tín hiệu thì `sTp` sẽ là `100−2=98`, và `rr` thành `1/6` thay vì `1.0`. Đọc lại đúng thứ tự hai khối đó trong file trước khi đi tiếp.

- [ ] **Step 6: Commit**

```bash
git add pine/rsi_trend_pullback_indicator.pine
git commit -F <scratchpad>/msg-task2.txt
```

Message phải nói rõ: **chưa compile**, đã qua checker tĩnh nào, và đã đối chiếu tay hai ca nào với oracle.

---

## Task 3: Guard chống trôi bản chép, chạy trong pytest

`blockdiff.py` hiện chỉ tồn tại trong thư mục scratchpad của một phiên **đã kết thúc**. Phiên đó mất thì guard mất, trong khi header của bốn file Pine vẫn trỏ vào nó. Đây đúng bài học đã ghi ở dự án `momentum_expansion`: **bằng chứng phải nằm trong version control**.

Task này chuyển nó thành một test thật, nên guard **tự chạy trong mỗi lần pytest** thay vì chờ ai đó nhớ gọi tay.

**Files:**
- Create: `tests/pine_blocks.py`
- Create: `tests/test_pine_blocks.py`

**Interfaces:**
- Produces: `collect_blocks(pine_dir) -> dict[str, dict[str, list[str]]]` — `{ten_vung: {ten_file: cac_dong}}`
- Produces: `drift(pine_dir, allowed) -> list[str]` — mô tả từng chỗ lệch ngoài danh sách ngoại lệ
- Produces: `ALLOWED` — ngoại lệ có chủ ý, dạng `{(ten_vung, file_goc, file_so): [(dong_goc, dong_so), ...]}`

- [ ] **Step 1: Viết test fail**

Tạo `tests/test_pine_blocks.py`:

```python
"""Guard chong troi giua cac ban chep khoi Pine.

Pine khong co module system, nen ban strategy CHEP NGUYEN VAN khoi tin hieu
tu ban indicator. Khong co gi canh thi hai ban troi khoi nhau am tham va
chart ve mot dang con lenh chay mot dang khac.

Truoc day guard nay la mot script trong scratchpad cua phien lam viec. Phien
ket thuc thi guard bien mat trong khi header cua bon file Pine van tro vao no.
Gio no la test, nen no tu chay.
"""
from pathlib import Path

from pine_blocks import ALLOWED, collect_blocks, drift

PINE = Path(__file__).resolve().parent.parent / "pine"


def test_khong_co_cho_nao_troi_ngoai_danh_sach_ngoai_le():
    assert drift(PINE, ALLOWED) == []


def test_guard_that_su_thay_cac_vung_dang_co():
    """Neu bo loc hong thi drift() tra ve rong VI KHONG THAY GI, va test tren
    xanh vi ly do sai. Ghim rang cac vung that su duoc gom."""
    blocks = collect_blocks(PINE)
    assert "TIN HIEU" in blocks
    assert len(blocks["TIN HIEU"]) >= 2


def test_ngoai_le_ghi_dich_danh_ca_hai_dong():
    """Ngoai le phai la cap dong cu the, KHONG phai nguong "cho lech N dong" —
    nguong thi bat cu cho troi nao khac cung lot qua."""
    for key, pairs in ALLOWED.items():
        assert len(key) == 3
        for old, new in pairs:
            assert isinstance(old, str) and isinstance(new, str)
            assert old != new
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf tests/__pycache__ && python -m pytest tests/test_pine_blocks.py -q
```

Kỳ vọng: FAIL, `ModuleNotFoundError: No module named 'pine_blocks'`.

- [ ] **Step 3: Viết module**

Tạo `tests/pine_blocks.py`:

```python
"""Gom cac vung duoc boc bang moc va so tung dong giua cac ban chep.

Moi khoi dung chung duoc boc bang mot cap moc:
    // ---- KHOI <ten> ----
    ...
    // ---- HET KHOI <ten> ----

File dau tien theo thu tu alphabet lam ban goc.

Nhung cho CO Y lech nhau ghi dich danh trong ALLOWED — ghi CA NOI DUNG hai
dong, khong phai "cho lech N dong": mot nguong dem thi bat cu cho troi nao
khac cung lot qua.
"""
import difflib
import re

OPEN = re.compile(r"^//\s*----\s*KHOI\s+(.+?)\s*----\s*$")
CLOSE = re.compile(r"^//\s*----\s*HET KHOI\s+(.+?)\s*----\s*$")

# (ten_vung, file_goc, file_so) -> [(dong_trong_file_goc, dong_trong_file_so)]
#
# kill_peak: khoi tin hieu duoc phep lech DUNG hai dong gate vi the. Da ghi
# trong header ca hai file. Bat cu cho lech thu ba nao la troi that.
ALLOWED = {
    ("TIN HIEU", "kill_peak_indicator.pine", "kill_peak_strategy.pine"): [
        ("if lowConf and enableBuy and flagBuy and not posOpen and not na(prevLowP) and not na(atr)",
         "if lowConf and enableBuy and flagBuy and strategy.position_size == 0 and not na(prevLowP) and not na(atr)"),
        ("if highConf and enableSell and flagSell and not posOpen and not na(prevHighP) and not na(atr)",
         "if highConf and enableSell and flagSell and strategy.position_size == 0 and not na(prevHighP) and not na(atr)"),
    ],
}


def collect_blocks(pine_dir):
    """{ten_vung: {ten_file: [cac dong ben trong, khong ke hai moc]}}"""
    out = {}
    for path in sorted(pine_dir.glob("*.pine")):
        name = None
        buf = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if name is None:
                m = OPEN.match(line)
                if m:
                    name, buf = m.group(1), []
                continue
            m = CLOSE.match(line)
            if m:
                out.setdefault(name, {})[path.name] = buf
                name = None
                continue
            buf.append(line)
    return out


def _diff_pairs(a, b):
    """Cac cap (dong_cu, dong_moi). Dong chi co o mot ben ghep voi chuoi rong."""
    pairs = []
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        old = a[i1:i2]
        new = b[j1:j2]
        for k in range(max(len(old), len(new))):
            pairs.append((old[k] if k < len(old) else "",
                          new[k] if k < len(new) else ""))
    return pairs


def drift(pine_dir, allowed):
    """Mo ta tung cho lech KHONG nam trong `allowed`. Rong = sach."""
    problems = []
    for region, by_file in sorted(collect_blocks(pine_dir).items()):
        names = sorted(by_file)
        if len(names) < 2:
            continue
        base = names[0]
        for other in names[1:]:
            ok = list(allowed.get((region, base, other), []))
            for old, new in _diff_pairs(by_file[base], by_file[other]):
                if (old, new) in ok:
                    continue
                problems.append(
                    "%s: %s vs %s\n  -%s\n  +%s" % (region, base, other, old, new)
                )
    return problems
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf tests/__pycache__ && python -m pytest tests/test_pine_blocks.py -q
```

Kỳ vọng: `3 passed`.

**Nếu `test_khong_co_cho_nao_troi_ngoai_danh_sach_ngoai_le` ĐỎ:** nghĩa là hai bản chép đang có trong repo đã trôi khỏi nhau thật. **DỪNG và báo — tuyệt đối không nới `ALLOWED` cho hết đỏ.** Nới ngoại lệ để test xanh là đúng cái mà guard này sinh ra để chặn.

- [ ] **Step 5: Chạy cả suite**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf __pycache__ tests/__pycache__ tests/pine_oracles/__pycache__ rsi_fvg/__pycache__ && python -m pytest -q
```

Kỳ vọng: `430 passed, 2 failed` (416 mốc + 11 của Task 1 + 3 của Task 3; hai ca đỏ là MT5 môi trường).

- [ ] **Step 6: Commit**

```bash
git add tests/pine_blocks.py tests/test_pine_blocks.py
git commit -F <scratchpad>/msg-task3.txt
```

---

## Task 4: File strategy

**Files:**
- Create: `pine/rsi_trend_pullback_strategy.pine`

**Interfaces:**
- Consumes: khối `KHOI TIN HIEU` của Task 2, **chép nguyên văn từng byte**.
- Consumes: guard của Task 3 để chứng minh bản chép không trôi.

- [ ] **Step 1: Dựng file bằng cách chép khối**

Chép `pine/rsi_trend_pullback_indicator.pine` thành file mới, rồi đổi **ba chỗ, và chỉ ba chỗ nằm NGOÀI khối `KHOI TIN HIEU`**:

1. Đổi dòng `indicator(...)` thành:

```pine
strategy("RSI Trend Pullback Strategy", overlay=true, initial_capital=10000,
     default_qty_type=strategy.fixed, currency=currency.NONE,
     commission_type=strategy.commission.percent, commission_value=0.0,
     process_orders_on_close=false, max_labels_count=500)
```

`max_labels_count=500` **bắt buộc khai tường minh**: `strategy()` mặc định **50** chứ không phải 500 như `indicator()`. Bỏ sót thì nhãn cũ lặng lẽ biến mất trên chart backtest.

2. Thêm một input vào nhóm `Rui ro`, ngay sau `tpAtrMult`:

```pine
riskPct = input.float(1.0, "Rui ro moi lenh (% equity)", minval=0.01, step=0.25, group=grpRisk)
```

3. Thêm khối đặt lệnh **ngay sau** `// ---- HET KHOI TIN HIEU ----`, trước phần vẽ:

```pine
// ---------------------------------------------------------------- lenh
if sSig and strategy.position_size == 0
    float sSlDist = sSl - sEntry
    if sSlDist > 0
        float sRiskUsd = strategy.equity * riskPct / 100.0
        float sQty     = sRiskUsd / (sSlDist * syminfo.pointvalue)
        strategy.entry("S", strategy.short, qty=sQty, comment="SELL rsi tp")
        strategy.exit("SX", from_entry="S", stop=sSl, limit=sTp)
if bSig and strategy.position_size == 0
    float bSlDist = bEntry - bSl
    if bSlDist > 0
        float bRiskUsd = strategy.equity * riskPct / 100.0
        float bQty     = bRiskUsd / (bSlDist * syminfo.pointvalue)
        strategy.entry("L", strategy.long, qty=bQty, comment="BUY rsi tp")
        strategy.exit("LX", from_entry="L", stop=bSl, limit=bTp)
```

Tên biến cục bộ có tiền tố `s`/`b` để hai khối `if` anh em không khai trùng tên — xem Global Constraints.

Bộ lọc vị thế nằm **ngoài** khối chép. Đó chính là thứ giữ cho khối chép giống hệt từng byte, và là lý do guard của Task 3 dùng được.

Header file cũng phải sửa: nói rõ đây là bản strategy, khối tín hiệu chép nguyên văn từ bản indicator, và guard nào canh.

- [ ] **Step 2: Chạy guard — phải xanh**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf tests/__pycache__ && python -m pytest tests/test_pine_blocks.py -q
```

Kỳ vọng: `3 passed`. Đỏ nghĩa là khối chép đã trôi — **sửa file strategy cho khớp bản indicator, KHÔNG thêm vào `ALLOWED`.** Cặp file này không có chỗ lệch nào được phép: khác với `kill_peak`, toàn bộ phần khác biệt đã nằm ngoài khối.

- [ ] **Step 3: Checker tĩnh trên file mới**

Chạy lại đúng bốn lệnh của Task 2 Step 2 và Step 3, đổi tên file thành `pine/rsi_trend_pullback_strategy.pine`. Cùng kỳ vọng.

- [ ] **Step 4: Chạy cả suite**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && rm -rf __pycache__ tests/__pycache__ tests/pine_oracles/__pycache__ rsi_fvg/__pycache__ && python -m pytest -q
```

Kỳ vọng: `430 passed, 2 failed` — không đổi so với Task 3, vì Task 4 không thêm test nào; nó chỉ làm guard sẵn có phải kiểm thêm một cặp file.

- [ ] **Step 5: Commit**

```bash
git add pine/rsi_trend_pullback_strategy.pine
git commit -F <scratchpad>/msg-task4.txt
```

---

## Self-Review

**1. Spec coverage** — soi từng mục của spec, chỉ ra task nào làm:

| spec | task |
|---|---|
| §2.0 khai báo, `overlay=true`, `max_labels_count` | Task 2 (indicator), Task 4 (strategy) |
| §2.1 ba mốc | Task 2 (input) |
| §2.2 so mức chứ không bắt cắt | Task 1 (oracle `r > mid`), Task 2 |
| §2.3 máy trạng thái BÁN | Task 1, Task 2 |
| §2.4 máy trạng thái MUA | Task 1, Task 2 |
| §2.5 thứ tự ba bước | Task 1 (đột biến M1, M7), Task 2 Step 4 và Step 5 |
| §2.6 giá, `rr`, mẫu số bằng 0 | Task 1 (`test_atr_bang_0...`), Task 2 |
| §2.7 setup bị tiêu thụ | Task 1 (M4, `test_setup_bi_tieu_thu...`, `test_atr_bang_0...`) |
| §3 không repaint, `barstate.isconfirmed` | Task 2 — **không có test tự động**, xem hạn chế dưới |
| §4.1 không dùng `line.new` | Task 2 Step 3 (grep), Task 4 Step 3 |
| §4.2 giữ SL/TP `holdBars` nến | Task 2 |
| §4.3 mọi lệnh vẽ gác bằng `sSig`/`bSig` | Task 2 — soát tay |
| §5 alert, `"0.#####"` | Task 2 Step 3 (grep), Task 4 Step 3 |
| §6 bảng trạng thái | Task 2 |
| §7 input | Task 2, Task 4 (`riskPct`) |
| §8.1 oracle trong version control | Task 1 |
| §8.2 mutation testing | Task 1 Step 7 |
| §8.3 `blockdiff` canh bản chép | **Task 3** — spec giả định công cụ đã có; thực tế nó chỉ sống trong scratchpad của một phiên đã kết thúc, nên Task 3 đưa nó vào repo thành test. Đây là phần **mở rộng phạm vi có chủ ý** so với spec. |
| §8.4 checker thụt dòng | Task 2 Step 2 |
| §8.5 không `ta.*` trong `if` | Task 2 Step 3 |
| §9 hai file và khối chép | Task 2 (mốc), Task 4 (bản chép) |
| §10 những gì cố ý không làm | không task nào — đúng, đó là danh sách phủ định |
| §11 rủi ro đã biết | ghi trong header file Pine (Task 2) |

**2. Placeholder scan** — không có "TBD", "TODO", "tương tự Task N", hay bước nào mô tả mà không có code. Ba chỗ ghi `<scratchpad>` là đường dẫn thật mà người thi công tự điền theo môi trường phiên của họ, không phải placeholder nội dung.

**3. Type consistency** — `Bar(h, l, c)` và `Signal(direction, bar, entry, sl, tp, rr, wait)` khai ở Task 1 và dùng đúng tên đó trong mọi test. Tên biến Pine (`sSt`, `sLow`, `sXBar`, `bSt`, `bHigh`, `bXBar`, `sSig`, `sEntry`, `sSl`, `sTp`, `sRr`, `sWait`) khai ở Task 2 và dùng lại đúng ở Task 4. Bảng ánh xạ ở đầu plan khớp cả hai.

### Hai hạn chế đã biết của chính kế hoạch này

1. **`barstate.isconfirmed` không có test tự động.** Oracle không mô hình khái niệm "nến đã đóng" — nó chạy trên chuỗi nến đã đóng sẵn, nên nó không phân biệt được bản có gác và bản không gác. Chỗ này chỉ được soát tay. Chấp nhận được vì trên nến lịch sử `barstate.isconfirmed` luôn đúng, tức nó không đổi một bit nào của backtest; nó chỉ ảnh hưởng nến live.

2. **Phần vẽ và bảng không có test nào.** Giống mọi file Pine khác trong repo. Bất biến "mọi lệnh vẽ gác bằng `sSig`/`bSig`, không lệnh nào tính lại điều kiện" (§4.3) chỉ được soát tay — và đó chính là lỗi mà `kill_peak` đã mắc một lần.
