# Quarterly Theory (ICT) — Nghiên cứu tiền đề — Design Spec

**Ngày:** 2026-09-09
**Trạng thái:** Đã duyệt thiết kế
**Phase:** 1 của 2. Phase 2 (strategy vào/ra) là spec riêng và **chỉ được viết nếu Phase 1 đạt luật §7**.
**Phạm vi:** ba file mới — `rsi_fvg/quarters.py`, `scripts/study_quarters.py`, `tests/test_quarters.py`. **Không** sửa engine, **không** sửa optimizer, **không** thêm strategy hay adapter, **không** sinh tín hiệu nào.

**Nguồn lý thuyết:** Jevaunie Daye (@traderdaye), phát triển từ ICT. Xem `2026-09-08-quarterly-theory-ict-indicator-design.md` §2 cho định nghĩa đầy đủ ba tầng, Defining Range và True Open — spec này không nhắc lại.

---

## 1. Mục tiêu

Trả lời **một câu duy nhất**: lưới thời gian của Quarterly Theory có cấu trúc thật trên XAUUSDc, hay cái ta nhìn thấy chỉ là hình học của việc chia một chuỗi giá thành bốn phần?

Câu hỏi này đứng trước mọi câu hỏi về luật vào lệnh. Nếu Q2 không thực sự sweep range Q1 nhiều hơn một lưới neo ở giờ bất kỳ, thì không có gì để khai thác và mọi strategy dựng trên nó là khớp nhiễu.

Không nằm trong phạm vi: luật vào/ra, backtest P&L, tầng micro 22.5m / weekly / monthly / yearly / nano, và bất kỳ khuyến nghị giao dịch nào.

---

## 2. Vấn đề chặn đường: dữ liệu đang sai giờ

`Bars.time` là epoch seconds, nhưng loader **gán nhãn đồng hồ server của broker là UTC mà không convert** (README, mục "Timestamps"). Exness chạy EET/EEST (UTC+2/+3). README kết luận việc gán nhãn sai này vô hại vì "nothing in the backtest depends on wall-clock time — there is no session filter".

**Kết luận đó đúng với RSI2 và RSI-FVG, và sai hoàn toàn với Quarterly Theory.** Mọi biên quarter là một mốc giờ treo tường New York. Lệch một giờ nghĩa là backtest một lý thuyết khác.

Và lệch không phải hằng số. DST của Mỹ bắt đầu Chủ nhật thứ 2 tháng 3, của EU Chủ nhật cuối tháng 3 ⇒ khoảng **3 tuần** offset là 6 giờ chứ không phải 7. DST Mỹ kết thúc Chủ nhật đầu tháng 11, EU Chủ nhật cuối tháng 10 ⇒ khoảng **1 tuần** offset là 8. Trừ cứng −7 sẽ sai **~4 tuần mỗi năm**.

Cách đúng: epoch → naive datetime → gán `Europe/Athens` → convert `America/New_York`. `zoneinfo`/`pandas` xử lý cả hai chế độ DST.

"Server Exness = EET" là **giả định lấy từ README, chưa từng kiểm**. §3.2 kiểm nó bằng dữ liệu, và nghiên cứu không được chạy nếu nó fail.

---

## 3. `rsi_fvg/quarters.py`

Hàm thuần, không I/O, không state. Đây là module Phase 2 sẽ dùng lại nguyên vẹn.

### 3.1 `server_to_ny(epoch: np.ndarray) -> pd.DatetimeIndex`

`pd.to_datetime(epoch, unit="s")` → `.tz_localize("Europe/Athens")` → `.tz_convert("America/New_York")`.

Chính sách cho giờ ambiguous (giờ lặp khi fall-back) và nonexistent (giờ mất khi spring-forward): **raise, không vá**. DST của EU đổi lúc 03:00 Chủ nhật, nằm giữa lúc thị trường đóng, nên lẽ ra không có bar nào rơi vào đó. Nếu nó raise thật, đó là **phát hiện về dữ liệu** cần điều tra, không phải lỗi cần bọc `try`. Bọc lại sẽ che mất đúng thứ đáng biết.

### 3.2 `verify_server_tz(bars: Bars) -> TzCheck` — cổng chặn, chạy trước mọi thứ

Hai kiểm định độc lập, đều suy ra từ dữ liệu:

**Kiểm định 1 — mở cửa đầu tuần.** Tìm mọi khe cuối tuần (`diff(time) > 24*3600`). Với mỗi khe, lấy giờ NY của bar đầu tiên sau khe. Vàng/forex mở **Chủ nhật 17:00–18:00 New York**. Giá trị mode phải là **Chủ nhật, trong khoảng 17:00–18:00 NY**. Ra 16:00 hay 19:00 ⇒ offset lệch một giờ ⇒ fail.

**Kiểm định 2 — nghỉ hằng ngày.** XAUUSD của Exness có khe bảo trì 00:00–01:00 EET. Convert đúng thì khe đó phải xuất hiện lặp lại ở **17:00–18:00 NY mỗi ngày trong tuần**. Tìm khe trong ngày (`diff(time)` lớn hơn bar interval nhưng nhỏ hơn 24h) và kiểm phân phối giờ NY của chúng.

Trả về dataclass: giá trị mode của từng kiểm định, số đếm, và một cờ `ok`. `scripts/study_quarters.py` **thoát với mã khác 0 và không chạy nghiên cứu** khi `ok` là false.

**Ghi chú đáng lưu ý cho §8:** khe nghỉ hằng ngày kết thúc **18:00 NY**, trùng đúng mốc neo chu kỳ ngày của Quarterly Theory. Đây vừa là kiểm định tốt, vừa là một confound — xem §8.

### 3.3 `label_quarters(ny: pd.DatetimeIndex, tier: str, anchor_offset: int = 0)`

Trả về `(cycle_id, q_index)`. Cùng số học với indicator Pine đã viết (`pine/quarterly_theory_ict.pine` §3 của spec kia): `hShift = (hour + 6) % 24`.

| `tier` | Độ dài quarter | `q_index` | `cycle_id` |
|---|---|---|---|
| `"session"` | 21600 s | `iSess` = `hShift // 6` | `trading_day` |
| `"q90"` | 5400 s | `iQ90` = `secInSess // 5400` | `(trading_day, iSess)` |

`trading_day` = ngày dương lịch NY của mốc 18:00 khởi đầu chu kỳ: nếu giờ NY ≥ 18 thì là ngày của chính bar đó, ngược lại là ngày trước. Định nghĩa theo **ngày dương lịch** chứ không theo số giây tích luỹ, để an toàn với DST.

`anchor_offset` (giây) dịch cả lưới: tương đương gọi hàm với `ny - Timedelta(seconds=anchor_offset)`. Tham số này tồn tại **chỉ để mô hình null dùng** (§4.1), và nó là lý do phần gán nhãn phải là hàm thuần nhận tham số thay vì hằng số hardcode.

---

## 4. `scripts/study_quarters.py`

CLI: `python scripts/study_quarters.py --tf M5 --shifts 200 --seed 20260909`

Nạp parquet qua loader hiện có (`rsi_fvg/data/`), chạy §3.2, rồi §4.2 trên lưới thật và `--shifts` lưới giả.

### 4.1 Mô hình null — và cái bẫy phải tránh

Lưới thật có biên trùng bar M5 chính xác: 18:00, 19:30, 21:00 đều là bội của 5 phút. Nếu neo lệch ngẫu nhiên, biên lưới giả rơi **giữa nến**, nên lưới giả bị handicap về hình học và lưới thật trông tốt hơn **chỉ vì nó căn lề bar**. Đó là bias nghiêng về phía lý thuyết, và nó sẽ làm nghiên cứu tự nói dối.

**Xử lý: snap mọi `anchor_offset` về bội số của bar interval** (300 s với M5), để lưới giả và lưới thật cùng điều kiện căn lề.

Offset lấy từ `[0, 4L)` — trọn một chu kỳ, không phải `[0, L)` — vì dịch đúng `L` không đổi biên mà chỉ **đổi tên** quarter (Q2 cũ thành Q1), và các phép đo ①②③⑥ đều phụ thuộc chỉ số quarter nên phép đổi tên đó là thông tin. Loại lân cận 0: bỏ offset `< 600 s` và `> 4L − 600 s`. Sinh bằng `np.random.default_rng(seed)`, seed cố định để tái lập.

### 4.2 Sáu phép đo

Mỗi phép chạy trên lưới thật và trên `--shifts` lưới giả. Báo giá trị thật, mean/p05/p50/p95 của null, và **percentile của giá trị thật trong phân phối null**.

Trong một chu kỳ, `Q1hi`/`Q1lo` là high/low của quarter index 0; `open` của một quarter là open của bar đầu tiên trong nó, `close` là close của bar cuối.

**Chu kỳ không đủ dữ liệu bị loại.** Ngày lễ, khe nghỉ hằng ngày và khoảng trống dữ liệu có thể để một quarter không có bar nào, hoặc quá ít bar để high/low có nghĩa. Luật: **loại cả chu kỳ nếu bất kỳ quarter nào trong bốn có ít hơn 3 bar.** Áp dụng y nguyên cho lưới thật và mọi lưới giả — nếu chỉ áp cho một bên thì cỡ mẫu lệch và so sánh vô nghĩa. Báo số chu kỳ bị loại của lưới thật trong `summary.md`.

**Ràng buộc hoà.** Khi giá bằng đúng mốc so sánh (`close == TO` ở ⑤, `Q2.close == Q1hi` ở ⑥), quan sát đó **bị loại**, không gán về một phía. Báo số quan sát hoà. Với vàng 3 chữ số thập phân, hoà là hiếm nhưng không phải không có.

| | Thống kê | Lý thuyết dự đoán |
|---|---|---|
| ① sweep | tỷ lệ chu kỳ có `Q2.high > Q1hi` **hoặc** `Q2.low < Q1lo` | cao |
| ② Q1 hẹp | `mean(high − low)` theo từng `q_index`; kèm tỷ lệ Q1 / mean(cả bốn) | Q1 nhỏ nhất |
| ③ Q3 giãn | `mean(abs(close − open))` theo từng `q_index` | Q3 lớn nhất |
| ④ Q1⇒Q2 | Spearman(range Q1, range Q2) qua các chu kỳ — `pandas.corr(method="spearman")`, không cần scipy | **âm** |
| ⑤ True Open | `TO` = open bar đầu Q2. `side_a` = sign(open bar đầu Q3 − TO), `side_b` = sign(close bar cuối Q4 − TO). Thống kê = P(`side_a == side_b`) | ≠ 0.5 theo hướng nào cũng là thông tin |
| ⑥ reclaim→Q3 | xem dưới | > 0.5 |

**⑥ định nghĩa chính xác** — đây là phép đo quyết định §7:

- *Sweep lên rồi reclaim*: `Q2.high > Q1hi` **và** `Q2.close <= Q1hi`. Với tập con này, đo `P(Q3.close < Q3.open)`.
- *Sweep xuống rồi reclaim*: `Q2.low < Q1lo` **và** `Q2.close >= Q1lo`. Với tập con này, đo `P(Q3.close > Q3.open)`.
- **Pooled** (chuẩn hoá hướng): gộp hai tập con, đo `P(Q3 đi ngược hướng sweep)`. Đây là con số đầu bảng.

Báo `n` của mọi tập con điều kiện — chúng có thể nhỏ, và một percentile đẹp trên `n` nhỏ không có nghĩa.

### 4.3 Kết quả

Ghi vào `results/quarters_study/<YYYY-MM-DD>/`:

- `stats.csv` — một dòng mỗi `(tier, claim, quantity)`: `real`, `null_mean`, `null_p05`, `null_p50`, `null_p95`, `real_percentile`, `n`.
- `summary.md` — bảng đọc được, cộng **phán quyết §7 tính bằng máy** (không phải do người đọc tự kết luận).

---

## 5. `tests/test_quarters.py`

Khác hẳn phần Pine của Phase trước: **đây là code test được thật**, hàm thuần, `pytest` chạy được. TDD áp dụng đúng nghĩa.

1. **Bảng mốc giờ NY → chỉ số quarter.** Dùng lại bảng đã kiểm tay khi làm indicator Pine (spec kia §8 và plan Task 1): 18:00→(0,0), 19:30→(0,1), 23:59→(0,3), 00:00→(1,0), 01:30→(1,1), 06:00→(2,0), 07:30→(2,1), 12:00→(3,0), 13:30→(3,1), 17:59→(3,3).
2. **DST lệch EU/Mỹ.** Một timestamp ngày **2026-03-10** (Mỹ đã vào DST từ 08/03, EU chưa tới 29/03): offset server→NY phải là **6 giờ**, không phải 7. Và một timestamp ngày 2026-10-28 (EU đã ra DST từ 25/10, Mỹ chưa tới 01/11): offset phải là **8**.
3. **`trading_day` qua nửa đêm — chỗ dễ cài sai nhất.** Bar lúc 23:00 NY ngày `D` và bar lúc 01:00 NY ngày `D+1` phải cho **cùng một `trading_day` = `D`**, vì cả hai thuộc chu kỳ khởi đầu 18:00 ngày `D`. Bar 23:00 lấy ngày của chính nó (giờ ≥ 18); bar 01:00 lấy ngày trước (giờ < 18). Cùng chu kỳ, `q_index` khác nhau: 0 và 1. Test cả `trading_day` bằng nhau **và** `q_index` khác nhau — chỉ test một trong hai sẽ không bắt được lỗi lệch ngày.
4. **`anchor_offset` dịch biên đúng lượng truyền vào.** Gán nhãn với `offset = 5400` phải cho `q_index` bằng đúng nhãn của `offset = 0` dịch đi một quarter ở tầng q90.
5. **`server_to_ny` raise** trên timestamp nonexistent và ambiguous tổng hợp (không lấy từ dữ liệu thật).
6. **`verify_server_tz`** trên dữ liệu tổng hợp: một chuỗi có khe cuối tuần đặt đúng chỗ ⇒ `ok=True`; cùng chuỗi dịch đi 1 giờ ⇒ `ok=False`.
7. **Snap offset.** Mọi offset sinh ra trong §4.1 phải là bội của bar interval và nằm ngoài lân cận 0.

---

## 6. Cỡ mẫu

Dữ liệu M5 dùng được từ 2017-04-27 (README, sau khi loader trim) đến nay: khoảng **9,4 năm**.

| Tầng | Chu kỳ | Số chu kỳ ước tính |
|---|---|---|
| session | ngày giao dịch 18:00→18:00 | ~2.450 |
| q90 | một session 6h | ~9.800 |

Tập con điều kiện của ⑥ sẽ nhỏ hơn — báo `n` thật trong kết quả, không ước lượng trước.

---

## 7. Luật kết luận — chốt TRƯỚC khi chạy

Phần này tồn tại để ngăn cả tôi và bạn hợp lý hoá kết quả sau khi đã thấy số.

> **Phase 2 được phép viết spec khi và chỉ khi: thống kê ⑥ pooled nằm ngoài percentile 95 của phân phối null ở ít nhất một trong hai tầng.**

①–⑤ là mô tả và bằng chứng hỗ trợ. Một mình chúng **không** mở cổng Phase 2, kể cả khi đẹp.

**Nói thẳng về multiple testing:** luật này chạy 2 kiểm định (hai tầng) ở mức 95%, nên sai số toàn họ khoảng **10%**, không phải 5%. Đây là ngưỡng dễ, chọn có ý thức vì Phase 1 là bước khám phá và vì backtest của Phase 2 là bộ lọc thứ hai — một edge lọt qua đây mà không sống nổi qua spread sẽ chết ở đó. Không được siết ngưỡng sau khi thấy số, và cũng không được nới.

---

## 8. Giới hạn đã biết

1. **Đo hiệp hội, không đo lợi nhuận.** ⑥ có percentile cao **không** đảm bảo strategy có lãi. Spread XAUUSDc trong `config/default.yaml` là 260 points = 0,26 USD; một edge nhỏ hơn spread là vô dụng dù thống kê có ý nghĩa đến đâu. Nghiên cứu này **không** tính cost.
2. **Confound của mốc 18:00.** §3.2 kiểm định 2 cho thấy khe nghỉ hằng ngày của broker kết thúc đúng 18:00 NY — trùng mốc neo chu kỳ ngày. Nếu lưới thật hơn lưới giả ở tầng session, một phần hoặc toàn bộ hiệu ứng có thể đến từ **microstructure của việc mở lại sau nghỉ** (spread rộng, thanh khoản mỏng, gap) chứ không từ "algorithmic delivery" mà lý thuyết mô tả. Nghiên cứu này không tách được hai nguyên nhân đó. Tầng q90 ít bị confound này hơn vì chỉ 1 trong 16 biên mỗi ngày trùng mốc mở lại.
3. **Null model kiểm đúng một điều hẹp:** "lưới neo 18:00 có đặc biệt so với lưới neo lệch". Nó **không** kiểm "giá có dự báo được".
4. **Một symbol, một broker, một khoảng thời gian.** Không có bằng chứng nào về việc kết quả chuyển sang symbol khác hay broker khác.
5. **Giả định EET chỉ được kiểm ở hiện tại.** §3.2 kiểm offset trên toàn bộ dữ liệu, nhưng nếu broker từng **đổi timezone server** trong 9 năm lịch sử thì kiểm định mode vẫn pass trong khi một đoạn dữ liệu bị lệch. Kiểm định 1 báo phân phối chứ không chỉ mode, nên bất thường sẽ lộ ra — nhưng không có cơ chế tự động phát hiện thời điểm đổi.
6. **Tầng micro 22.5m bị loại** khỏi nghiên cứu: 64 quarter mỗi ngày trên M1, mỗi quarter vài nến, nhiễu áp đảo.
7. **Không sinh tín hiệu, không chạy engine.** Nghiên cứu này không nạp `rsi_fvg/backtest/` và không tạo `Signal` nào.
