# Momentum Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một indicator TradingView đánh dấu ba nến liên tiếp cho thấy động lượng tăng tiến, kèm alert.

**Architecture:** Một file Pine không state, không MTF, không lệnh — pattern là hàm thuần của ba nến gần nhất. Rủi ro duy nhất đáng kể là lệch chỉ số khi dịch `n1/n2/n3` sang `[0]/[1]/[2]`, nên một oracle Python nhỏ được viết **trước** để làm bản đối chiếu, và một vòng soát riêng do người khác làm ở cuối.

**Tech Stack:** Pine Script v6; Python 3 + pytest cho oracle (chạy trong scratchpad, không commit).

**Spec:** `docs/superpowers/specs/2026-09-13-momentum-expansion-indicator-design.md`

## Global Constraints

Đọc hết trước khi bắt đầu bất kì task nào.

- **KHÔNG COMPILE ĐƯỢC PINE Ở MÁY NÀY.** Không bao giờ viết "đã test", "đã chạy", "verified", "works" về code Pine. Chỉ được nói "qua checker tĩnh", "đối chiếu với oracle", "đọc tay".
- **Thụt dòng nối tiếp trong Pine phải KHÔNG chia hết cho 4.** Repo dùng 5, 9, 13. Thụt 4 hoặc 8 bị Pine đọc thành khối mới — không báo lỗi, chỉ đổi hành vi.
- **Không gọi `ta.*` bên trong `if`.** File này không dùng `ta.*` nào, nhưng luật vẫn áp nếu có ai thêm.
- **Doji không tính, so sánh giá chặt.** `close > open` và `close[1] > high[2]` — dùng `>` chứ không `>=`, ở mọi chỗ. Spec §2.6.
- **Windows: xoá `__pycache__` trước mỗi lần chạy pytest.** Lệnh: `rm -rf __pycache__`. Hai lần ghi file liên tiếp có thể cho mtime giống hệt nhau và Python dùng lại bytecode cũ — chuyện này đã gây chạy xanh giả trong repo này.
- **Scratchpad:** `C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad`. Viết tắt `<SP>`. File Python kiểm chứng nằm ở đó, **không commit**.
- **Dùng công cụ Write cho nội dung file.** Heredoc bash trên máy này vỡ khi nội dung có nháy; chỉ khối `python - <<'PYEOF'` thuần Python là tin được.
- **Commit message:** tiếng Việt không dấu, ASCII, viết vào file `.txt` trong scratchpad rồi `git commit -F <file>`. Dòng cuối đúng nguyên văn:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- **Nhánh:** `feat/h4-kill-study`. Không merge, không push.
- **Nếu một bước trong kế hoạch này mâu thuẫn với thực tế, DỪNG và báo — không tự sửa test cho khớp code.** Ở dự án trước, giá trị test tính tay trong kế hoạch đã sai ba lần; người thi công báo lên đúng thay vì sửa lén, và đó là hành vi mong muốn.

### Ánh xạ chỉ số — dùng xuyên suốt

| Tên người dùng | Pine | Oracle | Vai trò |
|---|---|---|---|
| `n1` | `close`, `low`, `high` (không hậu tố) | tham số thứ **ba** | nến hiện tại, chốt pattern |
| `n2` | `[1]` | tham số thứ **hai** | nến giữa |
| `n3` | `[2]` | tham số thứ **nhất** | nến cũ nhất |

Oracle nhận `(n3, n2, n1)` — **ngược** thứ tự chỉ số Pine — là cố ý: chỗ dịch giữa hai cách đánh số nằm ở đúng một nơi và bị test soi thẳng vào.

---

## Cấu trúc file

| File | Trách nhiệm | Task |
|---|---|---|
| `<SP>/momexp_oracle.py` | `Candle`, `detect(n3, n2, n1)` | 1 |
| `<SP>/momexp_test.py` | test + mutation cho oracle | 1 |
| `pine/momentum_expansion.pine` | indicator | 2 |

---

## Task 1: Oracle Python và test

Oracle được viết **trước** file Pine, để Task 2 có bản đối chiếu sẵn và Task 3 có thứ để soi.

**Files:**
- Create: `<SP>/momexp_oracle.py`
- Create: `<SP>/momexp_test.py`

**Interfaces:**
- Produces: `Candle = namedtuple("Candle", "o h l c")`
- Produces: `detect(n3, n2, n1) -> "BULL" | "BEAR" | None`
- Produces: hằng `BULL = "BULL"`, `BEAR = "BEAR"`
- Task 2 và Task 3 dùng `detect` làm bản gốc để đối chiếu từng dòng.

**Không commit gì trong task này** — scratchpad không được git theo dõi. Bỏ mọi bước `git commit`.

- [ ] **Step 1: Viết test đầu tiên — ca BULL đầy đủ**

Tạo `<SP>/momexp_test.py`:

```python
"""Test cho momexp_oracle — pattern ba nen tang tien dong luong.

Moi nen la Candle(o, h, l, c). Thu tu tham so cua detect la (n3, n2, n1),
tuc CU NHAT TRUOC — nguoc voi chi so Pine [2],[1],[0]. Co y nhu vay: cho
dich giua hai cach danh so nam o dung mot noi.
"""
import random

from momexp_oracle import BEAR, BULL, Candle, detect


# Bang so cua spec section 2.5
N3_BULL = Candle(100.0, 103.0, 99.0, 102.0)
N2_BULL = Candle(102.0, 105.0, 101.0, 104.0)
N1_BULL = Candle(104.0, 107.0, 103.5, 106.0)


def test_bull_day_du():
    assert detect(N3_BULL, N2_BULL, N1_BULL) == BULL
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest momexp_test.py -q
```

Kỳ vọng: FAIL, `ModuleNotFoundError: No module named 'momexp_oracle'`.

- [ ] **Step 3: Viết oracle**

Tạo `<SP>/momexp_oracle.py`:

```python
"""Pattern ba nen tang tien dong luong.

Spec: docs/superpowers/specs/2026-09-13-momentum-expansion-indicator-design.md

Ban goc de doi chieu voi pine/momentum_expansion.pine. Rui ro so mot cua
file Pine la LECH CHI SO: nguoi dung dat ten n1 moi nhat / n3 cu nhat,
con Pine danh so [0],[1],[2] cung lui ve qua khu. Lech mot chi so thi
pattern van chay, van ve, va sai am tham.

Vi vay detect() nhan tham so theo TEN CUA NGUOI DUNG — (n3, n2, n1), cu
nhat truoc — chu khong theo thu tu chi so Pine. Cho dich giua hai cach
danh so vi the nam o dung mot noi va bi test soi thang vao.
"""
from collections import namedtuple

Candle = namedtuple("Candle", "o h l c")

BULL = "BULL"
BEAR = "BEAR"


def _green(x):
    """Doji khong tinh la xanh: luat la `>` chat. Spec section 2.6."""
    return x.c > x.o


def _red(x):
    return x.c < x.o


def detect(n3, n2, n1):
    """n3 cu nhat, n1 moi nhat. Tra ve BULL, BEAR hoac None.

    Bon dieu kien chieu tang, moi cai doc lap (spec section 2.4):
      1. ca ba nen xanh
      2. n2 dong tren dinh n3
      3. n1 dong tren dinh n2
      4. n1 thoat han range n3

    Dieu kien 4 dung dinh cua N3 chu khong phai n2: n1 duoc phep chong lan
    n2. Bat doi xung nay la co y, xem spec section 2.5.
    """
    if (_green(n3) and _green(n2) and _green(n1)
            and n2.c > n3.h
            and n1.c > n2.h
            and n1.l > n3.h):
        return BULL

    if (_red(n3) and _red(n2) and _red(n1)
            and n2.c < n3.l
            and n1.c < n2.l
            and n1.h < n3.l):
        return BEAR

    return None
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest momexp_test.py -q
```

Kỳ vọng: `1 passed`.

- [ ] **Step 5: Viết phần test còn lại**

Thêm vào cuối `<SP>/momexp_test.py`. Đây là các mục 2–9 của spec §7.2:

```python
# ------------------------------------------------------------------ BEAR
N3_BEAR = Candle(100.0, 101.0, 97.0, 98.0)
N2_BEAR = Candle(98.0, 99.0, 95.0, 96.0)
N1_BEAR = Candle(96.0, 96.5, 93.0, 94.0)


def test_bear_day_du():
    assert detect(N3_BEAR, N2_BEAR, N1_BEAR) == BEAR


# ------------------------------------- bat doi xung co y: n1 chong lan n2
def test_n1_chong_n2_van_hop_le():
    """Spec section 2.5. Day la ly do dieu kien 4 dung n3 chu khong phai n2."""
    assert N1_BULL.l < N2_BULL.h          # co chong lan that
    assert detect(N3_BULL, N2_BULL, N1_BULL) == BULL


# ------------------------------------------------------------------ doji
def test_doji_o_n3_thi_khong_tinh():
    n3 = Candle(102.0, 103.0, 99.0, 102.0)      # c == o
    assert detect(n3, N2_BULL, N1_BULL) is None


def test_doji_o_n2_thi_khong_tinh():
    n2 = Candle(104.0, 105.0, 101.0, 104.0)     # c == o
    assert detect(N3_BULL, n2, N1_BULL) is None


def test_doji_o_n1_thi_khong_tinh():
    n1 = Candle(106.0, 107.0, 103.5, 106.0)     # c == o
    assert detect(N3_BULL, N2_BULL, n1) is None


# ----------------------------------------------------------------- bien
def test_bien_n2_close_bang_dung_dinh_n3():
    """Luat la `>` chat: dong cua dung bang dinh nen truoc KHONG tinh."""
    n2 = Candle(102.0, 105.0, 101.0, 103.0)     # c == n3.h == 103
    assert detect(N3_BULL, n2, N1_BULL) is None


def test_bien_n1_low_bang_dung_dinh_n3():
    n1 = Candle(104.0, 107.0, 103.0, 106.0)     # l == n3.h == 103
    assert detect(N3_BULL, N2_BULL, n1) is None


def test_bien_n1_close_bang_dung_dinh_n2():
    n1 = Candle(104.0, 107.0, 103.5, 105.0)     # c == n2.h == 105
    assert detect(N3_BULL, N2_BULL, n1) is None


# ---------------------------------------------- bo tung dieu kien mot
def test_bo_dieu_kien_1_mot_nen_khong_xanh():
    n2 = Candle(105.0, 105.0, 101.0, 104.0)     # do: c 104 < o 105
    assert detect(N3_BULL, n2, N1_BULL) is None


def test_bo_dieu_kien_2_n2_dong_duoi_dinh_n3():
    n2 = Candle(100.0, 105.0, 99.0, 102.5)      # xanh, nhung c 102.5 < 103
    assert detect(N3_BULL, n2, N1_BULL) is None


def test_bo_dieu_kien_3_n1_dong_duoi_dinh_n2():
    n1 = Candle(104.0, 107.0, 103.5, 104.5)     # xanh, nhung c 104.5 < 105
    assert detect(N3_BULL, N2_BULL, n1) is None


def test_bo_dieu_kien_4_n1_khong_thoat_range_n3():
    n1 = Candle(104.0, 107.0, 102.0, 106.0)     # xanh, nhung l 102 < 103
    assert detect(N3_BULL, N2_BULL, n1) is None


# -------------------------------------------------------------- di ngang
def test_ba_nen_xanh_nhung_di_ngang():
    n3 = Candle(100.0, 101.0, 99.0, 100.5)
    n2 = Candle(100.5, 101.5, 99.5, 100.8)      # c 100.8 < n3.h 101
    n1 = Candle(100.8, 101.2, 100.0, 101.0)
    assert detect(n3, n2, n1) is None
```

- [ ] **Step 6: Chạy test**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest momexp_test.py -q
```

Kỳ vọng: `14 passed`.

Nếu có test đỏ: tính lại bằng tay từ dữ liệu, xác định **test hay oracle** sai theo spec §2.2/§2.3, rồi sửa bên sai và ghi lý do vào comment ngay tại chỗ. Không bẻ test cho khớp code.

- [ ] **Step 7: Viết test tính chất (fuzz)**

Thêm vào cuối `<SP>/momexp_test.py`:

```python
# --------------------------------------------- tinh chat tren du lieu ngau nhien
def _rand_candle(rng):
    a, b = rng.uniform(90, 110), rng.uniform(90, 110)
    o, c = rng.uniform(min(a, b), max(a, b)), rng.uniform(min(a, b), max(a, b))
    return Candle(o, max(a, b), min(a, b), c)


def test_ket_qua_luon_thuoc_ba_gia_tri():
    rng = random.Random(20260913)
    for _ in range(5000):
        r = detect(_rand_candle(rng), _rand_candle(rng), _rand_candle(rng))
        assert r in (BULL, BEAR, None)


def test_BULL_keo_theo_du_bon_dieu_kien():
    """Neu detect noi BULL thi ca bon dieu kien phai that su dung."""
    rng = random.Random(20260914)
    seen = 0
    for _ in range(20000):
        n3, n2, n1 = (_rand_candle(rng) for _ in range(3))
        if detect(n3, n2, n1) == BULL:
            seen += 1
            assert n3.c > n3.o and n2.c > n2.o and n1.c > n1.o
            assert n2.c > n3.h
            assert n1.c > n2.h
            assert n1.l > n3.h
    assert seen > 0, "fuzz khong sinh duoc ca BULL nao — doi seed"


def test_BEAR_keo_theo_du_bon_dieu_kien():
    rng = random.Random(20260915)
    seen = 0
    for _ in range(20000):
        n3, n2, n1 = (_rand_candle(rng) for _ in range(3))
        if detect(n3, n2, n1) == BEAR:
            seen += 1
            assert n3.c < n3.o and n2.c < n2.o and n1.c < n1.o
            assert n2.c < n3.l
            assert n1.c < n2.l
            assert n1.h < n3.l
    assert seen > 0, "fuzz khong sinh duoc ca BEAR nao — doi seed"
```

**Nếu `seen == 0`:** nến ngẫu nhiên độc lập rất hiếm tạo được pattern này. Thay vì đổi seed vu vơ, dựng dữ liệu có hướng: sinh `n3` ngẫu nhiên rồi đặt `n2`, `n1` dịch lên/xuống một lượng ngẫu nhiên dương đủ lớn. Ghi lại cách sinh trong comment.

- [ ] **Step 8: Chạy test**

Kỳ vọng: `17 passed`.

- [ ] **Step 9: Mutation testing — bảy mutation của spec §7.3**

Mỗi lần: sửa `momexp_oracle.py` → `rm -rf __pycache__` → `python -m pytest momexp_test.py -q` → ghi số test đỏ → hoàn nguyên.

| # | Mutation | Nhắm vào |
|---|---|---|
| 1 | `n2.c > n3.h` → `>=` | ranh giới §2.6 |
| 2 | `n1.c > n2.h` → `>=` | ranh giới §2.6 |
| 3 | `n1.l > n3.h` → `>=` | ranh giới §2.6 |
| 4 | `n1.l > n3.h` → `n1.l > n2.h` | **lệch chỉ số** §2.1 |
| 5 | `n1.c > n2.h` → `n1.c > n3.h` | **lệch chỉ số** §2.1 |
| 6 | Bỏ `_green(n3) and _green(n2) and _green(n1)` | điều kiện 1 |
| 7 | `_green` dùng `>=` thay `>` | doji §2.6 |

**Mutation nào sống sót thì PHẢI thêm test cho tới khi nó chết.** "Sống sót, chấp nhận" không phải kết quả hợp lệ. Ở dự án trước, 3 trên 5 mutation sống sót lần đầu dù kế hoạch chỉ đoán trước một cái — nên đừng ngạc nhiên nếu phải thêm test.

Ghi số test đỏ của từng mutation vào báo cáo.

- [ ] **Step 10: Chạy lại lần cuối**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest momexp_test.py -q
```

Kỳ vọng: ít nhất `17 passed`, nhiều hơn nếu mutation buộc thêm test.

---

## Task 2: File Pine

**Files:**
- Create: `pine/momentum_expansion.pine`

**Interfaces:**
- Consumes: `<SP>/momexp_oracle.py` hàm `detect` làm bản đối chiếu (Task 1).
- Produces: file Pine hoàn chỉnh. Task 3 soát nó.

- [ ] **Step 1: Viết header và khai báo**

Tạo `pine/momentum_expansion.pine`. Mở đầu `//@version=6`, rồi khối comment header nêu:

- pattern là gì, bằng lời (ba nến cùng màu, mỗi nến đóng vượt đỉnh nến trước, nến cuối thoát hẳn range nến đầu)
- **bảng ánh xạ `n1/n2/n3` ↔ `[0]/[1]/[2]`** và câu cảnh báo lệch chỉ số thì sai âm thầm
- bất đối xứng có chủ ý: n1 được phép chồng n2, điều kiện 4 dùng đỉnh **n3**
- doji không tính, so sánh `>` chặt
- **chưa compile** — chỉ qua checker tĩnh và đối chiếu oracle

```pine
indicator("Momentum Expansion", overlay=true)
```

Không truyền `max_lines_count` hay `max_labels_count`: file này không dùng đối tượng `line`/`label`/`box` nào.

- [ ] **Step 2: Viết inputs**

Đúng năm input của spec §6, không thêm không bớt:

```pine
// ---------------------------------------------------------------- inputs
grpDir     = "Chieu"
enableBull = input.bool(true, "Enable BULL", group=grpDir)
enableBear = input.bool(true, "Enable BEAR", group=grpDir)

grpShow    = "Hien thi"
showShapes = input.bool(true, "Mui ten tin hieu", group=grpShow)
showTint   = input.bool(true, "To ba nen cua pattern", group=grpShow)
tintTransp = input.int(85, "Do trong suot khi to", minval=0, maxval=100, group=grpShow)
```

Không có input nào về rủi ro, entry, SL, TP. Không có input chuyển biến thể của điều kiện 4.

- [ ] **Step 3: Viết khối pattern**

```pine
// ---------------------------------------------------------------- pattern
// n1 = nen hien tai, n2 = [1], n3 = [2]. Doi chieu voi momexp_oracle.detect,
// ham do nhan (n3, n2, n1) tuc NGUOC thu tu chi so o day.
bool bull = close > open and close[1] > open[1] and close[2] > open[2]
     and close[1] > high[2]
     and close    > high[1]
     and low      > high[2]

bool bear = close < open and close[1] < open[1] and close[2] < open[2]
     and close[1] < low[2]
     and close    < low[1]
     and high     < low[2]

// barstate.isconfirmed luon dung tren nen lich su, nen no chi chan nen live —
// dung thu can chan. Khong co no thi dau hieu nhap nhay roi bien mat.
bool bullSig = bull and barstate.isconfirmed and enableBull
bool bearSig = bear and barstate.isconfirmed and enableBear
```

Dòng nối tiếp thụt **5 dấu cách**. Thụt 4 hoặc 8 là Pine đọc thành khối mới, không báo lỗi.

- [ ] **Step 4: Viết khối vẽ**

```pine
// ---------------------------------------------------------------- ve
// To ba nen bang bgcolor voi offset am. Pattern chot o n1 nhung can to ca n3
// va n2 nam phia trai, ma Pine khong nhin toi tuong lai duoc — offset day mau
// sang trai dung vi tri. Khong dung box.new: Pine chan cung 500 box va mot
// chart nhieu nam co the chua hang nghin pattern, box se tran va pattern cu
// nhat lang le bien mat. bgcolor khong co tran nao.
color bullTint = color.new(color.teal, tintTransp)
color bearTint = color.new(color.red,  tintTransp)
color tint     = bullSig ? bullTint : bearSig ? bearTint : na

bgcolor(showTint ? tint : na, offset =  0, title="Nen n1")
bgcolor(showTint ? tint : na, offset = -1, title="Nen n2")
bgcolor(showTint ? tint : na, offset = -2, title="Nen n3")

plotshape(showShapes and bullSig, title="BULL", style=shape.triangleup,
     location=location.belowbar, color=color.new(color.teal, 0), size=size.small)
plotshape(showShapes and bearSig, title="BEAR", style=shape.triangledown,
     location=location.abovebar, color=color.new(color.red, 0), size=size.small)
```

**Bất biến:** mọi lệnh vẽ gác bằng `bullSig`/`bearSig`, **không** lệnh nào tính lại điều kiện. Ở dự án `kill_peak` đã mắc lỗi này — phần vẽ dùng một ngưỡng, phần tín hiệu dùng ngưỡng khác, và chart vẽ nhãn mà strategy không đồng ý.

- [ ] **Step 5: Viết alert**

```pine
// ---------------------------------------------------------------- alert
// level = bien cua n3 ma n1 vua thoat khoi; edge = bien gan nhat cua n1.
// Khoang giua hai so do la vung gia pattern bo lai. File nay khong ve vung do
// va khong tuyen bo gi ve no — chi dua hai so vao alert de dung ngoai chart.
if bullSig
    alert('{"symbol":"' + syminfo.ticker + '","tf":"' + timeframe.period + '","direction":"BULL","setup":"MOMEXP"' + ',"level":' + str.tostring(high[2], "#.#####") + ',"edge":' + str.tostring(low, "#.#####") + ',"close":' + str.tostring(close, "#.#####") + '}', alert.freq_once_per_bar_close)
if bearSig
    alert('{"symbol":"' + syminfo.ticker + '","tf":"' + timeframe.period + '","direction":"BEAR","setup":"MOMEXP"' + ',"level":' + str.tostring(low[2], "#.#####") + ',"edge":' + str.tostring(high, "#.#####") + ',"close":' + str.tostring(close, "#.#####") + '}', alert.freq_once_per_bar_close)
```

Chuỗi Pine dùng nháy đơn bọc ngoài để chứa nháy kép bên trong, giống bốn file Pine khác trong repo.

- [ ] **Step 6: Chạy checker tĩnh**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && python "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad/kp_check.py" pine/momentum_expansion.pine
```

Kỳ vọng: `SACH`.

Nếu báo lỗi thụt dòng: kiểm ba dòng nối tiếp của `bool bull`, ba dòng của `bool bear`, và hai dòng của `plotshape` — tất cả phải là 5 dấu cách.

- [ ] **Step 7: Đọc tay — đối chiếu Pine với oracle**

Mở `<SP>/momexp_oracle.py` hàm `detect` cạnh khối pattern của Pine. Điền bảng này và đưa vào báo cáo:

| Điều kiện | Oracle | Pine | Khớp? |
|---|---|---|---|
| 1 xanh n3 | `_green(n3)` | `close[2] > open[2]` | |
| 1 xanh n2 | `_green(n2)` | `close[1] > open[1]` | |
| 1 xanh n1 | `_green(n1)` | `close > open` | |
| 2 | `n2.c > n3.h` | `close[1] > high[2]` | |
| 3 | `n1.c > n2.h` | `close > high[1]` | |
| 4 | `n1.l > n3.h` | `low > high[2]` | |

Và bảng tương ứng cho chiều BEAR (`_red`, `n2.c < n3.l`, `n1.c < n2.l`, `n1.h < n3.l`).

**Nhớ oracle nhận `(n3, n2, n1)` còn Pine đánh `[2],[1],[0]`** — đây chính là chỗ dễ sai và là lý do bước này tồn tại. Chỗ nào không khớp: **DỪNG và báo**, đừng tự chọn bên.

- [ ] **Step 8: Commit**

Tiêu đề: `feat(pine): momentum_expansion - danh dau ba nen tang tien dong luong`.

Thân bài nêu: bốn điều kiện mỗi chiều; bất đối xứng có chủ ý n1 chồng n2 và điều kiện 4 dùng đỉnh n3; `bgcolor` offset âm thay cho `box.new` và lý do (trần 500 box); `barstate.isconfirmed` gác phần nhìn; doji không tính, so sánh `>` chặt; oracle Python với N test xanh và 7 mutation bị giết; và câu **chưa compile**.

---

## Task 3: Soát cuối

Task này do **người khác** làm, không phải người viết Task 2. Lý do: rủi ro chính của dự án là lệch chỉ số, và người vừa viết bản dịch `n1/n2/n3 → [0]/[1]/[2]` là người kém khả năng nhất để phát hiện mình dịch sai.

**Files:**
- Modify: `pine/momentum_expansion.pine` (chỉ nếu tìm ra lỗi)

**Interfaces:**
- Consumes: tất cả.
- Produces: báo cáo kiểm chứng.

- [ ] **Step 1: Chạy lại hai cổng nghiệm thu**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && SP="C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && python "$SP/kp_check.py" pine/momentum_expansion.pine && cd "$SP" && rm -rf __pycache__ && python -m pytest momexp_test.py -q
```

Kỳ vọng: `SACH`, rồi ít nhất `17 passed`.

- [ ] **Step 2: Đi bộ tay ca BULL qua chính nguồn Pine**

Lấy bảng số của spec §2.5:

| | open | high | low | close |
|---|---|---|---|---|
| n3 | 100 | 103 | 99 | 102 |
| n2 | 102 | 105 | 101 | 104 |
| n1 | 104 | 107 | 103,5 | 106 |

Đọc **thẳng từ file Pine**, không từ oracle: thay `close`=106, `close[1]`=104, `close[2]`=102, `open`=104, `open[1]`=102, `open[2]`=100, `high[1]`=105, `high[2]`=103, `low`=103,5. Tính từng hạng tử của `bull` và ghi ra kết quả mỗi hạng tử.

Kỳ vọng: cả sáu hạng tử đúng, `bull` đúng.

Đây là lớp kiểm chứng duy nhất **không** đi qua oracle, nên nó bắt được ca oracle và Pine cùng sai một kiểu.

- [ ] **Step 3: Đi bộ tay ca BEAR**

Y hệt với `N3_BEAR`/`N2_BEAR`/`N1_BEAR` của Task 1 Step 5:

| | open | high | low | close |
|---|---|---|---|---|
| n3 | 100 | 101 | 97 | 98 |
| n2 | 98 | 99 | 95 | 96 |
| n1 | 96 | 96,5 | 93 | 94 |

Kỳ vọng: cả sáu hạng tử của `bear` đúng.

- [ ] **Step 4: Đi bộ một ca ÂM — pattern phải KHÔNG kích hoạt**

Dùng dữ liệu của `test_bien_n1_low_bang_dung_dinh_n3`: n1 = (104, 107, **103**, 106) với n3.high = 103.

Kỳ vọng: `low > high[2]` cho `103 > 103` = **sai**, nên `bull` sai. Nếu bạn tính ra `bull` đúng thì file dùng `>=` ở đâu đó — **DỪNG và báo**.

- [ ] **Step 5: Soát năm điểm**

| # | Soát | Cách |
|---|---|---|
| 1 | Đúng năm input, đúng tên và mặc định của spec §6 | đọc, đối chiếu spec |
| 2 | Không dùng `line`/`label`/`box` nào | `grep -n "line\.\|label\.\|box\." pine/momentum_expansion.pine` phải rỗng |
| 3 | Mọi lệnh vẽ gác bằng `bullSig`/`bearSig`, không tính lại điều kiện | đọc từng lệnh vẽ |
| 4 | Thụt dòng nối tiếp không chia hết cho 4 | đo bằng máy, không ước lượng |
| 5 | Không có chỗ nào viết "đã test"/"works"/"verified" về Pine | `grep -in "da test\|works\|verified\|tested"` |

Điểm 4 — `kp_check.py` **đã** kiểm luật này đúng cách rồi (Step 1), nên đây chỉ
là soát bổ sung để đọc ra con số thật:

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && grep -nE "^ +(and |or |location=|color=)" pine/momentum_expansion.pine | awk -F: '{line=$0; sub(/^[0-9]+:/, "", line); match(line, /^ +/); print $1, RLENGTH, (RLENGTH % 4 == 0 ? "<-- CHIA HET CHO 4" : "ok")}'
```

Kỳ vọng: đúng **tám** dòng (ba `and` của `bull`, ba của `bear`, hai `location=`
của `plotshape`), tất cả thụt **5**, không dòng nào có `<-- CHIA HET CHO 4`.

**Lọc theo `^ +(and |or |location=|color=)` chứ không phải mọi dòng thụt.** Luật
chỉ cấm dòng **nối tiếp**; thân khối `if` thụt 4, 8, 12 là hoàn toàn bình
thường. Lệnh bắt mọi dòng thụt sẽ báo hàng trăm cảnh báo giả — đã thử trên
`rsi_failure_swing_indicator.pine`, nó kêu 137 dòng trên một file vốn sạch.

- [ ] **Step 6: Báo cáo**

Ghi rõ **đã làm gì** và **chưa làm gì**.

Đã làm — `kp_check.py` SACH; N test xanh; 7 mutation đều giết được test; đi bộ tay hai ca dương và một ca âm đọc thẳng từ nguồn Pine; năm điểm soát.

Chưa làm — **chưa compile trên TradingView**; chưa chạy trên dữ liệu thật; chưa biết `bgcolor` có nhận tham số `offset` không (spec §7.5 ghi đây là chỗ ngờ nhất, và nếu TradingView từ chối thì cách sửa là bỏ hai lời gọi `offset=-1`/`offset=-2`, giữ lại mỗi nến n1).

- [ ] **Step 7: Commit**

Nếu Step 1–5 không tìm ra lỗi: commit rỗng (`git commit --allow-empty`) chỉ để ghi báo cáo, tiêu đề `chore(pine): momentum_expansion - soat cuoi, bao cao kiem chung`.

Nếu có sửa: commit kèm sửa.

---

## Tự soát kế hoạch

**1. Phủ spec.** Duyệt từng mục, tìm task tương ứng:

| Spec | Task |
|---|---|
| §2.0 khai báo + không state | 2 Step 1 |
| §2.1 ánh xạ chỉ số | Global Constraints; 2 Step 7; 3 Step 2–4 |
| §2.2 chiều tăng | 2 Step 3; oracle 1 Step 3 |
| §2.3 chiều giảm | 2 Step 3; oracle 1 Step 3 |
| §2.4 bốn điều kiện độc lập | 1 Step 5 (bốn test "bỏ từng điều kiện") |
| §2.5 bất đối xứng n1 chồng n2 | 1 Step 5 `test_n1_chong_n2_van_hop_le`; mutation #4 |
| §2.6 doji + so sánh chặt + ba nến đầu chart | 1 Step 5 (doji, biên); mutation #1–3, #7 |
| §3 không repaint | 2 Step 3 (`barstate.isconfirmed`) |
| §4.1 bgcolor offset | 2 Step 4 |
| §4.2 plotshape | 2 Step 4 |
| §4.3 bất biến vẽ | 2 Step 4; 3 Step 5 điểm 3 |
| §5 alert | 2 Step 5 |
| §6 inputs | 2 Step 2; 3 Step 5 điểm 1 |
| §7.1 checker tĩnh | 2 Step 6; 3 Step 1 |
| §7.2 oracle + 9 nhóm test | 1 Step 1, 5, 7 |
| §7.3 bảy mutation | 1 Step 9 |
| §7.4 đọc tay đối chiếu | 2 Step 7; 3 Step 2–4 |
| §7.5 chưa compile | Global Constraints; 3 Step 6 |
| §8 ngoài phạm vi | không task nào — đúng |

Không mục spec nào thiếu task.

**2. Chỗ kế hoạch tự nhận là chưa chắc.** Ba chỗ đánh dấu "DỪNG và báo" thay vì đoán: bảng đối chiếu Pine↔oracle ở 2 Step 7 nếu có dòng không khớp; ca âm ở 3 Step 4 nếu tính ra `bull` đúng; và mutation nào sống sót ở 1 Step 9 thì phải thêm test chứ không được ghi "chấp nhận". Thêm một chỗ được báo trước: fuzz ở 1 Step 7 có thể không sinh nổi ca BULL/BEAR nào, và kế hoạch đưa sẵn cách sinh có hướng thay vì đổi seed vu vơ.

**3. Nhất quán tên.** `Candle`, `detect(n3, n2, n1)`, `BULL`, `BEAR` (Task 1) dùng lại đúng tên ở Task 2 Step 7 và Task 3 Step 2–4. `bull`/`bear`/`bullSig`/`bearSig`, `enableBull`/`enableBear`/`showShapes`/`showTint`/`tintTransp` (Task 2) dùng nhất quán ở Task 3 Step 5. Hằng số trong dữ liệu test (`N3_BULL` = 100/103/99/102 v.v.) dùng lại nguyên vẹn ở Task 3 Step 2 và 3.

**4. Placeholder.** Quét tìm "TBD", "TODO", "tương tự Task N", "thêm xử lý lỗi phù hợp", bước mô tả việc mà không có code. Một chỗ đã sửa khi soát: Task 2 Step 1 ban đầu chỉ viết "viết header nêu các điểm quan trọng" — đã đổi thành danh sách năm mục cụ thể phải có trong header. Task 3 Step 6 nói "ghi rõ đã làm gì và chưa làm gì" và kèm ngay nội dung của cả hai phần, nên không phải placeholder.
