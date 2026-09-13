# Quarterly Theory — trạng thái Q2 (`quarterly_theory_ict`) — Design Spec

**Ngày:** 2026-09-13
**Trạng thái:** chờ duyệt
**Nguồn:** hội thoại brainstorming 2026-09-13
**Phạm vi:** một file mới `pine/quarterly_theory_ict.pine`. **Không** sửa Python, **không** sửa engine, **không** sinh tín hiệu, **không** đặt lệnh.

Công cụ **hiển thị và tự chấm điểm**. Nó không tuyên bố gì về lợi nhuận và
không phải bằng chứng thống kê — xem §11.1.

---

## 1. Mục tiêu

Phân loại mỗi chu kỳ Quarterly Theory theo **vị trí đóng cửa của Q2 so với
range Q1**, vẽ nó lên chart, và tự đếm xem Q3/Q4 sau đó có đi đúng bias không.

Năm trạng thái, do người dùng đề xuất và khoá **trước khi** nhìn thấy bất kỳ
con số nào của hai trạng thái mới:

| # | Điều kiện tại đóng Q2 | Bias cho Q3/Q4 | Đã đo chưa |
|---|---|---|---|
| 1 | `q2Close > q1High` | BULL | **chưa bao giờ** |
| 2 | `q2Close < q1Low` | BEAR | **chưa bao giờ** |
| 3 | trong range, `q2High > q1High` và **không** `q2Low < q1Low` | BEAR | rồi — percentile 3,0 |
| 4 | trong range, `q2Low < q1Low` và **không** `q2High > q1High` | BULL | rồi — percentile 3,0 |
| 5 | trong range, không phá bên nào **hoặc** phá cả hai | NEUTRAL | — |

**Vị trí close quyết định trước.** Nếu Q2 quét thủng `q1Low` rồi bật lên đóng
cửa trên `q1High`, đó là trạng thái **1 (BULL)**, không phải 5. Nhánh "phá cái
gì" chỉ áp cho close nằm **trong** range. Năm trạng thái vì vậy là một phân
hoạch đầy đủ và rời nhau: mỗi chu kỳ hợp lệ rơi vào đúng một ô.

Ngoài phạm vi: luật vào/ra, SL/TP, backtest P&L, mô hình null, và bất kỳ khuyến
nghị giao dịch nào.

---

## 2. Quan hệ với hai nghiên cứu đã đóng

Trạng thái 3 và 4 **chính là** phép đo ⑥ của
`2026-09-09-quarterly-theory-premise-study-design.md`, và là trigger chung của
cả năm biến thể trong `2026-09-09-quarterly-theory-variants-study-design.md`.
Cả hai nghiên cứu kết luận **trượt**:

| Tầng | ⑥ pooled thật | Null mean | Percentile |
|---|---|---|---|
| session | 0,4730 | 0,5077 | **3,0** |
| q90 | 0,4847 | 0,4985 | **2,9** |

Luật "phá cả hai biên → loại" mà người dùng đề xuất **không phải cải tiến**:
spec biến thể §2 đã ghi `both = swept_up AND swept_dn -> LOẠI khỏi mọi biến
thể`, và Phase 1b vẫn trượt sau khi loại chúng.

**Trạng thái 1 và 2 thì chưa từng nằm trong phép đo nào.** Trigger của cả Phase
1 lẫn năm biến thể đều đòi `q2_close` quay **lại trong** range, nên toàn bộ
nhánh "phá ra và giữ được" là phần bù chưa ai chạm tới. Đó là một tiền đề
**khác**, không phải biến thể thứ sáu: sweep-reclaim nói về *thất bại*, còn
trạng thái 1/2 nói về *thành công*.

**File này không vi phạm luật chặn nào.** §7 của Phase 1 chặn việc viết spec
*strategy*; §6 của Phase 1b đóng họ sweep-reclaim. Một công cụ hiển thị không
đặt lệnh và không tuyên bố gì. Hai hàng 3/4 trong bảng điểm được in **xám và có
dấu**, để không ai đọc chúng như một kết quả mới.

---

## 3. Lưới thời gian — mirror `rsi_fvg/quarters.py`

Đây là phần dễ sai nhất của cả file, và là lý do §13 tồn tại.

### 3.1 Bản gốc

`rsi_fvg/quarters.py:label_quarters` là bản gốc. Docstring của nó trỏ tới
`pine/quarterly_theory_ict.pine` — file này. Tham chiếu đó hiện **treo**; spec
này biến nó thành thật.

```python
ny      = epoch UTC -> America/New_York
hour    = ny.hour                      # giờ treo tường NY
h_shift = (hour + 6) % 24              # dịch 18:00 NY về 0
i_sess  = h_shift // 6                 # Q1..Q4 của tầng session
sec_in_sess = (h_shift % 6)*3600 + minute*60 + second
i_q90   = sec_in_sess // 5400          # Q1..Q4 của tầng q90
trading_day = ngày lịch NY, lùi 1 ngày nếu hour < 18
```

### 3.2 Bản Pine

```pine
int hNy    = hour(time, "America/New_York")
int hShift = (hNy + 6) % 24
int iSess  = int(math.floor(hShift / 6.0))
int secIn  = (hShift % 6) * 3600 + minute(time, "America/New_York") * 60
     + second(time, "America/New_York")
int iQ90   = int(math.floor(secIn / 5400.0))
int qIdx   = tier == "session" ? iSess : iQ90
```

**Chia cho `6.0` và `5400.0` rồi `math.floor` rồi `int()`** — cố ý không dựa vào
việc Pine có cắt cụt phép chia int/int hay không. Giả định đúng loại đó đã gây
lỗi ở `kill_peak` Task 4 và phải sửa trên ba file. `math.floor` trả float, và
Pine không tự thu hẹp float→int, nên `int()` là bắt buộc chứ không phải trang trí.

`hour(time, tz)` của Pine tự xử lý DST của New York. Vì `time` của Pine là
instant UTC, phép convert này tương đương `server_to_ny` bên Python: không có
giờ lặp hay giờ mất nào phải xử lý.

**Không dùng `request.security`, không MTF.** Lưới tính thẳng từ `time` của bar
hiện tại; range Q1 là running max/min trong lúc `qIdx == 0`.

### 3.3 Biên quarter và biên chu kỳ

- Quarter mới: `qIdx != qIdx[1]`
- Chu kỳ mới: `qIdx == 0 and qIdx[1] != 0`

Không cần tính `trading_day` hay `cycle_id` trong Pine: chúng tồn tại bên Python
để gom nhóm vector hoá. Pine chạy tuần tự nên chỉ cần biết "đã sang chu kỳ mới
chưa". §13 kiểm rằng hai cách cho cùng một phân hoạch.

### 3.4 Khung chart tối thiểu

Một quarter session dài 6 giờ, một quarter q90 dài 90 phút. Nếu khung chart lớn
hơn hoặc bằng độ dài quarter thì lưới vô nghĩa. Guard:

```pine
if barstate.isfirst and timeframe.in_seconds() >= (tier == "session" ? 21600 : 5400)
    runtime.error("Khung chart phai nho hon mot quarter")
```

---

## 4. State per chu kỳ

```
q1High, q1Low                      cực trị Q1
q2High, q2Low, q2Close             cực trị Q2 + đóng cửa Q2
q3Open, q3Close                    mốc đo Q3
q4Open, q4Close                    mốc đo Q4
n1, n2, n3, n4                     số bar từng quarter
state                              0 chưa có, 1..5 theo §1
biasDir                            +1 BULL, -1 BEAR, 0 NEUTRAL
```

### 4.1 Thứ tự trong một nến — bắt buộc

```
1. tính qIdx
2. neu chu ky moi  -> chot diem chu ky truoc (§5), reset toan bo state
3. neu quarter moi -> chuyen giai doan (§4.2)
4. noi cuc tri cua quarter dang chay
5. ve + bang
```

Bước 2 **phải** trước bước 3: chu kỳ mới cũng là quarter mới, và điểm của chu kỳ
cũ phải được chốt bằng dữ liệu cũ trước khi state bị xoá.

### 4.2 Chuyển giai đoạn

| Vào quarter | Làm gì |
|---|---|
| Q2 (`qIdx` 0→1) | đóng băng `q1High`/`q1Low` |
| Q3 (`qIdx` 1→2) | `q2Close := close[1]`; **phân loại §1**; `q3Open := open` |
| Q4 (`qIdx` 2→3) | `q3Close := close[1]`; `q4Open := open` |
| chu kỳ mới | `q4Close := close[1]`; **chấm điểm §5** |

**Vì sao đọc `close[1]`:** Pine không biết một nến là nến cuối của quarter cho
tới khi nến sau xuất hiện. Nên trạng thái được chốt tại nến **đầu Q3**, đọc giá
đóng cửa của nến cuối Q2. Đây cũng chính là thứ làm indicator không repaint
(§9).

---

## 5. Chấm điểm

Ba cột, mọi cột dùng **dấu của (close cuối − open đầu)**:

| Cột | Công thức | Vai trò |
|---|---|---|
| **Q3→Q4** | `sign(q4Close − q3Open)` | **cột chính** |
| Q3 | `sign(q3Close − q3Open)` | phụ |
| Q4 | `sign(q4Close − q4Open)` | phụ |

Một cột tính là **đúng** khi dấu khớp `biasDir`. Hoà (`== 0`) **bị loại khỏi
mẫu của cột đó**, không gán về phía nào — cùng luật với nghiên cứu cũ. Với vàng
ba chữ số thập phân, hoà hiếm nhưng có.

Trạng thái NEUTRAL có `biasDir == 0` nên không có "đúng". Với nó, **mỗi cột hiển
thị tỉ lệ tăng của chính cột đó** — cột Q3→Q4 là `q4Close > q3Open`, cột Q3 là
`q3Close > q3Open`, cột Q4 là `q4Close > q4Open`. Đó là **mốc sanity**: nếu ô
NEUTRAL lệch xa 50% thì hoặc lưới sai, hoặc bản thân symbol có drift, và mọi ô
khác phải đọc lại dưới ánh sáng đó.

Cột chính gộp Q3+Q4 trùng đúng thống kê mà một nghiên cứu về sau sẽ dùng (V4 của
spec biến thể đã thử chính chân trời này), nên số trên bảng so sánh được.

---

## 6. Loại chu kỳ thiếu bar

Loại cả chu kỳ khỏi bảng điểm nếu **bất kỳ** quarter nào có `< minBars` bar
(mặc định 3). Y nguyên luật của nghiên cứu cũ (Phase 1 §4.2).

**Kiểm tại lúc chấm điểm**, không phải lúc phân loại: `n1..n4` chỉ đủ thông tin
khi chu kỳ đã chạy hết. Điều này cũng xử luôn ca Q4 **không có bar nào** (ngày
lễ) — khi đó `n4 == 0`, `q4Open`/`q4Close` còn `na`, và chu kỳ bị loại trước khi
có phép so sánh nào chạm vào `na`. Nhãn trạng thái ở §4.2 vẫn được vẽ bình
thường, vì nó không phụ thuộc Q3/Q4.

Cần có, không phải tuỳ chọn: khe nghỉ bảo trì hằng ngày của XAUUSDc kết thúc
**đúng 18:00 NY** — trùng khít biên Q1. `quarters.py` ghi rõ confound này đã
được xác nhận bằng dữ liệu thật. Chu kỳ bị loại vẫn vẽ nhưng tô mờ, để nhìn thấy
chúng ở đâu.

---

## 7. Vẽ

`indicator(overlay=true, max_labels_count=500)`.

| Đối tượng | Cách vẽ | Vì sao |
|---|---|---|
| `q1High`, `q1Low` | **`plot()`**, chỉ hiện khi `qIdx >= 1` của chu kỳ đó | `plot` không bị chặn 500 |
| Tô nền **Q3+Q4** theo bias | `bgcolor` | không tốn đối tượng vẽ |
| Tô nền **Q1+Q2** xen kẽ nhạt | `bgcolor` | không tốn đối tượng vẽ |
| Nhãn trạng thái | `label.new` tại nến đầu Q3 | bị chặn 500 → §7.1 |

**Hai lớp nền không bao giờ chồng nhau.** `showQuarters` chỉ tô Q1 và Q2;
`showBias` chỉ tô Q3 và Q4. Nếu để cả hai cùng áp lên Q3/Q4 thì Pine trộn màu và
sắc bias — thứ duy nhất đáng nhìn — bị pha loãng. Phân vai này còn nói đúng câu
chuyện: Q1/Q2 là lúc setup đang hình thành, Q3/Q4 là lúc bias có hiệu lực.

### 7.1 Vì sao `plot` chứ không `line.new`

Pine chặn cứng 500 line. Dữ liệu XAUUSDc M5 có **2.409 chu kỳ** ở tầng session
và **9.537** ở tầng q90. Vẽ mức bằng `line.new` là tràn ngay.

Hệ quả tốt và cố ý: **bảng điểm đếm trên toàn bộ lịch sử chart**, trong khi chỉ
`labelCycles` chu kỳ gần nhất có nhãn. Bộ đếm là biến `var int`, không phải đối
tượng vẽ, nên nó không dính trần nào.

### 7.2 Màu

BULL teal, BEAR đỏ, NEUTRAL xám. Chu kỳ bị loại theo §6: xám nhạt hơn, nhãn có
tiền tố `LOAI:`.

---

## 8. Bảng điểm

`table.new(position.top_right, 5, 7)` — một hàng tiêu đề, năm hàng trạng thái,
một hàng tổng.

| Trạng thái | n | Q3→Q4 | Q3 | Q4 |
|---|---|---|---|---|
| BULL · close trên high Q1 | | | | |
| BEAR · close dưới low Q1 | | | | |
| ~~BEAR · phá hụt lên~~ † | | | | |
| ~~BULL · phá hụt xuống~~ † | | | | |
| NEUTRAL (mốc sanity) | | | | |
| Tổng chu kỳ hợp lệ / bị loại | | | | |

**† Hai hàng này in xám.** Chúng đã có phán quyết — percentile 3,0 và 2,9, xem
§2 — và chỉ nằm đây để đối chiếu. Chú thích ngay dưới bảng, không phải trong
header file, vì người đọc bảng có thể chưa bao giờ mở file.

Dựng trong `if showTable and barstate.islast`, có guard `if na(tbl)` trước
`table.new`.

---

## 9. Không repaint

- Trạng thái chốt tại nến **đầu Q3** từ `close[1]` — dữ liệu đã đóng.
- Điểm chốt tại nến **đầu chu kỳ kế** từ `close[1]` — dữ liệu đã đóng.
- Nhãn vẽ tại nến quyết định và không bao giờ dịch.
- Không `request.security`, nên không có lớp lookahead nào để sai.

Thứ duy nhất cập nhật trong nến hiện tại là cực trị của quarter đang chạy và
bảng — đúng như mong đợi.

---

## 10. Inputs

```
Luoi
  tier          input.string("session", options=["session", "q90"])
  minBars       input.int(3, minval=1)

Hien thi
  showLevels    input.bool(true)    duong q1High / q1Low
  showBias      input.bool(true)    to nen Q3+Q4
  showLabels    input.bool(true)    nhan trang thai
  labelCycles   input.int(50, minval=1, maxval=200)
  showQuarters  input.bool(true)    vach bien quarter
  showTable     input.bool(true)    bang diem
```

Không có input nào về rủi ro, entry, SL, TP — file này không giao dịch.

---

## 11. Rủi ro đã biết

### 11.1 Bảng điểm KHÔNG phải bằng chứng

Nó không biết một lưới neo lệch ngẫu nhiên làm được bao nhiêu. Đó chính xác là
thứ đã giết phép đo ⑥: tỉ lệ sweep 90,4% nghe rất mạnh, nhưng nằm ở **percentile
41** của phân phối null — lưới giả cũng làm được vậy.

Nếu hai ô mới cho 58% trên bảng, con số đó **chưa nói gì** cho tới khi có null
model. Câu duy nhất bảng này trả lời được là "hình dạng của setup trông thế nào
và nó xuất hiện bao nhiêu lần", không phải "nó có edge không".

Ghi câu này vào header file, không chỉ trong spec.

### 11.2 Có lý do để nghi ngờ trước

Phép đo ① cho thấy ranh giới Q1/Q2 không đặc biệt so với một lưới neo bất kỳ
(percentile 41). Nếu bản thân cái range không đặc biệt thì "đóng ngoài range nó"
khó mà đặc biệt. Vẫn đáng làm vì rẻ và vì chưa ai đo.

### 11.3 Confound 18:00

Khe nghỉ hằng ngày kết thúc đúng biên Q1. §6 giảm nhẹ bằng luật `minBars` nhưng
không xoá được: quarter đầu mỗi chu kỳ luôn bắt đầu ngay sau một khe dữ liệu.

### 11.4 Chưa compile

Pine không compile được ở máy này. Mọi thứ chỉ qua checker tĩnh, đối chiếu với
`quarters.py`, và đọc tay. **Không được viết "đã test"** ở bất cứ đâu.

Chỗ ngờ nhất: `hour(time, "America/New_York")` — cú pháp timezone của `hour()`.
Nếu TradingView báo lỗi, cách sửa là dùng `timestamp()`/`time()` với tham số
timezone, hoặc tính offset thủ công từ `time_close` — nhưng thủ công thì mất xử
lý DST và **không được làm** nếu không có bù trừ DST tường minh.

---

## 12. Ngoài phạm vi

- Luật vào lệnh, SL/TP, file strategy. Bị §7 của Phase 1 chặn cho tới khi có
  tiền đề đứng được.
- Mô hình null / nghiên cứu thống kê cho hai ô mới. Đó là spec riêng, và spec
  đó phải khoá trước số phép kiểm định và ngưỡng — xem hội thoại brainstorming
  ngày 2026-09-13 (hướng C: hai kiểm định xác nhận, Bonferroni 97,5%).
- Tầng nano / weekly / monthly / yearly.
- Sửa `rsi_fvg/quarters.py`. File này mirror nó, không đổi nó.

---

## 13. Kiểm chứng

Pine không compile được. Nhưng khác ba dự án Pine trước, lần này **có bản gốc
bằng Python để đối chiếu bằng máy** — và phần dễ sai nhất của file (timezone,
DST, biên chu kỳ) nằm đúng trong phần đối chiếu được đó.

### 13.1 Checker tĩnh

`scratchpad/kp_check.py` trên file mới. Phải in `SACH`.

### 13.2 Đối chiếu lưới với `quarters.py` — bắt buộc

Viết `scratchpad/qt_gridcheck.py`:

1. Sinh một chuỗi epoch M5 phủ **ít nhất hai lần chuyển DST của New York** theo
   cả hai chiều (tháng 3 và tháng 11), cộng vài ngày thường.
2. Chạy `label_quarters(epoch, tier)` cho cả `"session"` và `"q90"`.
3. Cài lại **đúng số học §3.2 của Pine** bằng Python — `hour` lấy từ
   `zoneinfo("America/New_York")`, rồi `(h+6) % 24`, `floor(/6)`, v.v.
4. Khẳng định hai bên cho **cùng `q_index` trên mọi mốc thời gian**, và cùng chỗ
   đổi chu kỳ.

Đây là bản mô phỏng số học của Pine, không phải bản thân Pine — nó **không**
chứng minh `hour(time, tz)` của TradingView hành xử đúng. Ghi rõ giới hạn đó
trong docstring của script.

**Test biên bắt buộc:** một mốc rơi đúng 18:00 NY; một mốc ngay trước và sau mỗi
lần chuyển DST; một mốc 00:00, 06:00, 12:00 NY (ba biên quarter còn lại).

### 13.3 Oracle cho phân loại năm trạng thái

Viết `scratchpad/qt_state_oracle.py` + test: hàm thuần nhận
`(q1High, q1Low, q2High, q2Low, q2Close)` trả về `1..5`. Test bắt buộc:

1. Năm ô, mỗi ô một ca cơ bản
2. **Quét thủng low rồi đóng trên high → trạng thái 1**, không phải 5 (§1)
3. Quét thủng high rồi đóng dưới low → trạng thái 2
4. `q2Close == q1High` đúng bằng → **không** phải trạng thái 1 (luật là `>` chặt)
5. `q2High == q1High` đúng bằng → **không** tính là đã phá (luật là `>` chặt)
6. Phân hoạch đầy đủ: sinh ngẫu nhiên vài nghìn bộ năm số, khẳng định mọi bộ rơi
   vào **đúng một** ô và không bộ nào rơi ra ngoài

Mutation testing trên oracle: đảo `>` thành `>=` ở từng chỗ, bỏ nhánh "phá cả
hai", đảo thứ tự ưu tiên close/clear. Mỗi mutation **phải** làm ít nhất một test
đỏ; cái nào sống sót thì thêm test cho tới khi chết.

### 13.4 Đọc tay

Đối chiếu từng dòng §3.2 của Pine với `label_quarters`, và từng nhánh phân loại
với oracle §13.3.
