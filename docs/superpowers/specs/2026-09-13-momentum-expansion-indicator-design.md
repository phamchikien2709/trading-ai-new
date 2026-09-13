# Momentum Expansion (`momentum_expansion`) — Design Spec

**Ngày:** 2026-09-13
**Trạng thái:** chờ duyệt
**Nguồn:** hội thoại brainstorming 2026-09-13
**Phạm vi:** một file mới `pine/momentum_expansion.pine`. **Không** sinh tín hiệu vào lệnh, **không** đặt lệnh, **không** bảng đếm.

Công cụ đánh dấu. Nó chỉ nói "pattern này vừa xảy ra ở đây", không nói gì
về việc nên làm gì với nó.

---

## 1. Mục tiêu

Đánh dấu ba nến liên tiếp cho thấy động lượng đang **tăng tiến**: mỗi nến
đóng cửa vượt qua đỉnh của nến trước, và nến cuối thoát hẳn khỏi range của
nến đầu.

---

## 2. Khai báo và luật pattern

### 2.0 Khai báo

```pine
indicator("Momentum Expansion", overlay=true)
```

Không cần `max_lines_count` hay `max_labels_count`: phần vẽ không dùng đối tượng
`line`/`label`/`box` nào (§4).

**File này không có state.** Không một biến `var` nào, không máy trạng thái,
không thứ tự bắt buộc trong nến. Pattern là một hàm thuần của ba nến gần nhất.
Các spec khác trong repo đều có mục "thứ tự trong một nến" — ở đây nó vắng mặt
vì không có gì để sắp thứ tự, không phải vì bị bỏ sót.

### 2.1 Ánh xạ chỉ số — nguồn lỗi số một của file này

Người dùng đặt tên nến theo thứ tự **lùi về quá khứ**: `n1` mới nhất, `n3`
cũ nhất. Pine đánh chỉ số cũng lùi về quá khứ nhưng bắt đầu từ 0:

| Tên người dùng | Pine | Vai trò |
|---|---|---|
| `n1` | `[0]` (không hậu tố) | nến hiện tại, nến chốt pattern |
| `n2` | `[1]` | nến giữa |
| `n3` | `[2]` | nến cũ nhất |

Lệch một chỉ số ở đây thì pattern **vẫn chạy, vẫn vẽ, và sai âm thầm** — không
có lỗi nào báo ra. Đó là lý do §7.2 tồn tại.

### 2.2 Chiều tăng

```pine
bool bull = close > open and close[1] > open[1] and close[2] > open[2]
     and close[1] > high[2]
     and close    > high[1]
     and low      > high[2]
```

Đọc thành lời:

1. **Ba nến đều xanh** — `close > open` chặt cho cả ba
2. **n2 đóng trên đỉnh n3** — `close[1] > high[2]`
3. **n1 đóng trên đỉnh n2** — `close > high[1]`
4. **n1 thoát hẳn range n3** — `low > high[2]`

### 2.3 Chiều giảm — soi gương hoàn toàn

```pine
bool bear = close < open and close[1] < open[1] and close[2] < open[2]
     and close[1] < low[2]
     and close    < low[1]
     and high     < low[2]
```

### 2.4 Bốn điều kiện độc lập, không rút gọn được

Đã kiểm từng cặp: không điều kiện nào suy ra được từ điều kiện khác.

- Điều kiện 4 **không** kéo theo điều kiện 2: n2 có thể đóng **dưới** đỉnh n3
  rồi n1 nhảy vọt qua cả hai.
- Điều kiện 4 **không** kéo theo điều kiện 3: đỉnh n2 có thể cao hơn hẳn đỉnh
  n3, nên `low > high[2]` vẫn đúng trong khi `close < high[1]`.
- Điều kiện 1 không kéo theo gì cả: nến xanh chỉ nói `close > open`, không nói
  gì về quan hệ với nến khác.

Cả bốn đều phải kiểm.

### 2.5 Bất đối xứng có chủ ý: n1 được phép chồng n2

Điều kiện 4 bắt n1 thoát hoàn toàn khỏi range của **n3** — nến cách hai cây —
nhưng **cho phép n1 chồng lấn n2**. Ví dụ hợp lệ:

| | open | high | low | close |
|---|---|---|---|---|
| n3 | 100 | **103** | 99 | 102 |
| n2 | 102 | 105 | 101 | **104** → > 103 ✓ |
| n1 | 104 | 107 | **103,5** → > 103 ✓ | **106** → > 105 ✓ |

`n1.low = 103,5` vẫn thấp hơn `n2.high = 105`, tức n1 chồng lên n2, và pattern
**vẫn hợp lệ**.

Luật chặt hơn `n1.low > n2.high` (thang ba bậc không chồng nhau chút nào) **cố
ý không làm**: người dùng viết `n3`, và biến thể kia hiếm hơn nhiều. Không thêm
input để chuyển đổi — thêm lúc này là đoán.

### 2.6 Hai quyết định về ca biên

**Doji không tính.** `close == open` không phải xanh cũng không phải đỏ. Luật
là `>` và `<` chặt ở cả ba nến.

**So sánh giá cũng chặt.** `close[1] > high[2]` chứ không phải `>=`. Đóng cửa
đúng bằng đỉnh nến trước **không** tính là vượt qua.

**Ba nến đầu chart.** Với `bar_index < 2`, `close[2]` và `high[2]` là `na`. Mọi
phép so sánh với `na` trong Pine cho `na`, và `na` trong ngữ cảnh boolean là
false — nên pattern tự động không kích hoạt. Không cần guard riêng, nhưng phải
ghi lại để không ai thêm guard thừa về sau.

---

## 3. Không repaint

Điều kiện đọc `close`, `low`, `high` của **nến hiện tại**, nên trên nến đang
chạy nó sẽ bật tắt theo giá rồi có thể biến mất khi nến đóng. Đó đúng là kiểu
repaint mà ba dự án Pine trước trong repo này đều tránh.

Gác bằng `barstate.isconfirmed`:

```pine
bool bullSig = bull and barstate.isconfirmed and enableBull
bool bearSig = bear and barstate.isconfirmed and enableBear
```

Trên nến lịch sử `barstate.isconfirmed` luôn đúng, nên nó chỉ chặn nến live —
đúng thứ cần chặn.

Cả mũi tên **và** `alert()` đều gác bằng cùng một biến `bullSig`/`bearSig` —
tức cả hai đều đã có `barstate.isconfirmed` bên trong, không chỉ phần nhìn.
Đây là chủ ý: mũi tên và alert luôn đồng thuận là tính chất mà công cụ đánh
dấu này cần, nên không tách gác riêng cho từng phần.

Cái giá phải trả: `barstate.isconfirmed` chỉ đúng khi có một lần script chạy
đúng vào tick đóng nến của nến realtime đó. Nếu không có lần chạy nào rơi
đúng lúc đó — feed chậm, hoặc người dùng mở chart giữa chừng một nến đang
chạy — thì nến đó không sinh ra **cả** mũi tên lẫn alert. Tải lại chart sau
đó sẽ vẽ lại mũi tên trên nến lịch sử (vì lúc đó `barstate.isconfirmed` luôn
đúng), nhưng `alert()` thì không bao giờ bắn lại — bản chất alert chỉ bắn
tại thời điểm chạy thực, không phải khi vẽ lại lịch sử. Vì vậy: **thấy mũi
tên trên lịch sử không phải là bằng chứng alert đã bắn** lúc đó.

---

## 4. Vẽ

### 4.1 Tô ba nến bằng `bgcolor` với `offset` âm

Pattern chốt tại n1, nhưng cần tô cả n3 và n2 nằm **phía trái** — mà Pine không
nhìn tới tương lai được, nên tại n3 ta chưa biết pattern sẽ thành.

Giải bằng tham số `offset` của `bgcolor`, đẩy màu sang trái:

```pine
color bullTint = color.new(color.teal, tintTransp)
color bearTint = color.new(color.red,  tintTransp)
color tint = bullSig ? bullTint : bearSig ? bearTint : na

bgcolor(showTint ? tint : na, offset =  0, title="Nen n1")
bgcolor(showTint ? tint : na, offset = -1, title="Nen n2")
bgcolor(showTint ? tint : na, offset = -2, title="Nen n3")
```

**Vì sao không dùng `box.new`:** Pine chặn cứng 500 box. Một chart nhiều năm có
thể chứa hàng nghìn pattern, và box sẽ tràn — những pattern cũ nhất lặng lẽ biến
mất khỏi chart mà không báo gì. `bgcolor` không có trần nào.

### 4.2 Mũi tên

```pine
plotshape(showShapes and bullSig, title="BULL", style=shape.triangleup,
     location=location.belowbar, color=color.new(color.teal, 0), size=size.small)
plotshape(showShapes and bearSig, title="BEAR", style=shape.triangledown,
     location=location.abovebar, color=color.new(color.red, 0), size=size.small)
```

`plotshape` cũng không có trần.

**Toàn bộ phần vẽ của file này không dùng một đối tượng `line`/`label`/`box`
nào**, nên `indicator()` không cần `max_lines_count` hay `max_labels_count`.

### 4.3 Bất biến

Mọi lệnh vẽ gác bằng `bullSig`/`bearSig` — **không** lệnh nào tính lại điều kiện.
Ở dự án `kill_peak` đã mắc lỗi này: phần vẽ dùng một ngưỡng, phần tín hiệu dùng
ngưỡng khác, và chart vẽ nhãn mà strategy không đồng ý.

---

## 5. Alert

Một lời gọi `alert()` cho mỗi chiều, theo đúng hình JSON của bốn file Pine trước
trong repo:

Ví dụ chiều BULL — chiều BEAR cùng hình, chỉ khác `direction` và nguồn của
`level`/`edge` theo bảng dưới:

```
{"symbol":"<ticker>","tf":"<period>","direction":"BULL","setup":"MOMEXP",
 "level":<n3.high>,"edge":<n1.low>,"close":<n1.close>}
```

| Trường | BULL | BEAR | Ý nghĩa |
|---|---|---|---|
| `level` | `high[2]` | `low[2]` | biên của n3 mà n1 vừa thoát khỏi |
| `edge` | `low` | `high` | biên gần nhất của n1 |
| `close` | `close` | `close` | đóng cửa n1 |

Khoảng giữa `level` và `edge` là vùng giá pattern bỏ lại. File này **không** vẽ
vùng đó và không tuyên bố gì về nó — chỉ đưa hai số vào alert để dùng ngoài
chart nếu cần.

Chuỗi Pine dùng nháy đơn để chứa nháy kép bên trong, giống bốn file kia.

---

## 6. Inputs

```
Chieu
  enableBull    bool   true
  enableBear    bool   true

Hien thi
  showShapes    bool   true
  showTint      bool   true
  tintTransp    int    85    minval 0, maxval 100
```

Năm input, hết. Không có input nào về rủi ro, entry, SL, TP — file này không
giao dịch. Không có input chuyển biến thể của điều kiện 4 (§2.5).

---

## 7. Kiểm chứng

Pine không compile được ở máy này. Hai lớp thay thế.

### 7.1 Checker tĩnh

`scratchpad/kp_check.py` trên file mới. Phải in `SACH`.

Bắt: thụt dòng nối tiếp chia hết cho 4 (repo dùng 5, 9, 13 — các dòng `and ...`
ở §2.2 và §2.3 thụt **5**), `ta.*` gọi trong `if`, ngoặc lệch.

### 7.2 Oracle Python — rẻ, và bắt đúng loại lỗi nguy hiểm nhất

`scratchpad/momexp_oracle.py`: một hàm thuần nhận ba nến và trả về
`"BULL"` / `"BEAR"` / `None`.

```python
def detect(n3, n2, n1):
    """n3 cu nhat, n1 moi nhat. Moi nen la (open, high, low, close)."""
```

Thứ tự tham số cố ý viết **theo tên của người dùng** (n3 trước), ngược với thứ
tự chỉ số Pine, để chỗ dịch giữa hai cách đánh số nằm ở **đúng một nơi** và
được test soi thẳng vào.

`scratchpad/momexp_test.py`, test bắt buộc:

1. Ca BULL đầy đủ — dùng đúng bảng số của §2.5
2. Ca BEAR đầy đủ, soi gương
3. **n1 chồng n2 vẫn hợp lệ** (§2.5) — ghim bất đối xứng có chủ ý
4. Một nến doji ở mỗi vị trí trong ba → `None`
5. Biên `close[1] == high[2]` đúng bằng → `None` (luật `>` chặt)
6. Biên `low == high[2]` đúng bằng → `None`
7. Bỏ từng điều kiện một (4 ca) → `None`
8. Ba nến xanh nhưng đi ngang, không thoả điều kiện nào → `None`
9. Không bao giờ trả về cả BULL lẫn BEAR: sinh ngẫu nhiên vài nghìn bộ ba nến,
   khẳng định kết quả luôn thuộc `{BULL, BEAR, None}` và hai chiều loại trừ nhau

### 7.3 Mutation testing — bắt buộc, không được bỏ qua

Với mỗi mutation, sửa oracle → `rm -rf __pycache__` → chạy test → ghi số test
đỏ → hoàn nguyên. **Mutation nào sống sót thì phải thêm test cho tới khi nó
chết**; "sống sót, chấp nhận" không phải kết quả hợp lệ.

| # | Mutation | Nhắm vào |
|---|---|---|
| 1 | `>` → `>=` ở điều kiện 2 | ranh giới §2.6 |
| 2 | `>` → `>=` ở điều kiện 3 | ranh giới §2.6 |
| 3 | `>` → `>=` ở điều kiện 4 | ranh giới §2.6 |
| 4 | Đổi `n3` ↔ `n2` ở điều kiện 4 | **lệch chỉ số** — §2.1 |
| 5 | Đổi `n1` ↔ `n2` ở điều kiện 3 | **lệch chỉ số** — §2.1 |
| 6 | Bỏ điều kiện "ba nến cùng màu" | điều kiện 1 |
| 7 | Doji tính là xanh (`>=` thay `>`) | §2.6 |

Mutation 4 và 5 là lý do chính oracle này tồn tại.

### 7.4 Đọc tay

Đối chiếu từng dòng §2.2/§2.3 của Pine với `detect()` của oracle, dùng bảng ánh
xạ §2.1. Đây là lớp duy nhất kiểm được rằng bản dịch `n1/n2/n3` → `[0]/[1]/[2]`
đúng, vì oracle và Pine đánh số ngược nhau.

### 7.5 Chưa compile

Mọi thứ chỉ qua checker tĩnh, oracle và đọc tay. **Không được viết "đã test"**
về code Pine ở bất cứ đâu.

Chỗ ngờ nhất: tham số `offset` của `bgcolor` (§4.1). Nếu TradingView không nhận,
cách sửa là bỏ hai lời gọi `offset=-1`/`offset=-2` và chỉ tô nến n1 — mất phần
tô ba nến nhưng mũi tên và alert vẫn nguyên.

---

## 8. Ngoài phạm vi

- Bảng đếm / tự chấm điểm. Người dùng đã chọn phạm vi "đánh dấu + alert"; nếu
  muốn đo hiệu quả thì đó là spec riêng, và nó sẽ cần mô hình null chứ không
  phải một bảng tỉ lệ.
- Vẽ vùng giá bỏ lại giữa `level` và `edge` (§5).
- Luật vào lệnh, SL/TP, file strategy.
- Biến thể `n1.low > n2.high` của điều kiện 4 (§2.5).
- Bản Python trong `rsi_fvg/` — file này không nối vào engine.
