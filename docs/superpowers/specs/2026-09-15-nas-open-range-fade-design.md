# NAS Open Range Fade (`nas_open_range_fade`) — Design Spec

**Ngày:** 2026-09-15
**Trạng thái:** chờ duyệt
**Nguồn:** hội thoại brainstorming 2026-09-15, kèm ảnh chart NAS100 M1 do người dùng chú thích
**Phạm vi:** một file mới `pine/nas_open_range_fade.pine`. **Không** có bản
strategy, **không** SL/TP, **không** đặt lệnh.

Công cụ đánh dấu. Nó nói "cú phá range vừa hỏng ở đây", không nói nên làm gì
với chuyện đó.

---

## 1. Mục tiêu

Hai phiên mỗi ngày mở lúc **07:00** và **19:00** giờ UTC+7. Giờ đầu tiên của
mỗi phiên tạo ra một range. Khi giá đóng cửa vượt ra khỏi range rồi **quay lại
xuyên qua** mốc của cây nến ngược chiều cuối cùng trước cú phá, đó là dấu hiệu
cú phá đã hỏng.

Đây là setup **đảo chiều**, không phải setup đi theo cú phá. Phá lên mà hỏng thì
tín hiệu là **BÁN**. Người dùng đã xác nhận điều này khi được hỏi thẳng.

---

## 2. Range

### 2.1 Cửa sổ

| phiên | cửa sổ gom range (UTC+7) |
|---|---|
| sáng | `[07:00, 08:00)` |
| tối | `[19:00, 20:00)` |

`rangeHigh` = high cao nhất của mọi nến 1m trong cửa sổ.
`rangeLow` = low thấp nhất của mọi nến 1m trong cửa sổ.

Range được **chốt cứng** tại thời điểm cửa sổ đóng và không đổi cho tới phiên
sau.

### 2.2 Tính từ nến 1m, KHÔNG dùng `request.security`

Đây là quyết định chịu lực, và nó tránh một cái bẫy im lặng.

Đề bài nói "cây H1 mở lúc 07:00". Cách hiển nhiên là gọi
`request.security(syminfo.tickerid, "60", ...)`. **Không làm vậy.** Nến H1 của
TradingView neo theo phiên của sàn, không neo theo 07:00 UTC+7. Trên NAS100 của
FOREX.com, "cây H1 mở lúc 07:00 UTC+7" rất có thể **không tồn tại** như một nến
H1 — nó rơi vào giữa hai nến. Khi đó `request.security` vẫn trả về một giá trị,
chỉ là giá trị của một cây khác. Không lỗi, không cảnh báo, chỉ là một range
sai.

Gom trực tiếp từ nến 1m cho đúng thứ người dùng vẽ trong ảnh, và không phụ
thuộc vào cách sàn cắt nến H1.

### 2.3 Chart phải là M1

Toàn bộ logic đọc nến 1m. Trên khung khác, cửa sổ `[07:00, 08:00)` chứa một
hoặc không nến nào và setup vô nghĩa.

File **không tự sửa lại cho khung khác**. Nó vẽ một nhãn cảnh báo ở nến cuối khi
`timeframe.period != "1"` và **không sinh tín hiệu nào**. Im lặng chạy sai trên
khung khác là chế độ hỏng tệ hơn nhiều so với từ chối chạy.

### 2.4 Guard số nến tối thiểu

`minRangeBars` (mặc định 30). Nếu cửa sổ gom được ít hơn ngần ấy nến 1m thì
range **không được chốt** và phiên đó không sinh tín hiệu nào.

Lý do: NAS100 là CFD chạy gần như 24h nên cửa sổ đầy đủ phải có 60 nến. Một cửa
sổ chỉ có 3 nến nghĩa là dữ liệu thủng — ngày lễ, sàn nghỉ, hoặc lỗ feed — và
một range dựng từ 3 nến là một con số vô nghĩa trông y hệt một con số thật.
Ngưỡng 30 (một nửa) là bảo thủ và rẻ.

### 2.5 Múi giờ

Dùng `"Asia/Bangkok"` — UTC+7 cố định, không DST.

**Phải nói rõ vì nó là nguồn nhiễu thật:** UTC+7 không có DST còn Mỹ thì có, nên
hai mốc này **trôi so với phiên Mỹ mỗi năm hai lần**. `19:00 UTC+7` là 08:00 ET
vào mùa hè nhưng 07:00 ET vào mùa đông. Cùng một setup đo hai thứ khác nhau tuỳ
mùa. Không sai — người dùng chọn mốc theo giờ địa phương — nhưng khi đọc kết quả
gộp nhiều năm thì đây là biến gây nhiễu, và nó phải được nêu trong báo cáo bất
kì nào dùng file này.

---

## 3. Máy trạng thái

### 3.1 Trạng thái, chiều LÊN (chiều XUỐNG soi gương)

Không dùng biến trạng thái dạng số. Ba biến độc lập cho mỗi chiều:

| biến | nghĩa |
|---|---|
| `upEligible` | một cú phá lên MỚI có được tính không |
| `upArmed` | đang chờ giá đóng cửa trở lại xuyên mốc |
| `upLevel` | close của nến ĐỎ cuối cùng trước cú phá |

### 3.2 Cú phá là một SỰ KIỆN, không phải một mức

Người dùng chọn: *"mỗi cú phá một lần"*, và *"phải đóng lại trong range trước"*.

Vì vậy một cú phá lên được tính khi **cả hai** đúng:

```
close > rangeHigh   và   upEligible
```

`upEligible` bật lại **chỉ khi** một nến đóng cửa **trong** range
(`rangeLow <= close <= rangeHigh`). Nó tắt ngay khi một cú phá được tính.

Nếu chỉ so mức (`close > rangeHigh`) thì mọi nến ở trên biên đều là "phá" và
`upLevel` bị ghi đè liên tục suốt lúc giá còn ở ngoài — mốc đuổi theo giá thay
vì đứng yên. Đó là lý do luật này tồn tại.

Nến đóng cửa ở **biên kia** (dưới `rangeLow`) **không** bật lại `upEligible`:
nó ở ngoài range, không phải trong.

### 3.3 "Nến đỏ cuối cùng trước cú phá"

Theo dõi liên tục bằng một biến, không dùng vòng lặp:

```
lastDownClose := close   khi   close < open
```

`close == open` không phải đỏ cũng không phải xanh — bỏ qua, nhất quán với
`momentum_expansion` và `rsi_failure_swing`.

**Cập nhật biến này là bước CUỐI CÙNG trong nến** (§3.5). Nhờ vậy khi cú phá
được kiểm, `lastDownClose` phản ánh các nến **hoàn toàn trước** nến hiện tại —
đúng chữ "trước khi có cú breakout". Nếu cập nhật trước, một nến phá mà bản thân
nó là nến đỏ sẽ tự lấy close của chính mình làm mốc.

Biến này có **hai điểm xoá** trong code: một lần khi cửa sổ gom của phiên mới
bắt đầu (§3.7 xoá sạch mọi thứ), và một lần nữa **khi range được chốt**.
Nhưng chỉ điểm xoá **thứ nhất** thực sự chịu lực. Điểm xoá thứ hai là **phòng
thủ thừa**: bước 6 (cập nhật `lastDownClose`/`lastUpClose`) chỉ chạy sau khi
đã qua cổng "không còn trong cửa sổ gom" ở **cả hai** bản Pine lẫn oracle, và
điểm xoá phiên mới (thứ nhất) đã xoá sạch hai biến này trước đó trong cùng
phiên. Vì vậy, giữa lúc phiên mới bắt đầu và lúc range được chốt, hai biến
này **luôn đã là `na`/`None`** — không có gì để điểm xoá thứ hai xoá cả. Diễn
giải cũ ("nến trong cửa sổ gom không được làm mốc") mô tả đúng **hệ quả**
nhưng gán sai **nguyên nhân**: nến trong cửa sổ gom bị loại bởi chính cổng
cửa sổ (bước 1 luôn `continue`/bỏ qua khi còn `inWin`), không phải bởi điểm
xoá thứ hai. Điểm xoá thứ hai được giữ lại vì nó rẻ và vì nó sẽ bắt đầu có
tác dụng thật nếu sau này ai đó dời cổng cửa sổ đi — nhưng ở trạng thái code
hiện tại, đừng khẳng định nó đang làm việc gì.

### 3.4 Ba điều kiện để arm

```
close > rangeHigh
upEligible
not na(lastDownClose)   và   lastDownClose < rangeHigh
```

Vế cuối cần giải thích. `lastDownClose` là close của một nến nằm sau lúc chốt
range, nên nó **có thể** ở trên `rangeHigh` — trường hợp nến đỏ đó tự nó đã là
một cú phá. Khi ấy `upLevel > rangeHigh` và điều kiện "đóng cửa trở lại dưới
mốc" có thể thoả **trong khi giá vẫn còn trên range** — một tín hiệu suy biến.
Chặn thẳng: mốc phải nằm dưới biên mà giá vừa phá qua, nếu không thì không arm.

Chiều xuống soi gương đúng từng vế: `close < rangeLow`, `dnEligible`,
`not na(lastUpClose)` và **`lastUpClose > rangeLow`**.

Khi arm: `upLevel := lastDownClose`, `upArmed := true`, `upEligible := false`.

**Cú phá mới ghi đè mốc cũ.** Nếu đang armed mà có cú phá lên mới hợp lệ, `upLevel`
bị thay. Lý do: mốc được định nghĩa là "nến đỏ cuối cùng trước cú phá **gần
nhất**" — theo định nghĩa chỉ có một. Không giữ hàng đợi.

### 3.5 Tín hiệu, và thứ tự trong một nến

Tín hiệu BÁN: `upArmed và close < upLevel`. Bắn xong thì `upArmed := false`.
Tín hiệu MUA soi gương: `dnArmed và close > dnLevel`.

Thứ tự sáu bước, **đúng thứ tự này**:

```
1. gom range (nếu đang trong cửa sổ) / chốt range (nếu cửa sổ vừa đóng)
2. kiểm tín hiệu BÁN và MUA        -> bắn, disarm
3. cập nhật upEligible / dnEligible (nếu nến này đóng trong range)
4. kiểm cú phá LÊN                 -> arm
5. kiểm cú phá XUỐNG               -> arm
6. cập nhật lastDownClose / lastUpClose TỪ NẾN NÀY
```

Ba chỗ chịu lực:

- **Bước 6 phải cuối cùng** — §3.3.
- **Bước 2 phải trước bước 4** — nếu không, một cú phá mới sẽ ghi đè mốc trước
  khi tín hiệu của mốc cũ kịp bắn. Hai điều kiện loại trừ nhau trên cùng một
  nến (`close < upLevel < rangeHigh` không thể đồng thời `close > rangeHigh`),
  nên thực tế không va nhau — nhưng thứ tự vẫn được cố định để không phụ thuộc
  vào lập luận đó.
- **Bước 3 trước bước 4** — chỉ để tất định. Một nến không thể vừa đóng trong
  range vừa đóng trên `rangeHigh`, nên thứ tự hai bước này không đổi hành vi.

### 3.6 Hai chiều độc lập

Chiều lên và chiều xuống có bộ biến riêng và **không** ảnh hưởng nhau. Đang
armed chiều bán mà giá phá xuống dưới `rangeLow` thì cú phá xuống đó arm chiều
mua bình thường, chiều bán vẫn giữ nguyên.

Thực tế hai chiều hiếm khi cùng armed: `upLevel` nằm dưới `rangeHigh` (§3.4),
nên giá muốn xuống tới `rangeLow` thường đã đóng cửa dưới `upLevel` trước và
tín hiệu bán đã bắn. Nhưng "hiếm" không phải "không bao giờ", và spec không
dựa vào điều đó.

### 3.7 Phiên mới xoá sạch

Khi cửa sổ gom của phiên kế tiếp bắt đầu, **mọi** trạng thái bị xoá: range,
`upArmed`/`dnArmed`, `upLevel`/`dnLevel`, `lastDownClose`/`lastUpClose`,
`upEligible`/`dnEligible`. Một setup đang armed **không sống qua phiên**.

---

## 4. Không repaint

Tín hiệu và cú phá đều gác bằng `barstate.isconfirmed`.

Ở setup này việc gác là đúng về ngữ nghĩa: mọi luật đều phát biểu bằng **giá
đóng cửa** ("1m close qua high"), nên đánh giá trước lúc nến đóng là đánh giá
một con số chưa tồn tại.

Trên nến lịch sử `barstate.isconfirmed` luôn đúng, nên phần lịch sử không đổi
một bit so với bản không gác.

**Cái giá, phải nói rõ:** nếu không có lần script chạy nào rơi đúng tick đóng
nến — feed chậm, hoặc mở chart giữa chừng một nến — thì nến đó không sinh **cả**
mũi tên lẫn alert.

Cú phá **không mất hẳn** — nhưng lập luận này chỉ đúng cho **sáu bước của
§3.5**, không đúng cho bước 0 (xoá trạng thái phiên mới, §3.7). Vì cả sáu
bước đó đều nằm sau cùng một cổng `barstate.isconfirmed`, một nến bị lỡ thì
**không bước nào trong sáu bước** chạy cho nó — kể cả bước 6, nên
`lastDownClose` cũng không trôi theo nó. Nến xác nhận kế tiếp vẫn thấy
`upEligible` còn bật và vẫn arm nếu còn đóng cửa trên biên.

Bước 0 thì khác hẳn: nó không idempotent, mà là một **sự kiện cạnh lên**
(`newSess`), chỉ đúng trên đúng một nến — xem §11 mục 7 để biết hậu quả khi
đúng nến đó bị lỡ.

Hai hệ quả thật, nhỏ hơn nhưng có thật: cú phá được ghi nhận **muộn một nến**,
và nếu chính nến bị lỡ là một nến đỏ thì nó **không được xét làm mốc** —
`upLevel` sẽ là close của một nến đỏ cũ hơn, tức một mốc khác với mốc mà người
đọc chart nhìn thấy.

Tải lại chart sẽ vẽ lại mũi tên trên nến lịch sử, còn `alert()` **không bao giờ
bắn lại**.

Vì vậy: **thấy mũi tên trên lịch sử không phải bằng chứng alert đã bắn.**

---

## 5. Vẽ

### 5.1 Box — và trần 500

Người dùng yêu cầu range dạng **box**, nên dùng `box.new`.

`box` bị Pine chặn cứng **500**. Hai box mỗi ngày là khoảng 250 phiên — nửa năm
lịch sử. Cũ hơn thì box **lặng lẽ biến mất khỏi chart mà không báo gì**, đúng
cái đã xảy ra với `kill_peak`.

Chấp nhận, với hai điều kiện:

1. Khai `max_boxes_count=500` tường minh.
2. **Trần này chỉ ảnh hưởng phần VẼ, không ảnh hưởng một bit nào của logic.**
   Máy trạng thái không đọc đối tượng box; nó đọc `rangeHigh`/`rangeLow` là
   biến `float`. Mũi tên tín hiệu dùng `plotshape` — không có trần.

Box được mở rộng sang phải (`box.set_right`) mỗi nến cho tới khi phiên kết thúc,
đúng như ảnh.

### 5.2 Những thứ còn lại — không dùng `line` nào

| vẽ gì | bằng gì | trần |
|---|---|---|
| box range | `box.new` + `box.set_right` | **500** |
| mốc `upLevel` / `dnLevel` lúc đang armed | `plot(..., style=plot.style_linebr)` | không có |
| mũi tên tín hiệu | `plotshape` | không có |
| nhãn cảnh báo sai khung | `label.new` | 500 (một cái) |

`line.new` bị chặn 500 và tràn thì cái cũ nhất biến mất. `plot` với
`style_linebr` không có trần và tự ngắt khi giá trị là `na` — đúng thứ cần cho
một mốc chỉ tồn tại lúc armed.

### 5.3 Bất biến

Mọi lệnh vẽ gác bằng chính biến trạng thái hoặc biến tín hiệu — **không** lệnh
nào tính lại điều kiện. `kill_peak` đã mắc lỗi này: phần vẽ dùng một ngưỡng,
phần tín hiệu dùng ngưỡng khác, và chart vẽ nhãn mà strategy không đồng ý.

---

## 6. Alert

Một lời gọi `alert()` cho mỗi chiều, cùng hình JSON với các file Pine khác
trong repo:

```
{"symbol":"<ticker>","tf":"<period>","direction":"SELL","setup":"ORFADE",
 "level":<upLevel>,"range_high":<rangeHigh>,"range_low":<rangeLow>,
 "close":<close>,"session":"<07:00|19:00>","wait":<số nến từ cú phá>}
```

`alert.freq_once_per_bar_close`.

**Định dạng số là `"0.#####"`, KHÔNG phải `"#.#####"`.** Cái sau là
`DecimalFormat` của Java và nó rụng số 0 đứng đầu, sinh `"level":.98432` — JSON
hỏng trên instrument dưới 1.0. NAS100 không bị, nhưng 9 file Pine cũ trong repo
đang mang lỗi này và file mới không mang thêm.

`wait` và `session` có mặt vì chúng là hai biến gây nhiễu rõ nhất khi đọc kết
quả (§9 mục 2 và §2.5).

---

## 7. Bảng trạng thái

Góc trên bên phải, chỉ vẽ ở `barstate.islast`:

| dòng | nội dung |
|---|---|
| phiên | `07:00` / `19:00` / `—`, và số nến đã gom |
| range | `rangeHigh` / `rangeLow`, hoặc `—` nếu chưa chốt |
| chiều LÊN | `READY` / `ARMED @ <upLevel>`, và số nến từ cú phá |
| chiều XUỐNG | như trên |
| tín hiệu cuối | chiều, giá đóng cửa, `wait` |

---

## 8. Input

| nhóm | input | mặc định |
|---|---|---|
| Phiên | `tz` | `"Asia/Bangkok"` |
| | `sess1Hour` / `sess2Hour` | 7 / 19 |
| | `rangeMinutes` | 60 |
| | `minRangeBars` | 30 |
| Chiều | `enableUpBreak` / `enableDownBreak` | bật / bật |
| Hiển thị | `showBox`, `showLevel`, `showSignals`, `showTable` | bật |
| | `boxTransp` | 85 |

**Không có input nào cho SL/TP, cho hạn chờ, cho bộ lọc.** Xem §9.

---

## 9. Những gì cố ý KHÔNG làm

- **Không SL/TP, không bản strategy.** Người dùng xác nhận hai hộp màu trong
  ảnh chỉ là tô highlight. File này là công cụ đánh dấu, giống
  `momentum_expansion`. Không có SL/TP thì không backtest được bằng
  `strategy()`, và đó là lựa chọn có ý thức — đo bằng mắt trước.
- **Không hạn chờ.** Một cú đóng cửa xuyên mốc sau 3 tiếng vẫn được tính. Cùng
  tinh thần "đo trước, lọc sau" của `rsi_trend_pullback`. Hệ quả ở §10 mục 2.
- **Không lọc theo độ rộng range.** Một range 5 điểm và một range 200 điểm cho
  cùng một loại tín hiệu. Thêm ngưỡng lúc chưa đo là đoán.
- **Không dùng `request.security`.** §2.2.
- **Không tự điều chỉnh cho khung khác M1.** §2.3.

---

## 10. Kiểm chứng

**KHÔNG COMPILE ĐƯỢC PINE Ở MÁY NÀY.** Không báo cáo nào được nói "đã test",
"đã chạy", "verified", "works" về code Pine. Chỉ được nói "qua checker tĩnh",
"đối chiếu với oracle", "đọc tay".

1. **Oracle Python** dựng lại máy trạng thái §3, **commit vào
   `tests/pine_oracles/`**. Oracle nhận sẵn danh sách nến kèm nhãn phiên; nó
   **không** tự tính múi giờ — múi giờ là việc của `hour(time, tz)` trong Pine,
   không phải thứ đang có rủi ro. Thứ có rủi ro là máy trạng thái và thứ tự
   trong nến.
2. **Mutation testing.** Đột biến bắt buộc phải giết: cập nhật `lastDownClose`
   trước bước kiểm phá thay vì sau; bỏ điều kiện `upEligible`; bỏ vế
   `lastDownClose < rangeHigh`; đổi `close < upLevel` thành `<=`; cho nến đóng
   ở biên kia bật lại `upEligible`; bỏ bước xoá trạng thái ở phiên mới. Con nào
   sống sót là thiếu test, không phải "chấp nhận được".
3. **Checker tĩnh**: thụt dòng nối tiếp **không chia hết cho 4**; không `ta.*`
   trong `if`; không `line.new(`; không `"#.#####"`.
4. **`tests/test_pine_indent.py`** quét mọi file trong `pine/` và sẽ tự bắt file
   này. **Nó chưa có trên `master`** — nó nằm trên nhánh `feat/rsi-trend-pullback`
   và chỉ tồn tại sau khi nhánh đó merge. Cho tới lúc đó, checker thụt dòng của
   mục 3 phải chạy tay. Đây là phụ thuộc chéo nhánh có thật, không phải giả định.

Không có bản chép nào, nên **không cần** guard `tests/test_pine_blocks.py` cho
file này.

---

## 11. Rủi ro và hạn chế đã biết

1. **Mốc 07:00 và 19:00 trôi so với phiên Mỹ mỗi năm hai lần** (§2.5). Một mẫu
   gộp nhiều năm trộn hai chế độ khác nhau.

2. **Không có hạn chờ nghĩa là `wait` không có chặn trên.** Một mốc armed lúc
   08:15 và bị xuyên lúc 11:40 vẫn tính là tín hiệu, dù nó chẳng còn liên quan
   gì tới cú phá nữa. Khi đọc kết quả, **đừng nhìn số tín hiệu một mình — nhìn
   nó cùng phân phối `wait`.** Đó là lý do `wait` có mặt ở cả bảng lẫn alert.

3. **Box biến mất sau ~250 phiên** (§5.1). Chỉ ảnh hưởng phần vẽ.

4. **Một cú phá bị lỡ tick đóng nến thì mất hẳn**, không bắn muộn (§4). Chỉ xảy
   ra live.

5. **Chưa từng compile trên TradingView.** Toàn bộ file Pine trong repo đều
   chưa. File này không dùng `force_overlay` nên rủi ro thấp hơn
   `rsi_failure_swing`, nhưng "thấp hơn" không phải "đã kiểm".

6. **`box` là loại đối tượng đầu tiên trong repo có trần bị chạm thật.** Các file
   trước dùng `label` (500, hiếm khi chạm) hoặc `plot` (không trần). Ở đây trần
   bị chạm sau nửa năm lịch sử, tức chắc chắn sẽ xảy ra với người dùng thật.

7. **Xoá trạng thái phiên (bước 0) là edge-triggered, không phải
   idempotent, và nằm sau cùng cổng `isconfirmed` như sáu bước còn lại.**
   §4 lập luận "một nến bị lỡ thì không bước nào chạy cho nó" — lập luận đó
   **đúng cho sáu bước của §3.5**, nhưng **sai cho bước 0**. Bước 0 chạy
   khi:

   ```pine
   bool newSess = (inWin1 and not nz(inWin1[1], false))
        or (inWin2 and not nz(inWin2[1], false))
   ```

   Đây là một **sự kiện cạnh lên**: `newSess` chỉ đúng trên đúng một nến —
   nến đầu tiên bước vào cửa sổ gom. Nếu đúng nến đó không chạy dưới cổng
   `isconfirmed` (đứt feed, hoặc script gián đoạn ngay lúc chart bước qua
   mốc 07:00/19:00), thì nến xác nhận kế tiếp có `inWin1[1] == true` (hoặc
   `inWin2[1] == true`), `newSess` là **false**, và **bước xoá không bao
   giờ chạy cho phiên đó**. Không có nến nào khác bù lại — cửa sổ đó vĩnh
   viễn mất lượt reset của mình.

   Hậu quả dây chuyền, tất cả im lặng, không lỗi, không cảnh báo:

   - `rangeHigh`/`rangeLow` không phải `na` nữa → nhánh `math.max`/`math.min`
     chạy thay vì nhánh khởi tạo → **range phiên mới bị gộp với range phiên
     trước** thay vì được tính lại từ đầu.
   - `finalized` vẫn `true` từ phiên trước → khối chốt range (bước 1b)
     không chạy lại → `rangeOk`, `upEligible`, `dnEligible`, `upArmed`,
     `dnArmed`, `upLevel`, `dnLevel` đều giữ nguyên trạng thái của phiên
     **trước**, áp dụng nhầm lên dữ liệu của phiên **này**.
   - `nWin` cộng dồn qua nhiều phiên thay vì đếm lại từ 0 → bảng trạng thái
     (§7) hiện số nến sai, và `sessName` hiện tên phiên **cũ** (vì
     `sessName` cũng chỉ được gán trong khối bước 0) — alert JSON (§6) gắn
     nhãn `"session"` sai theo.

   Đây chính xác là chế độ hỏng mà §2.2 được viết ra để tránh — "không lỗi,
   không cảnh báo, chỉ là một range sai" — nhưng đến từ một cửa khác
   (script gián đoạn đúng lúc chuyển phiên) chứ không phải từ
   `request.security`.

   Lỗi này **tự lành khi reload chart**: nạp lại lịch sử tính `newSess` từ
   đầu trên toàn bộ nến đã có, nên bug chỉ tồn tại trong phiên live bị ảnh
   hưởng, không lan sang phiên sau.

   Có một trigger thứ hai, không cần chạy live mới gặp: `inWin1[1]` là
   **nến ngay trước trong chuỗi dữ liệu đưa vào script**, không phải "phút
   trước theo đồng hồ". Nếu thị trường đóng cửa rồi mở lại (cuối tuần, nghỉ
   lễ) sao cho nến cuối cùng trước khi đóng cửa và nến đầu tiên sau khi mở
   lại **cùng nằm trong cùng một cửa sổ gom** (ví dụ cả hai đều có
   `inWin1 = true`), thì `inWin1[1]` vẫn `true` ở nến đầu tiên sau gap và
   `newSess` vẫn câm — không cần lỗi feed, chỉ cần lịch thị trường bình
   thường xếp đúng chỗ.

   **Vì sao oracle không lộ chuyện này:** oracle reset theo **so sánh giá
   trị** (`if s != cur: ...`, xem `tests/pine_oracles/orfade_oracle.py`) —
   tức **level-triggered**, không phải edge-triggered. Oracle nhận sẵn
   `session[i]` là một nhãn đã tính rồi; nó không mô phỏng việc script bị
   lỡ mất đúng nến cạnh lên. Ở khía cạnh này oracle **an toàn hơn** bản
   Pine thật — và chính sự chênh lệch đó là lý do oracle không bao giờ có
   thể bắt được điểm giòn này của Pine bằng mutation testing hay bất kì
   test nào khác đối chiếu với nó. Đây là một giới hạn thật của phương
   pháp kiểm chứng bằng oracle, không phải một lỗ hổng có thể vá bằng cách
   thêm test.

8. **Trạng thái sống qua mọi lần đóng cửa thị trường trong tuần, không bị
   giới hạn trong phạm vi một ngày.** Không có gì trong máy trạng thái buộc
   nó reset theo *ngày*. Ví dụ cụ thể: range của phiên tối thứ Sáu (19:00),
   cùng với `upArmed`/`dnArmed`, `upLevel`/`dnLevel`,
   `lastDownClose`/`lastUpClose`, sống liên tục — không hề bị đụng tới —
   cho tới khi `newSess` kế tiếp trở thành true, tức **07:00 sáng thứ Hai**.
   Mọi nến chạy từ lúc thị trường mở lại đầu tuần (thường sớm hơn nhiều so
   với 07:00 thứ Hai giờ UTC+7, tuỳ sàn) cho tới 07:00 thứ Hai đều được xử
   lý bằng **range của tối thứ Sáu** và **mốc `lastDownClose`/`lastUpClose`
   được ghi nhận từ đêm thứ Sáu**.

   Gap giá qua cuối tuần gần như luôn đẩy giá mở cửa ra ngoài range tối thứ
   Sáu. Kịch bản thật: giá mở cửa đầu tuần nhảy qua khỏi `rangeHigh`/
   `rangeLow` của tối thứ Sáu, rồi trong vài giờ đầu tuần quay lại xuyên
   qua một `lastDownClose`/`lastUpClose` đã **ba ngày tuổi** — sinh ra một
   tín hiệu (ví dụ BÁN) lúc khoảng 06:30 sáng thứ Hai, nhưng alert JSON vẫn
   gắn nhãn `"session":"19:00"` — đúng về mặt kỹ thuật (đó đúng là phiên
   chưa bị xoá), nhưng gây hiểu lầm nếu người đọc hình dung phiên 19:00 chỉ
   kéo dài vài tiếng.

   Về mặt câu chữ, spec không cấm điều này: §9 mục 2 nói rõ "không hạn
   chờ", và §3.7 chỉ nói setup không sống qua *phiên* — mà phiên kế tiếp
   đúng là 07:00 thứ Hai, không sớm hơn. Nhưng ví dụ minh hoạ ở §11 mục 2
   ("armed lúc 08:15, bị xuyên lúc 11:40") gợi ý một khung thời gian vài
   tiếng trong cùng ngày; không ai đọc ví dụ đó mà hình dung ra một khoảng
   chờ 59 tiếng vắt qua cả cuối tuần. Và khác với hầu hết rủi ro khác trong
   mục này, đây **không phải một trường hợp hiếm hay xác suất thấp** — nó
   xảy ra **đều đặn mỗi tuần**, với mọi setup còn armed vào cuối phiên tối
   thứ Sáu.

   Hệ quả kéo theo cho việc đọc `wait` (§9 mục 2, §11 mục 2): `wait` đếm
   **số nến 1m**, không đếm phút hay giờ theo đồng hồ. Trên chuỗi nến liền
   mạch trong ngày, một đơn vị `wait` xấp xỉ một phút — hai con số gần như
   trùng nhau. Nhưng qua một khoảng gián đoạn thị trường (cuối tuần, nghỉ
   lễ), `wait` vẫn chỉ đếm nến đã xử lý, nên `wait = 5` có thể là 5 phút
   trong một phiên liền mạch, hoặc là 5 nến trải dài qua một kỳ nghỉ cuối
   tuần. Phân phối `wait` — thứ §11 mục 2 nói phải luôn nhìn kèm số lượng
   tín hiệu — do đó **trộn lẫn hai đơn vị đo khác nhau** (nến-liền-mạch và
   nến-vắt-qua-gap) mà không có cột nào trong bảng (§7) hay trường nào
   trong alert JSON (§6) đánh dấu sự khác biệt đó.
