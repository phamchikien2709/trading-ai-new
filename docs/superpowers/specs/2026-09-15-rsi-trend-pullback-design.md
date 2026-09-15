# RSI Trend Pullback (`rsi_trend_pullback`) — Design Spec

**Ngày:** 2026-09-15
**Trạng thái:** chờ duyệt
**Nguồn:** hội thoại brainstorming 2026-09-15
**Phạm vi:** hai file mới — `pine/rsi_trend_pullback_indicator.pine` và
`pine/rsi_trend_pullback_strategy.pine`.

Setup **theo xu hướng**, ngược vai với `rsi_failure_swing` (bắt đỉnh đáy). Ở đó
một cú quá bán rồi phân kì là tín hiệu **đảo chiều**; ở đây một cú quá bán là
bằng chứng xu hướng giảm đang mạnh, và cú hồi về 50 là chỗ bán tiếp.

---

## 1. Mục tiêu

RSI thủng 25 đánh dấu một xung giảm thật. Giá hồi lên, RSI về lại 50 — đó là
điểm bán theo xu hướng. Mục tiêu đặt dưới đáy của chính xung đó.

Chiều mua soi gương qua mốc 75.

---

## 2. Khai báo và luật

### 2.0 Khai báo

```pine
indicator("RSI Trend Pullback", overlay=true, max_labels_count=500)
```

`overlay=true` — file nằm ở **pane giá**, không vẽ RSI.

Đây là quyết định có chủ ý và nó khác `rsi_failure_swing`. File kia nằm ở pane
riêng để vẽ RSI, rồi dùng `force_overlay=true` (14 chỗ) đẩy đường và nhãn sang
pane giá. `force_overlay` có từ Pine v5.5 nhưng **chưa bao giờ compile được ở
máy viết ra nó**, và đó là rủi ro mở duy nhất còn lại của file kia. Không có lý
do gì để cược file mới vào cùng một thứ chưa kiểm chứng. Muốn nhìn RSI thì bật
indicator RSI dựng sẵn của TradingView; bảng trạng thái (§6) vẫn in RSI hiện
tại nên soi tay được.

`max_lines_count` **không cần**: phần vẽ không dùng một đối tượng `line` nào
(§4). `max_labels_count=500` cần, vì nhãn là thứ duy nhất bị đếm.

### 2.1 Ba mốc và một chiều đọc

| mốc | input | vai trò |
|---|---|---|
| 25 | `loLevel` | thủng xuống → mở pha BÁN |
| 75 | `hiLevel` | vượt lên → mở pha MUA |
| 50 | `midLevel` | mốc xác nhận cho **cả hai** chiều |

### 2.2 So mức, không bắt cắt

Luật dùng **so mức** (`rsi > midLevel`) chứ không dùng bắt cắt
(`rsi[1] <= midLevel and rsi > midLevel`). Hai lý do:

1. **Nó đúng chữ của đề bài.** Người dùng viết "sell tại cây nến có rsi > 50",
   không viết "cây nến cắt lên 50".
2. **Nó không vỡ khi lỡ một nến.** Tín hiệu bị gác bằng `barstate.isconfirmed`
   (§3). Nếu dùng bắt cắt và không có lần script chạy nào rơi đúng tick đóng
   nến, thì sang nến sau `rsi[1] <= 50` đã sai và setup **kẹt ở SEEKING vĩnh
   viễn**, chỉ thoát khi RSI tụt lại dưới 50 rồi lên lần nữa — tức một lệnh
   khác hẳn. Với so mức, nó chỉ bắn muộn một nến.

So mức không sinh tín hiệu thừa: trạng thái `SEEKING` chỉ tồn tại sau khi đã
thấy RSI < 25, nên nến xác nhận đầu tiên có RSI > 50 **chính là** cú vượt mốc.

### 2.3 Máy trạng thái — chiều BÁN

Hai trạng thái, không ba.

| từ | sự kiện | sang | làm gì |
|---|---|---|---|
| IDLE (0) | `rsi < loLevel` | SEEKING (1) | ghi `sXBar`, đặt `sLow = low` |
| SEEKING | mỗi nến | SEEKING | `sLow = min(sLow, low)` |
| SEEKING | `rsi > midLevel`, nến đã đóng | **TÍN HIỆU BÁN** → IDLE | tính entry/SL/TP/rr |

**Không có điều kiện huỷ, không có hạn nến.** Đây là lựa chọn có chủ ý của
người dùng: đo phân phối thời gian chờ thật trước, rồi mới quyết có cần hạn hay
không. Hệ quả phải đọc kèm nằm ở §11 mục 2.

### 2.4 Máy trạng thái — chiều MUA (gương hoàn toàn)

| từ | sự kiện | sang | làm gì |
|---|---|---|---|
| IDLE | `rsi > hiLevel` | SEEKING | ghi `bXBar`, đặt `bHigh = high` |
| SEEKING | mỗi nến | SEEKING | `bHigh = max(bHigh, high)` |
| SEEKING | `rsi < midLevel`, nến đã đóng | **TÍN HIỆU MUA** → IDLE | |

### 2.5 Thứ tự trong một nến — chỗ chịu lực

Ba bước, đúng thứ tự này, cho mỗi chiều:

```
1. nới cực trị đang chạy   (chỉ khi SEEKING)
2. kiểm tín hiệu           (chỉ khi SEEKING)
3. mở pha mới              (chỉ khi IDLE)
```

**Bước 1 phải đứng trước bước 2.** Đề bài nói đáy được lấy "từ lúc cross dưới
25 **cho tới nến entry**", nên `low` của chính nến vào lệnh phải được tính vào
`sLow`. Đảo hai bước này thì TP lệch đi một nến — pattern vẫn chạy, vẫn vẽ, và
sai âm thầm.

Trên chính nến mở pha, bước 1 **không** chạy (lúc đó còn IDLE) — `sLow` được
khởi tạo bằng `low` của nến đó ở bước 3. Từ nến sau trở đi bước 1 mới nới nó.
Không có nến nào bị bỏ sót và cũng không có nến nào bị tính hai lần.

**Bước 2 phải đứng trước bước 3.** Nếu tín hiệu vừa bắn và đưa trạng thái về
IDLE, bước 3 chạy ngay sau đó trên cùng nến sẽ thấy `rsi > 50` nên không mở pha
bán mới. Đúng. Chiều ngược lại cũng vậy: RSI rơi 60 → 20 trong một nến thì bước
2 không làm gì (đang IDLE) còn bước 3 mở pha bán.

**Hai chiều không bao giờ cùng SEEKING.** Pha bán sống khi RSI chưa vượt 50;
pha mua sống khi RSI chưa thủng 50. Nếu RSI nhảy 24 → 80 trong một nến thì khối
BÁN chạy trước (bắn tín hiệu, về IDLE), rồi khối MUA mở pha — cùng một nến,
theo thứ tự, không giẫm nhau.

### 2.6 Giá

Chiều BÁN:

```
entry = close của nến xác nhận
SL    = entry + slAtrMult × ATR(14)        (mặc định slAtrMult = 3.0)
TP    = sLow  − tpAtrMult × ATR(14)        (mặc định tpAtrMult = 1.0)
rr    = (entry − TP) / (SL − entry)
wait  = bar_index − sXBar
```

Chiều MUA:

```
entry = close
SL    = entry − slAtrMult × ATR
TP    = bHigh + tpAtrMult × ATR
rr    = (TP − entry) / (entry − SL)
```

**Không có ca suy biến về giá.** `sLow ≤ low của nến entry ≤ close = entry`,
nên TP luôn dưới entry và SL luôn trên entry, với mọi `slAtrMult > 0` và
`tpAtrMult ≥ 0`. Không cần guard `e − s > 0` như `rsi_failure_swing`.

Hai thứ **vẫn phải chặn**:

- RSI/ATR còn `na` ở ~14 nến đầu chart.
- **Mẫu số của `rr` bằng 0.** `SL − entry = slAtrMult × ATR`, nên nó bằng 0 khi
  `slAtrMult = 0` (chặn bằng `minval` ở input, §7) hoặc khi `ATR = 0` — xảy ra
  thật trên chuỗi tổng hợp phẳng, tức trong chính test của oracle. Khi mẫu số
  bằng 0 thì `rr = na` và **tín hiệu không bắn**: không đo được rủi ro thì
  không đánh dấu, cùng tinh thần với mặc-định-chặn ở cổng của nghiên cứu H4.

### 2.7 Setup bị tiêu thụ kể cả khi chiều đó bị tắt

`sSt := 0` nằm **ngoài** mọi `if` con của bước 2. Nếu `enableSell` tắt, hoặc
nếu sau này ai đó thêm bộ lọc chặn tín hiệu, setup vẫn bị tiêu thụ và phải đợi
một cú thủng 25 mới. Tắt một chiều không làm chiều đó tích trạng thái rồi bắn
dồn khi bật lại. Giống hệt `rsi_failure_swing` §bước 3.

---

## 3. Không repaint

Tín hiệu gác bằng `barstate.isconfirmed`.

Ở setup này việc gác là **miễn phí về ngữ nghĩa**: entry đã định nghĩa là giá
đóng cửa, nên đánh giá trước lúc nến đóng là vô nghĩa — bạn sẽ vào ở một giá
không phải giá entry. Máy trạng thái vẫn chạy live (cực trị vẫn nới, bảng vẫn
cập nhật); chỉ khoảnh khắc bắn tín hiệu là đợi nến đóng.

Trên nến lịch sử `barstate.isconfirmed` luôn đúng, nên backtest không đổi một
bit so với bản không gác.

**Cái giá, phải nói rõ:** `barstate.isconfirmed` chỉ đúng khi có một lần script
chạy rơi đúng tick đóng nến. Nếu không — feed chậm, hoặc người dùng mở chart
giữa chừng một nến đang chạy — thì nến đó không sinh **cả** mũi tên lẫn alert.
Nhờ luật so mức (§2.2), tín hiệu sẽ bắn ở nến kế tiếp nếu RSI còn trên 50, chứ
không mất hẳn; nhưng entry khi đó là giá đóng của nến sau. Tải lại chart sẽ vẽ
lại mũi tên trên nến lịch sử, còn `alert()` thì **không bao giờ bắn lại**.
Vì vậy: **thấy mũi tên trên lịch sử không phải bằng chứng alert đã bắn.**

---

## 4. Vẽ

### 4.1 Không dùng một đối tượng `line` nào

| vẽ gì | bằng gì | trần |
|---|---|---|
| cực trị đang theo dõi (`sLow` / `bHigh`) | `plot(..., style=plot.style_linebr)` | không có |
| SL và TP, giữ `holdBars` nến sau tín hiệu | `plot(..., style=plot.style_linebr)` | không có |
| mũi tên tín hiệu | `plotshape` | không có |
| tô nền lúc SEEKING | `bgcolor` | không có |
| nhãn chi tiết | `label.new` | **500** |

`line.new` bị chặn cứng 500 đối tượng, và khi tràn thì **những cái cũ nhất lặng
lẽ biến mất khỏi chart mà không báo gì** — `kill_peak` đã mắc đúng lỗi này. Một
chart nhiều năm trên M5 có thể chứa hàng trăm setup, mỗi setup hai đường SL/TP
là đã 250 setup chạm trần. `plot` với `style_linebr` không có trần nào và ngắt
đúng chỗ giá trị là `na`, nên nó vẽ đoạn chứ không kéo dài vô hạn.

Chỉ nhãn là bị đếm, và nhãn có input tắt (`showLabels`).

### 4.2 Giữ SL/TP bao lâu

```pine
var float slPlot   = na
var float tpPlot   = na
var int   plotTill = na

if sSig or bSig
    slPlot   := sSig ? sSl : bSl
    tpPlot   := sSig ? sTp : bTp
    plotTill := bar_index + holdBars
if not na(plotTill) and bar_index > plotTill
    slPlot   := na
    tpPlot   := na
    plotTill := na
```

`holdBars` mặc định 20. Đây là công cụ **đánh dấu**, không quản lý lệnh — hai
đường này để soi tay hình dạng lệnh, không để theo dõi lệnh đang chạy.

### 4.3 Bất biến

Mọi lệnh vẽ gác bằng `sSig`/`bSig` hoặc bằng trạng thái — **không** lệnh nào
tính lại điều kiện. Ở `kill_peak` đã mắc lỗi này: phần vẽ dùng một ngưỡng, phần
tín hiệu dùng ngưỡng khác, và chart vẽ nhãn mà strategy không đồng ý.

---

## 5. Alert

Một lời gọi `alert()` cho mỗi chiều, cùng hình JSON với bốn file Pine trước
trong repo, cộng hai trường mới `rr` và `wait`:

```
{"symbol":"<ticker>","tf":"<period>","direction":"SELL","setup":"RSITP",
 "entry":<close>,"sl":<entry+3ATR>,"tp":<sLow-1ATR>,"rr":<rr>,"wait":<bars>}
```

`alert.freq_once_per_bar_close`.

**Định dạng số là `"0.#####"`, không phải `"#.#####"`.** Cái sau là
`DecimalFormat` của Java và nó **rụng số 0 đứng đầu**, nên trên instrument dưới
1.0 nó sinh `"sl":.98432` — JSON hỏng. 9 file Pine cũ trong repo vẫn mang lỗi
này (20 dòng); file mới không mang thêm.

`rr` và `wait` vào alert vì đó chính là hai con số cần để quyết định có thêm bộ
lọc hay không (§11 mục 1 và 2) — có chúng trong alert thì thu được dữ liệu thật
mà không phải chạy lại chart.

---

## 6. Bảng trạng thái

Góc trên bên phải, chỉ vẽ ở `barstate.islast`:

| dòng | nội dung |
|---|---|
| RSI(14) / ATR(14) | giá trị hiện tại |
| BÁN | trạng thái, `sLow`, số nến chờ |
| MUA | trạng thái, `bHigh`, số nến chờ |
| tín hiệu gần nhất | chiều, entry, rr |

Số nến chờ có mặt ở đây **và** trong nhãn **và** trong alert — ba chỗ, vì nó là
biến gây nhiễu chính khi đọc phân phối `rr` (§11 mục 2).

---

## 7. Input

| nhóm | input | mặc định |
|---|---|---|
| RSI | `rsiLen` | 14 |
| | `loLevel` / `midLevel` / `hiLevel` | 25 / 50 / 75 |
| Rủi ro | `atrLen` | 14 |
| | `slAtrMult` (`minval=0.1`) | 3.0 |
| | `tpAtrMult` (`minval=0`) | 1.0 |
| Chiều | `enableSell` / `enableBuy` | bật / bật |
| Hiển thị | `showTint`, `showLevel`, `showSig`, `showLabels`, `showTable` | bật |
| | `holdBars` | 20 |

Bản strategy thêm `riskPct` (mặc định 1.0).

**Không có input `minRR`, không có input hết hạn.** Xem §10.

---

## 8. Kiểm chứng

**KHÔNG COMPILE ĐƯỢC PINE Ở MÁY NÀY.** Không báo cáo nào được nói "đã test",
"đã chạy", "verified", "works" về code Pine. Chỉ được nói "qua checker tĩnh",
"đối chiếu với oracle", "đọc tay".

1. **Oracle Python** dựng lại máy trạng thái hai chiều và số học `rr`, **commit
   vào `tests/pine_oracles/`** — không để trong scratchpad. Ở dự án
   `momentum_expansion` oracle từng chỉ sống trong thư mục tạm của phiên trong
   khi header file Pine trỏ vào nó; bằng chứng phải nằm trong version control.
2. **Mutation testing** trên oracle. Đột biến bắt buộc phải giết: đảo thứ tự
   bước 1 và bước 2 (TP lệch một nến); đổi `sLow` thành low của riêng nến
   entry; đổi `>` thành `>=` ở mốc 50; bỏ `sSt := 0`; đổi dấu ATR ở SL hoặc TP.
   Con nào sống sót là thiếu test, không phải "chấp nhận được".
3. **`blockdiff.py`** canh khối tín hiệu chép giữa indicator và strategy.
4. **Checker tĩnh** cho thụt dòng nối tiếp: thụt **phải không chia hết cho 4**
   (repo dùng 5, 9, 13). Thụt 4 hoặc 8 bị Pine đọc thành khối mới — không báo
   lỗi, chỉ đổi hành vi.
5. **Không gọi `ta.*` bên trong `if`.** `ta.rsi` và `ta.atr` giữ state nội bộ;
   gọi trong nhánh điều kiện là sai âm thầm. Cả hai khai ở top level.

---

## 9. Hai file và khối chép

Pine không có module system, nên bản strategy **chép nguyên văn** khối từ
`// ---------- series` tới `// ---- HET KHOI TRANG THAI ----`, và
`blockdiff.py` canh để hai bản không trôi khỏi nhau. Đúng kiến trúc đã dùng cho
cặp `rsi_failure_swing` và cặp `kill_peak_fs`.

Phần **chỉ có ở bản strategy**, nằm ngoài khối chép:

```pine
if sSig and strategy.position_size == 0
    float slDist = sSl - sEntry
    if slDist > 0
        float riskUsd = strategy.equity * riskPct / 100.0
        float qty     = riskUsd / (slDist * syminfo.pointvalue)
        strategy.entry("S", strategy.short, qty=qty, comment="SELL rsi tp")
        strategy.exit("SX", from_entry="S", stop=sSl, limit=sTp)
```

Bộ lọc vị thế nằm **ngoài** mọi khối của phần chép — đó là lý do khối chép giữ
được tính giống hệt từng byte.

**`strategy()` phải khai `max_labels_count=500` tường minh**, vì nó mặc định
**50** chứ không phải 500 như `indicator()`. Bỏ sót thì nhãn cũ lặng lẽ biến
mất trên chart backtest.

---

## 10. Những gì cố ý KHÔNG làm

- **Không lọc `minRR`.** Đề xuất đã nêu và người dùng chọn đo trước. `rr` được
  in lên nhãn và đưa vào alert để thu phân phối thật; thêm ngưỡng lúc này là
  đoán.
- **Không có hạn chờ.** Cùng lý do.
- **Không vẽ RSI, không dùng `force_overlay`.** §2.0.
- **Không lọc khung lớn hơn, không lọc phiên, không lọc trend bằng EMA.** Setup
  tự nhận mình là theo xu hướng qua chính cú thủng 25; thêm bộ lọc thứ hai lúc
  chưa đo là thêm bậc tự do.
- **Không quản lý lệnh** (dời SL, chốt một phần, trailing). Bản indicator là
  công cụ đánh dấu; bản strategy vào một lệnh với SL/TP cố định.

---

## 11. Rủi ro và hạn chế đã biết

1. **R:R là hàm của độ sâu cú hồi, và nó nghịch với trực giác.** SL cố định
   `3×ATR`; TP cách entry `(entry − sLow) + 1×ATR`. Muốn `rr ≥ 1` thì cần
   `entry − sLow ≥ 2×ATR`. Nghĩa là hồi **càng nông** → entry càng gần đáy →
   TP càng gần → `rr` càng tệ. Mà hồi nông lại chính là thứ dân theo xu hướng
   thích, vì nó cho thấy lực bán còn mạnh. Setup đang **thưởng cho cú hồi sâu
   và phạt cú hồi nông** — ngược với ý đồ của chính nó. Ví dụ: hồi 2,5 ATR cho
   `rr ≈ 1,17`; hồi 1 ATR cho `rr ≈ 0,67`. Chưa đo trên dữ liệu thật, nhưng
   cấu trúc thì chắc chắn. Đây là thứ đầu tiên phải nhìn khi có kết quả
   backtest.

2. **Không hết hạn nghĩa là `rr` không có chặn trên.** `sLow` tiếp tục hạ nếu
   giá còn rơi, nên một setup chờ 500 nến sẽ cho `rr` rất đẹp trên giấy mà
   không ai vào được. **Khi đọc kết quả, đừng nhìn phân phối `rr` một mình —
   nhìn nó cùng với số nến chờ.** Đó là lý do `wait` có mặt ở cả bảng, nhãn và
   alert.

3. **SL `3×ATR` không biết gì về cấu trúc.** Nó có thể rơi vào giữa vùng nhiễu,
   hoặc nằm xa hơn đỉnh của cú hồi rất nhiều. Phương án treo SL ở đỉnh cú hồi
   cộng một đệm ATR đã được nêu và **không** chọn, để giữ đúng đề bài. Nếu
   backtest cho thấy `rr` quá thấp một cách hệ thống thì đây là chỗ sửa đầu
   tiên, trước khi thêm `minRR`.

4. **Chưa từng compile trên TradingView.** Không riêng file này — cả năm file
   Pine trong repo đều chưa. Rủi ro compile ở đây thấp hơn `rsi_failure_swing`
   vì không dùng `force_overlay`, nhưng "thấp hơn" không phải "đã kiểm".

5. **Nguồn dữ liệu backtest.** Bản strategy chạy trên TradingView với dữ liệu
   của broker mà chart đang dùng; con số sẽ không khớp tuyệt đối với bất kỳ
   backtest Python nào chạy trên XAUUSDc của Exness.
