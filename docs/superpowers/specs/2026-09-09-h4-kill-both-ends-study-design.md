# XAUUSD — Nến H4 bị kill hai đầu — Design Spec

**Ngày:** 2026-09-09
**Trạng thái:** Đã duyệt thiết kế
**Phase:** 1 của 2. Phase 2 (luật vào/ra) là spec riêng và **chỉ được viết nếu Phase 1 đạt luật §10**.
**Phạm vi:** hai module mới (`rsi_fvg/h4_grid.py`, `rsi_fvg/h4_kill.py`), một script (`scripts/study_h4_kill.py`), hai file test, cộng hai thay đổi **thuần thêm** vào file có sẵn (§7). **Không** sửa engine, **không** sửa optimizer, **không** thêm strategy hay adapter, **không** sinh tín hiệu nào, **không** tính P&L.

**Câu hỏi gốc của người dùng:** XAUUSD trên sàn FXCM, theo UTC+7, đánh dấu high/low của cây H4 mở lúc 1h và 5h sáng; tính tỉ lệ những cây đó bị kill hai đầu trong một ngày; và max range kill.

---

## 1. Mục tiêu

Trả lời **một câu**: hai cây H4 đó có bị quét cả hai đầu nhiều hơn mức mà **hình học** đã giải thích được hay không?

"Hình học" ở đây không phải cách nói tu từ. §2.3 cho thấy hai cây được hỏi là hai cây **hẹp nhất** trong sáu cây H4 của ngày, và theo định nghĩa cửa sổ mà người dùng đã chọn thì chúng cũng nhận **hai cửa sổ dài nhất**. Cây hẹp hơn và có nhiều thời gian hơn thì đương nhiên bị quét hai đầu nhiều hơn, không cần bất kỳ hành vi thị trường nào. Một báo cáo chỉ in ra "cây A 5x%, cây B 6x%" sẽ khiến người đọc kết luận sai. Spec này tồn tại phần lớn là để chặn điều đó.

Không nằm trong phạm vi: luật vào/ra, backtest P&L, "sau khi kill hai đầu thì giá đi đâu", win rate, và bất kỳ khuyến nghị giao dịch nào.

---

## 2. Lưới H4 neo 17:00 New York

### 2.1 Mốc neo và hai cây được hỏi

Người dùng phát biểu đề bài theo giờ UTC+7 ("mở lúc 1h và 5h sáng"), nhưng đã **duyệt** cách neo theo nến H4 của FXCM, tức neo **17:00 New York** và chạy theo DST của New York. Hai cách này chỉ trùng nhau nửa năm: quy đổi 17:00 NY sang giờ Việt Nam cho 5h vào mùa đông (EST) nhưng 4h vào mùa hè (EDT).

Vì vậy **spec này gọi hai cây theo giờ New York**, và mọi con số đều tính trên giờ NY. Gọi theo giờ VN là mời DST vào làm nhiễu.

Sáu slot của một ngày giao dịch, đánh số theo thứ tự thời gian từ mốc neo:

| slot | cửa sổ NY | tên người dùng dùng | ghi chú |
|---|---|---|---|
| 0 | 17:00–21:00 | "cây mở 5h" (mùa đông) | **cây B** — giờ đầu là khe nghỉ, thực chất 18:00–21:00 |
| 1 | 21:00–01:00 | | |
| 2 | 01:00–05:00 | | |
| 3 | 05:00–09:00 | | |
| 4 | 09:00–13:00 | | London + NY chồng nhau |
| 5 | 13:00–17:00 | "cây mở 1h" (mùa đông) | **cây A** — đóng đúng mốc đóng ngày |

Ngày giao dịch chạy 17:00 → 17:00 NY. Mốc này trùng khít cả **khe nghỉ hằng ngày** lẫn **biên tuần**, cả hai đều đo được trên M1:

- Khe nghỉ hằng ngày: **17:00 → 18:00 NY**, 2.290 lần. Bar cuối trước khe ở giờ 16 (81,8%), bar đầu sau khe ở giờ 18 (91,1%).
- Biên tuần: đóng **17:00 NY thứ Sáu** (92% trong 331 khe cuối tuần sạch, bar cuối ở 16:57–16:59), mở lại **18:00 NY Chủ nhật** (81%). Khe cuối tuần bình thường dài **49 giờ**.

Đó là một sự tiện lợi, và đồng thời là confound của §5.2.

### 2.2 Số thật của lưới, đo trên XAUUSDc M1

Đo trên 3.299.723 bar M1 (2017-04-27 → 2026-09-08) để xác nhận lưới khớp dữ liệu trước khi xây gì lên nó:

| slot | bar median | range median (USD) |
|---|---|---|
| 0 | **179** | **4,76** |
| 1 | 240 | 6,25 |
| 2 | 240 | 8,35 |
| 3 | 240 | 10,40 |
| 4 | 240 | 13,20 |
| 5 | 238 | **6,22** |

Slot 1–4 có đúng 240 bar M1 = đúng 4 giờ, xác nhận mốc neo đúng. Slot 0 có 179 vì khe nghỉ ăn mất một giờ. Tổng: **2584** ngày giao dịch, **2385** ngày đủ cả sáu slot.

### 2.3 Hai thiên lệch phải kiểm soát, không phải nhắc qua

**(a) Hai cây được hỏi là hai cây hẹp nhất.** 4,76 và 6,22 USD, so với 13,20 của slot 4. Xác suất bị quét cả hai đầu là hàm giảm theo độ rộng, nên so sánh thô giữa các slot chủ yếu đang đo độ rộng. Kiểm soát bằng đại lượng ③ của §4.3.

**(b) Đơn vị USD không gộp được 9 năm.** Range median của slot 0 theo năm:

```
2017  2,56   2020  6,69   2023   4,15   2025  14,70
2018  2,57   2021  4,12   2024   5,41   2026  33,53
2019  3,00   2022  4,70
```

Gấp **13 lần** từ đầu đến cuối mẫu, và slot 5 cùng dạng (3,72 → 30,43). Một phân vị USD gộp cả mẫu gần như chỉ nói về 2025–2026. Xử lý bằng §4.4.

---

## 3. `rsi_fvg/h4_grid.py` — gán nhãn và gộp

Tách khỏi phần đo để mỗi module có một việc: file này biết về **thời gian**, `h4_kill.py` biết về **giá**.

### 3.1 `label_h4(time, anchor_offset=0) -> H4Labels`

Trả về `ny`, `trading_day` (naive, nửa đêm NY của ngày mở 17:00), `slot` (0..5), `day_num` (int64).

Số học:

```
ny       = server_to_ny(time)            # dùng lại rsi_fvg/quarters.py
ny       = ny - anchor_offset            # chỉ mô hình null dùng
naive    = ny.tz_localize(None)
h_shift  = (naive.hour + 7) % 24         # đưa 17:00 NY về 0
slot     = h_shift // 4
trading_day = naive.normalize() - (1 ngày nếu naive.hour < 17)
```

Ba điều phải làm đúng:

1. **Dùng lại `server_to_ny`, không viết lại.** Hàm đó đã được kiểm bằng dữ liệu và docstring của nó giải thích tại sao `Bars.time` là instant UTC thật chứ không phải giờ server (`rsi_fvg/quarters.py`). Viết lại là mời lại đúng cái bug đã tốn công bác bỏ một lần.
2. **KHÔNG nhét vào `label_quarters` sẵn có.** Hàm đó giả định **4** quarter một chu kỳ và neo **18:00** NY (`(hour + 6) % 24`). Lưới này có **6** slot và neo **17:00**. Nhồi vào sẽ phá cả hai study Quarterly Theory đang dùng nó.
3. **`trading_day` tính bằng số học lịch trên giờ treo tường naive**, không bằng số giây tích luỹ — trừ một ngày trên timestamp tz-aware là trừ 24 giờ tuyệt đối, và qua biên DST New York điều đó cho ra 23:00 hoặc 01:00 thay vì nửa đêm. Đây là bài học đã ghi trong `label_quarters`.

### 3.2 `aggregate_days(bars, labels, ...) -> pd.DataFrame`

Một dòng mỗi `trading_day`, cột `s0_open … s5_n` (OHLC + số bar cho từng slot), cộng `n_slots_present`. `open`/`close` lấy `first`/`last` — đúng vì `bars` theo thứ tự thời gian và `groupby` giữ thứ tự trong nhóm.

Thêm hai cột suy ra ở cấp ngày:
- `day_high`, `day_low`, `day_close` — để tính ATR ngày.
- `day_atr` = `atr_wilder(day_high, day_low, day_close, 14)` trên chuỗi nến ngày dựng theo chính lưới này. Dùng `rsi_fvg/indicators.py`, không viết lại. `day_atr` của 13 ngày đầu là `NaN` theo đúng ngữ nghĩa Wilder, và những ngày đó bị loại khỏi mọi đại lượng có chuẩn hoá (nhưng **không** bị loại khỏi ① và ②, vốn không cần ATR).

### 3.3 Luật loại — ba luật

1. **Loại cả ngày nếu bất kỳ slot nào thiếu hoặc có quá ít bar.** Ngưỡng theo **tỉ lệ**, không theo số tuyệt đối: slot 0 chỉ có 3 giờ nên một ngưỡng tuyệt đối chung sẽ hoặc loại oan slot 0 hoặc quá lỏng với năm slot kia. Luật: mỗi slot cần `n >= 0.6 * số bar kỳ vọng` với số bar kỳ vọng = `3h/bar_seconds` cho slot 0 và `4h/bar_seconds` cho slot 1–5. Trên M1 là 108 và 144 bar. Cần thiết vì dữ liệu thật cho **p05 của slot 0 = 1 bar** — có ngày lễ slot 0 gần như rỗng, và một cây H4 dựng từ một bar M1 có `high == low`, làm "kill hai đầu" thành vô nghĩa và làm phân vị excursion bùng nổ.
2. **Loại hai ngày chuyển DST mỗi năm**, nhận diện bằng: khoảng cách lịch giữa `trading_day` này và ngày giao dịch kế tiếp không phải 24 giờ tuyệt đối. Ngày đó có một slot dài 3 hoặc 5 giờ nên range của nó không so được. ~18 ngày trên 2584.
3. **Luật loại áp y nguyên cho lưới thật và mọi lưới null.** Áp một bên thì cỡ mẫu lệch và phép so vô nghĩa. Đây là bài học đã ghi trong docstring `aggregate_cycles`.

Ba luật này được thi hành trong **một hàm duy nhất** mà cả đường thật và đường null gọi, để không thể lệch nhau.

---

## 4. `rsi_fvg/h4_kill.py` — phép đo

### 4.1 Bốn nguyên thuỷ

Với mỗi (ngày, slot) còn sống, quét bar về phía trước tối đa `H_MAX = 1440` **phút thị trường mở** (đếm bar, xem §4.2) và ghi:

| tên | định nghĩa |
|---|---|
| `t_up` | số phút mở cửa từ lúc nến đóng tới bar đầu tiên có `high > nến.high`; `NaN` nếu không có trong `H_MAX` |
| `t_dn` | tương tự với `low < nến.low` |
| `exc_up` | `max(high trong cửa sổ ①) − nến.high`, chỉ định nghĩa khi đầu trên bị kill |
| `exc_dn` | `nến.low − min(low trong cửa sổ ①)`, chỉ định nghĩa khi đầu dưới bị kill |

Cộng hai cột kế toán: `w_bars` (độ dài cửa sổ ① của dòng đó, tính bằng bar) và `crosses_weekend`.

**So sánh ngặt** (`>` và `<`): chạm đúng mốc không tính là kill. Đây là quy ước đã dùng trong `stat_sweep` của `quarter_stats.py`; giữ nhất quán để hai nghiên cứu đọc được cạnh nhau.

### 4.2 Cửa sổ: hai định nghĩa, mỗi cái trả lời một câu khác

**Cửa sổ ① — "tới hết ngày giao dịch", do người dùng chọn.** Định nghĩa **bằng nhãn, không bằng đồng hồ**: với slot `s < 5`, cửa sổ là mọi bar có `trading_day == D` và `slot > s`. Với slot 5, cửa sổ ① rỗng theo định nghĩa (nến đóng đúng lúc ngày kết thúc), nên nó là **trọn ngày giao dịch kế tiếp có trong dữ liệu**. Người dùng đã được trình bày và duyệt bất đối xứng này.

Định nghĩa bằng nhãn xử lý DST, ngày lễ và cuối tuần miễn phí; định nghĩa bằng đồng hồ thì không.

Độ dài cửa sổ ① theo slot:

```
slot 0 → 20h    slot 2 → 12h    slot 4 →  4h
slot 1 → 16h    slot 3 →  8h    slot 5 → 24h (ngày kế tiếp)
```

Hai cây được hỏi nhận hai cửa sổ dài nhất. Vì vậy ① **một mình không so được giữa các slot**, và mọi bảng in ① phải in độ dài cửa sổ ngay cạnh.

**Cửa sổ ② — horizon chung, tính bằng phút thị trường mở.** Đếm **bar** chứ không đếm đồng hồ treo tường. Lý do: slot 5 của thứ Sáu có cửa sổ ① là ngày thứ Hai; nếu đếm 24 giờ đồng hồ thì rơi hết vào cuối tuần không có bar và cây đó "không bao giờ bị kill" một cách giả tạo. Đếm bar thì cuối tuần và khe nghỉ tự động bị nhảy qua, và sáu slot so được với nhau.

Cửa sổ ① luôn là **một đoạn đầu liên tục** của cùng dãy bar tiến (nến đóng là ranh giới, bar sau đó là bar kế tiếp trong thời gian thị trường). Nên `t_up`/`t_dn` đo một lần là suy ra được cả ① lẫn ②: kill trong ① ⇔ `t_up <= w_bars`. Không quét dữ liệu hai lần.

Horizon báo ra: 60, 120, 240, 480, 720, 1200, 1440 phút mở cửa.

### 4.3 Bảy đại lượng

Mỗi hàm nhận bảng dòng và trả `dict[str, float]`, cùng giao ước với `quarter_stats.STATS`, để bộ chạy null so lưới thật với lưới null một cách đồng nhất mà không cần biết đại lượng đó đo gì.

**① `kill_rate_window`** — đúng đề bài. Từng slot: tỉ lệ kill **cả hai đầu** trong cửa sổ ①, cộng chỉ-đầu-trên, chỉ-đầu-dưới, không đầu nào, `n`, và `window_hours` in kèm. Báo hai lần cho slot 5: có và không có nhóm `crosses_weekend` (~9% dòng slot 5 — cuối tuần chen giữa nên gap mở tuần có thể nhảy qua mốc).

**② `kill_rate_horizon`** — cùng tỉ lệ tại từng horizon chung của §4.2, từng slot. Ở horizon cố định, độ dài cửa sổ không còn là biến gây nhiễu; chỉ còn độ rộng cây.

**③ `kill_rate_standardized`** — kiểm soát độ rộng, và là đại lượng mà luật §10 dùng. Ba bước:
1. `rel_range = (nến.high − nến.low) / day_atr` — không đơn vị, so được xuyên năm và xuyên slot.
2. Chia `rel_range` thành **decile gộp cả sáu slot**. Báo bảng (slot × decile) với `n` từng ô, để ô thưa lộ ra.
3. **Chuẩn hoá trực tiếp**: mỗi slot ra **một** số = trung bình có trọng số của tỉ lệ kill trong từng decile, trọng số là phân phối decile **gộp**. Đọc là: "nếu slot này có cùng phân phối độ rộng như trung bình sáu slot, tỉ lệ kill của nó là bao nhiêu". Decile mà một slot không có quan sát nào bị bỏ khỏi cả tử và mẫu của slot đó, và số decile dùng được được báo ra — một slot chuẩn hoá trên 4/10 decile thì con số của nó không so được với slot chuẩn hoá trên 10/10, và người đọc phải thấy điều đó.

③ tính tại horizon chung 720 phút (12h), không tại cửa sổ ①, vì ① đã không so được giữa các slot.

**④ `kill_order`** — trong nhóm bị kill cả hai đầu: tỉ lệ đầu trên trước, đầu dưới trước, và **cùng một bar**. Ô thứ ba là phần **không xác định được** ở độ phân giải đang dùng, và nó được báo ra chứ không gán về một phía. Engine của repo có quy ước "SL thắng khi trùng bar", nhưng đó là quy ước bảo thủ cho backtest, không phải sự thật để đưa vào thống kê mô tả.

**⑤ `excursion`** — "max range kill" nghĩa thứ nhất: giá đi tiếp bao xa **quá** mốc. Phân vị p50/p75/p90/p95/max của `exc_up` và `exc_dn` trên nhóm bị kill, từng slot, trong cửa sổ ①.

**⑥ `killed_range`** — "max range kill" nghĩa thứ hai: phân vị p50/p75/p90/p95/max của **range của cây** trong nhóm bị kill cả hai đầu, từng slot.

**⑦ `context`** — range median, `rel_range` median, `day_atr` median, `n` từng slot. Không phải phát hiện, nhưng ③ và ⑤ không đọc được nếu thiếu.

### 4.4 Chuẩn hoá đơn vị — ⑤ và ⑥ báo ba dạng

1. **Chia cho `day_atr`** — dạng chính, không đơn vị, so được xuyên 9 năm.
2. **USD tách từng năm** — dạng dùng để đặt SL, vì chỉ năm gần nhất mới liên quan.
3. **USD gộp cả mẫu** — chỉ để tham khảo, và **in kèm cảnh báo** rằng nó bị 2025–2026 chi phối (§2.3b).

Với `max`: in ra nhưng **mỗi lần in phải kèm ghi chú rằng đó là một điểm dữ liệu**. Max trên mẫu 9 năm nói về ngày tin tức tệ nhất từng xảy ra, không nói về tuần sau. p90 là con số đặt SL được; p95 tách theo năm dựa trên ~250 quan sát nên đã lung lay (§9).

---

## 5. Null A — lệch mốc neo

### 5.1 Offset

Dịch cả lưới đi `anchor_offset` giây rồi đo lại toàn bộ. Offset lấy từ **trọn chu kỳ ngày** `[0, 86400)`, snap về bội số của `bar_seconds`, loại lân cận 0 và 86400.

Ba quyết định, đều kế thừa lý lẽ đã viết trong docstring `quarter_stats.make_offsets`:
1. **Snap về bội số `bar_seconds`** — lưới thật có biên trùng bar chính xác; lưới giả rơi giữa nến sẽ bị handicap hình học và lưới thật trông tốt hơn chỉ vì nó căn lề.
2. **Lấy trọn ngày, không phải `[0, 14400)`** — dịch đúng 14400 giây không đổi biên nến mà chỉ **đổi tên slot**, và mọi đại lượng đều theo slot nên phép đổi tên đó là thông tin.
3. **Loại lân cận 0** để lưới giả không trùng lưới thật.

Tái dùng `make_offsets` bằng cách thêm tham số `cycle_seconds: int | None = None`; không truyền thì hàm tra `TIERS[tier]` như cũ và **hành vi hai study Quarterly Theory không đổi một bit**. Thà thêm một tham số còn hơn copy một hàm có ba quyết định được lập luận cẩn thận.

Số mốc khả dụng: gần **1.440** trên M1 sau khi loại lân cận 0 (dư cho 200 lưới null), nhưng chỉ **24** trên H1. Null trên dữ liệu H1 vì vậy yếu; `n_nulls` được báo ra chứ không che, và §11 nhắc lại.

### 5.2 Confound đã biết, và điều Null A không làm được

Khe nghỉ hằng ngày và biên tuần **cố định** ở 17:00 NY (§2.1). Lưới thật căn khít cả hai: slot 0 của nó chứa khe nghỉ nên hẹp một cách cơ học, và biên ngày của nó trùng biên tuần. Lưới lệch thì không.

Nên Null A gần như chắc chắn sẽ nói "lưới thật khác lưới bất kỳ" — nhưng **một phần lý do là cơ học, không phải hành vi**, và Null A một mình **không tách được hai thứ đó**. Đại lượng ③ là thứ tiến gần nhất tới việc tách, vì nó kiểm soát độ rộng; nó vẫn không kiểm soát được phần microstructure của việc mở lại sau khe nghỉ (spread rộng, thanh khoản mỏng, gap qua khe).

Đây là giới hạn nghiêm trọng nhất của nghiên cứu, và nó cùng loại với confound đã ghi ở §8.2 spec Quarterly Theory Phase 1 — lần này còn trực tiếp hơn, vì mốc neo ở đây **là** mốc khe nghỉ, không chỉ trùng nó.

### 5.3 Null B đã bị loại khỏi phạm vi — và cái đã mất

Trong lúc thiết kế có đề xuất **Null B**: giữ nguyên mốc high/low của cây nhưng thay đường giá phía trước bằng đường giá **tương đối** của một ngày giao dịch khác trong ±10 ngày. Null đó trả lời trực tiếp câu "mốc này có gì đặc biệt, hay một mốc rộng tương đương ở đâu cũng bị quét ngần ấy", và nó tách được cơ học khỏi hành vi theo cách Null A không làm được.

**Người dùng đã quyết không làm Null B.** Ghi lại ở đây để không ai — kể cả tôi ở lần đọc sau — tưởng đó là một thiếu sót bị bỏ quên.

Hệ quả bắt buộc: kết luận của nghiên cứu này **không** phân biệt được "mốc H4 phiên Á bị nhắm" với "mốc hẹp thì hay bị quét". Luật §10 vì vậy chỉ còn hai cổng thay vì ba, và báo cáo phải nói ra giới hạn này ở chỗ dễ thấy, không nhét vào cuối.

---

## 6. Cổng dữ liệu

### 6.1 Tự dò timezone của nguồn — cổng CHẶN

`quarters.verify_server_tz` hardcode `SOURCE_TZ = "UTC"` vì epoch của MT5 đã được kiểm là UTC thật. **CSV export từ Trading Station thì theo timezone hiển thị của platform** — người dùng đặt sao nó ra vậy, và spec này không được giả định. Lệch một giờ nghĩa là đo một lưới khác, đúng bài học của `quarters.py` §2.1.

Cổng chặn `detect_source_tz(time, bar_seconds) -> TzDetect`:
- Ứng viên: offset nguyên giờ từ −12 đến +14, cộng các zone có tên `UTC`, `America/New_York`, `Europe/Athens`.
- **Tiêu chí là khe nghỉ hằng ngày, không phải mốc mở tuần.** Điểm của một ứng viên:

  ```
  score = 0.5 · P(bar cuối trước mỗi khe trong ngày rơi vào giờ 16 NY)
        + 0.5 · P(bar đầu sau mỗi khe trong ngày rơi vào giờ 18 NY)
  ```

  Khe nghỉ là 17:00→18:00 NY, nên cách đọc đúng đẩy hai đầu về giờ 16 và giờ 18.

  Chọn tiêu chí này sau khi **đo cả hai** trên 3.299.723 bar M1. Mốc mở tuần cho mẫu 331 khe sạch và chỉ 81% rơi vào giờ kỳ vọng, lại cần cửa sổ hai giờ rộng nên offset lệch ±1h vẫn lọt qua — phân biệt kém. Khe nghỉ hằng ngày cho **2.290** mẫu và phân biệt dứt khoát:

  ```
  đọc đúng   0,8644        lệch −1h  0,0020        lệch +1h  0,0155
                           lệch −2h  0,0094        lệch +2h  0,0181
  ```

- Chấm bằng **tỉ lệ** chứ không bằng mode: mode ẩn mất chuyện một đoạn lịch sử bị lệch, và đó chính là lỗ hổng đã ghi ở §8 mục 5 spec Quarterly Theory Phase 1.
- Đi tiếp **chỉ khi** điểm tốt nhất `>= 0.70` **và** cách ứng viên nhì `>= 0.30`. Ngược lại: **in toàn bộ bảng điểm rồi thoát 1**, không chạy nghiên cứu.

  Ngưỡng 0,70 chứ không phải 0,90 vì cách đọc **đúng** trên dữ liệu thật chỉ đạt 0,8644 — ngày lễ rút ngắn và tuần khởi động muộn ăn vào phần còn lại. Đặt 0,90 là tự chặn chính mình. Biên 0,30 an toàn rộng rãi vì khoảng cách thật giữa đúng và lệch là 0,86 so với 0,02.
- Nếu ứng viên offset nguyên giờ tốt nhất bị **chia đôi giữa hai giờ** (dấu hiệu nguồn có DST — đúng hiện tượng đã gặp với Exness), zone có tên sẽ thắng; cổng in ra rằng nó thắng và thắng vì lý do gì.
- Kết quả dò được in **thật to** trong báo cáo. Một nghiên cứu phụ thuộc giờ treo tường mà không nói nó đã đọc giờ thế nào là một nghiên cứu không kiểm chứng được.

Với dữ liệu MT5 parquet sẵn có, cổng vẫn chạy và phải chọn `UTC` — nếu nó chọn thứ khác thì có gì đã đổi và nghiên cứu phải dừng.

### 6.2 Dialect FXCM cho `csv_loader`

CSV FXCM có cột `DateTime, BidOpen, BidHigh, BidLow, BidClose, AskOpen, …`. `load_csv` hiện chỉ hiểu `open/high/low/close`. Thêm — **thuần thêm** — một bước map `bidopen→open` … `bidclose→close` khi nhận diện được cột Bid. Dùng **Bid** theo thông lệ repo (`Bars` docstring: "Prices are BID"). Nếu có cột Ask thì tính spread trung vị và ghi vào báo cáo, để §11 lượng hoá được thiên lệch một phía.

### 6.3 Nguồn dữ liệu — trạng thái thật

FXCM **không** phát lịch sử vàng miễn phí. Đã kiểm trực tiếp: `candledata.fxcorporate.com` còn sống và trả về `EURUSD/GBPUSD/USDJPY` cho `m1` và `H1`, nhưng `XAUUSD`, `XAGUSD`, `US30`, `SPX500`, `USOil` đều 404, và `H2/H3/H4/H8/D1/W1` cũng 404. Danh sách chính thức của dịch vụ là 21 cặp FX, không có vàng. `api-demo.fxcm.com` và `api.fxcm.com` **không resolve** (REST API đã chết), và `forexconnect` không có wheel cho Python 3.13 trên máy này.

Đường đã chọn: **người dùng export CSV từ Trading Station** (m1 cho độ phân giải, H1 cho lịch sử dài) và đặt vào `data/`. Trong lúc chờ, nghiên cứu chạy được ngay trên `XAUUSDc` M1 của Exness làm proxy — khe nghỉ của Exness đã đo được là trùng khít 17:00–18:00 NY như FXCM, nên cấu trúc phiên giống nhau và chỉ giá lệch cỡ vài cent. Script nhận cả hai nguồn qua một cờ dòng lệnh; đổi nguồn không sửa code.

Mọi kết quả **phải ghi rõ nguồn nào đã sinh ra nó**. Trộn hai nguồn trong một báo cáo mà không ghi nhãn là cách chắc chắn nhất để sau này không ai biết con số nào tin được.

---

## 7. File

| file | trạng thái |
|---|---|
| `rsi_fvg/h4_grid.py` | mới — §3 |
| `rsi_fvg/h4_kill.py` | mới — §4, §5 |
| `scripts/study_h4_kill.py` | mới — CLI, cổng chặn §6.1, báo cáo |
| `tests/test_h4_grid.py` | mới — §8 |
| `tests/test_h4_kill.py` | mới — §8 |
| `rsi_fvg/data/csv_loader.py` | **thêm** dialect FXCM (§6.2); hành vi cũ không đổi |
| `rsi_fvg/quarter_stats.py` | **thêm** `cycle_seconds` tuỳ chọn cho `make_offsets` (§5.1); hành vi cũ không đổi |

Kết quả: `results/h4_kill/<ngày>/`
- `rows.csv` — một dòng mỗi (ngày, slot) với đủ bốn nguyên thuỷ, `w_bars`, `crosses_weekend`, `rel_range`. Để người dùng tự cắt lát trong Excel mà không cần chạy lại.
- `stats.csv` — bảng thật vs null như `study_quarters.py` đang làm.
- `summary.md` — báo cáo đọc được, gồm kết quả cổng dò timezone, bảng ①–⑦, và phán quyết §10 **tính bằng máy**, không để người đọc tự kết luận.

CLI: `--symbol --tf --source {mt5,csv} --csv <path> --shifts --seed --out-dir`. Mã thoát: 0 chạy xong, 1 cổng timezone fail, 2 không đủ dữ liệu.

Hai thay đổi vào file có sẵn đều thuần thêm, và **toàn bộ 304 test hiện có phải xanh** sau khi làm — đặc biệt `tests/test_golden_grid.py`, vốn là cái pin hành vi của optimizer.

---

## 8. Test

Không phải danh sách đầy đủ; đây là những chỗ mà sai thì cả nghiên cứu sai và test thường không bắt:

1. **Lưới khớp mốc neo.** Trên dữ liệu thật: slot 1–4 có đúng `4h/bar_seconds` bar ở phần lớn ngày, slot 0 ít hơn đúng một giờ.
2. **DST hai chiều.** Chuỗi tổng hợp bắc qua cả hai biên DST New York; xác nhận `trading_day` là nửa đêm NY (không phải 23:00 hay 01:00) và ngày chuyển bị loại theo §3.3.2.
3. **Cửa sổ ① của slot 5 nhảy qua cuối tuần.** Chuỗi có thứ Sáu và thứ Hai; cửa sổ ① của slot 5 thứ Sáu phải là ngày thứ Hai và `crosses_weekend` phải bật.
4. **`t_up`/`t_dn` đếm phút mở cửa, không đếm đồng hồ.** Chuỗi có khe nghỉ ở giữa; xác nhận khe không được tính vào.
5. **So sánh ngặt.** Bar chạm đúng `nến.high` không tính là kill; bar vượt một tick thì tính.
6. **Chuẩn hoá trực tiếp ③.** Bảng dựng tay có phân phối độ rộng lệch giữa hai slot nhưng tỉ lệ kill trong từng decile bằng nhau → tỉ lệ chuẩn hoá của hai slot phải **bằng nhau** trong khi tỉ lệ thô khác nhau. Đây là test quan trọng nhất của cả suite: nó là bằng chứng rằng đại lượng dùng cho luật §10 thật sự kiểm soát được cái nó nói là kiểm soát.
7. **Luật loại áp đối xứng.** Cùng một hàm loại được gọi trên đường thật và đường null (test bằng cách gọi và so, không bằng cách đọc code).
8. **Cổng dò timezone.** Chuỗi UTC → dò ra `UTC`; cùng chuỗi dịch đi 3 giờ → dò ra offset +3; chuỗi ngẫu nhiên không có cấu trúc tuần → cổng **fail**.
9. **Bất biến tiền tố** cho mọi thứ có "tương lai": `measure(bars[:k])` trên các dòng còn đủ cửa sổ phải khớp `measure(bars)`. Dòng có cửa sổ bị cắt ngắn ở mép dữ liệu phải bị **loại**, không được báo là "không bị kill" — đây là look-ahead ngược, và nó sẽ làm tỉ lệ kill thấp giả tạo ở cuối mẫu.
10. **`make_offsets` không đổi hành vi cũ**: gọi không có `cycle_seconds` cho kết quả y hệt trước.

---

## 9. Cỡ mẫu

| | số dòng |
|---|---|
| ngày giao dịch có dữ liệu | 2.584 |
| ngày đủ sáu slot | 2.385 |
| dòng (ngày × slot) sau luật loại | ~14.300 |
| mỗi slot | ~2.385 |
| mỗi slot mỗi năm | ~250 |

Tỉ lệ thì thừa mẫu: sai số chuẩn của một tỉ lệ trên 2.385 quan sát là ~1 điểm phần trăm. Nhưng **p95 và max của ⑤/⑥ tách theo năm chỉ dựa trên ~250 quan sát**, và số đó còn nhỏ hơn nữa sau khi lọc "chỉ nhóm bị kill". Báo `n` thật ở mọi ô; không ước lượng trước.

---

## 10. Luật kết luận — chốt TRƯỚC khi chạy

Phần này tồn tại để ngăn cả tôi và người dùng hợp lý hoá kết quả sau khi đã thấy số.

> **Một slot được gọi là ĐẶC BIỆT khi và chỉ khi đạt cả hai cổng:**
> **(a)** tỉ lệ kill **chuẩn hoá theo độ rộng** (③, horizon 720 phút) của nó **cao hơn cả bốn slot đối chứng**; và
> **(b)** giá trị đó **vượt percentile 95** của phân phối Null A.
>
> **Phase 2 được phép viết spec khi và chỉ khi slot 0 hoặc slot 5 đạt cả hai cổng.**

①, ②, ④, ⑤, ⑥, ⑦ là mô tả và trả lời trực tiếp câu hỏi của người dùng. Một mình chúng **không** mở cổng Phase 2, kể cả khi con số trông lớn. Riêng ① — tỉ lệ kill thô — **không bao giờ** là căn cứ kết luận, vì §4.2 đã cho thấy nó không so được giữa các slot.

**Multiple testing, nói thẳng:** luật chạy 2 slot × 2 cổng ở mức 95%, nên sai số toàn họ rộng hơn 5%. Ngưỡng dễ này được chọn có ý thức vì Phase 1 là bước khám phá. **Không được siết hay nới sau khi thấy số.**

**Cổng (a) chưa từng bị Null B kiểm.** Vì §5.3, kể cả khi cả hai cổng đạt, kết luận đúng là "lưới 17:00 NY khác lưới bất kỳ, sau khi kiểm soát độ rộng" — **không** phải "mốc H4 phiên Á bị nhắm". Câu sau cần Null B, và Null B không nằm trong phạm vi. Spec Phase 2, nếu được viết, phải mở đầu bằng việc chạy Null B.

---

## 11. Giới hạn đã biết

1. **Không tách được cơ học khỏi hành vi.** Null B bị loại khỏi phạm vi (§5.3), nên nghiên cứu này đo "lưới thật có khác lưới lệch không", chứ không đo "mốc high/low này có bị nhắm không". Đây là giới hạn nghiêm trọng nhất.
2. **Mốc neo trùng khe nghỉ và biên tuần** (§5.2). Hiệu ứng của lưới thật có thể đến từ microstructure mở lại sau nghỉ chứ không từ cấu trúc phiên. ③ kiểm soát độ rộng nhưng không kiểm soát điều này.
3. **Thứ tự hai đầu không xác định được khi cùng một bar.** Báo ra thành ô riêng (④), không gán bừa. Trên H1 phần "cùng bar" sẽ lớn tới mức ④ vô dụng.
4. **Giá là Bid, không cộng spread.** Một stop mua khớp ở Ask, nên **tỉ lệ kill đầu trên thực tế cao hơn** con số báo, và thiên lệch này **một phía**. Lượng hoá bằng spread trung vị đo từ dữ liệu (§6.2), nhưng không sửa số.
5. **Đo hiệp hội, không đo lợi nhuận.** Tỉ lệ kill cao **không** đảm bảo có strategy sinh lời. Nghiên cứu này không tính cost và không tạo `Signal` nào.
6. **Nguồn có thể là proxy.** Nếu CSV FXCM ngắn, phần lịch sử dài dựa vào Exness (§6.3). Mọi bảng ghi rõ nguồn.
7. **Null yếu trên H1**: chỉ 24 mốc neo khả dụng (§5.1). Percentile tính trên 24 điểm thì thô; `n_nulls` được báo ra.
8. **Một symbol, một khoảng thời gian.** Không có bằng chứng nào về việc kết quả chuyển sang symbol khác.
9. **Đơn vị USD gộp cả mẫu bị 2025–2026 chi phối** (§2.3b). Chỉ dùng dạng chia `day_atr` hoặc dạng tách theo năm để quyết định bất cứ điều gì.
10. **Dữ liệu XAUUSDc có 163 bar Thứ Bảy lạc** (2018–2021, đúng 19:00 hoặc 20:00 NY, khoảng một bar mỗi tuần). Thị trường không mở Thứ Bảy, nên đây là dị thường của feed. Hệ quả đã kiểm: chúng chia 22% khe cuối tuần thành 27h + 22h thay vì một khe 49h — nên **mọi phép đếm khe cuối tuần trên bộ dữ liệu này đều không đáng tin**, và đó là lý do thứ hai để cổng §6.1 dùng khe nghỉ hằng ngày. Với lưới H4, mỗi bar lạc sinh ra một "ngày giao dịch" Thứ Bảy chỉ có 1–2 bar ở slot 0, và luật loại §3.3.1 xoá nó tự động. Nhưng nó nằm **giữa** thứ Sáu và ngày giao dịch thật kế tiếp, nên định nghĩa "ngày kế tiếp" của cửa sổ ① slot 5 phải là **ngày giao dịch còn sống kế tiếp**, không phải ngày lịch kế tiếp — nếu không, 163 dòng slot 5 của thứ Sáu trong 2018–2021 sẽ bị xoá oan, và đó là một phép xoá thiên lệch theo thời gian.
