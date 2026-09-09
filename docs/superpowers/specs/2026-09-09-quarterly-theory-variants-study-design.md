# Quarterly Theory (ICT) — Nghiên cứu biến thể ⑥ — Design Spec

**Ngày:** 2026-09-09
**Trạng thái:** Đã duyệt thiết kế
**Phase:** 1b. Đây **không phải Phase 2**. Xem §1.2.
**Kế thừa:** `2026-09-09-quarterly-theory-premise-study-design.md` (lớp thời gian §3, bảng chu kỳ §4.2, mô hình null §4.1, luật loại chu kỳ và luật hoà §4.2). Spec này không nhắc lại các định nghĩa đó.

**Phạm vi:** Tạo `rsi_fvg/quarter_variants.py`, `scripts/study_quarter_variants.py`, `tests/test_quarter_variants.py`. Sửa **một chỗ** trong `rsi_fvg/quarter_stats.py`: thêm tham số `stats` cho `run_grid`/`run_null`, mặc định là `STATS` hiện có nên hành vi Phase 1 **không đổi một bit**. Không chạm `rsi_fvg/quarters.py`, không chạm `scripts/study_quarters.py`, không chạm engine/optimizer/strategies.

---

## 1. Mục tiêu

### 1.1 Câu hỏi

Nghiên cứu Phase 1 đo **một** cách hình thức hoá ý tưởng sweep-reclaim và nó thất bại:

| Tầng | ⑥ pooled thật | Null mean | Percentile | n |
|---|---|---|---|---|
| session | 0,4730 | 0,5077 | 3,0 | 890 |
| q90 | 0,4847 | 0,4985 | 2,9 | 3.988 |

Câu hỏi của Phase 1b: **còn cách hình thức hoá nào khác của cùng ý tưởng đứng được không?** Năm biến thể, §2.

### 1.2 Tại sao spec này không vi phạm §7 của Phase 1

Luật §7 của Phase 1, nguyên văn: *"Phase 2 được phép viết spec khi và chỉ khi: thống kê ⑥ pooled nằm ngoài percentile 95 của phân phối null ở ít nhất một trong hai tầng."* Nó chặn việc **viết spec strategy**. Nó không cấm đo thêm.

Spec này chỉ đo. Nó **không** định nghĩa luật vào lệnh, **không** sinh `Signal`, **không** nạp engine. Nếu Phase 1b cũng fail thì Phase 2 vẫn bị chặn — và §6 biến điều đó thành kết luận đóng, không phải một vòng thử nữa.

### 1.3 Nguy cơ thật của việc làm điều này

Thử biến thể tới khi có cái pass **chính là p-hacking**. Với K biến thể ở mức 95%, xác suất ít nhất một cái pass do may là ~1−0,95^K: K=10 cho 40%. Phần lớn thiết kế của spec này (§3, §4, §5, §6) tồn tại **chỉ để** chống điều đó, và số biến thể bị **khoá ở 5** trước khi chạy dòng code nào.

---

## 2. Năm biến thể

**Trigger chung, y nguyên ⑥ của Phase 1 §4.2** — mọi biến thể dùng đúng nó, để chúng là *cách hình thức hoá khác nhau* chứ không phải vặn tham số:

```
swept_up = (q2_high > q1_high) AND (q2_close < q1_high)
swept_dn = (q2_low  < q1_low ) AND (q2_close > q1_low )
both     = swept_up AND swept_dn        -> LOẠI khỏi mọi biến thể
```

Luật loại chu kỳ thiếu bar (Phase 1 §4.2, `min_bars = 3`) và luật loại hoà áp y nguyên, cho lưới thật và mọi lưới null.

| | Định nghĩa | Thống kê |
|---|---|---|
| **V1** | Trigger chung, không thêm gì | P(Q3 đi **cùng** hướng sweep) |
| **V2** | Trigger chung **và** `range(Q1) <` median trượt của `range(Q1)` 20 chu kỳ **trước đó** | P(Q3 đi ngược) |
| **V3** | Reclaim quyết đoán: thay `q2_close` vượt biên bằng `q2_close` vượt **trung điểm** `(q1_high+q1_low)/2` | P(Q3 đi ngược) |
| **V4** | Trigger chung, đổi **chân trời đo** | P(`q4_close − q3_open` đi ngược hướng sweep) |
| **V5** | Trigger chung **và** đầu Q3 ở phía True Open khớp hướng kỳ vọng: sweep lên cần `q3_open > q2_open`, sweep xuống cần `q3_open < q2_open` | P(Q3 đi ngược) |

**Lý do từng biến thể, không phải ngẫu nhiên:**
- V1 — số Phase 1 nói Q3 đi *cùng* hướng sweep 52,7% số lần. Xem §7 về việc V1 **không** phải phát hiện.
- V2 — chính phát biểu ④ của lý thuyết: Q1 hẹp báo Q2 giãn, nên manipulation "thật" hơn.
- V3 — ICT nhấn *displacement*; "đóng lại trong range" hiện tại nhận cả một cú reclaim sát biên.
- V4 — hai profile AMDX và XAMD dịch vai trò các quarter (spec indicator §2.2), nên payoff hướng có thể không gói trong Q3.
- V5 — §2.4 True Open, kết hợp hai yếu tố được nhắc nhiều nhất của lý thuyết.

**Chi tiết bắt buộc, để cài không lệch:**
- **V2 không được lookahead.** Median là **trượt trên 20 chu kỳ trước đó**, không phải tercile toàn cục. Chu kỳ nào chưa có đủ 20 chu kỳ trước thì **loại**. So sánh là `<` chặt; `range(Q1)` bằng đúng median là hoà nên **loại**, y như mọi luật hoà khác.
- **V3 giữ nguyên luật loại `both`.** Điều kiện của V3 khiến `up` và `dn` không thể cùng đúng (một giá đóng không thể vừa dưới vừa trên trung điểm), nhưng chu kỳ **sweep cả hai biên** vẫn bị loại như mọi biến thể khác. Không đổi luật loại giữa các biến thể, nếu không chúng mất tính so sánh được.
- **Hoà theo từng biến thể:** V1/V2/V3/V5 loại khi `q3_close == q3_open`; V4 loại khi `q4_close == q3_open`; V5 loại thêm khi `q3_open == q2_open`.

---

## 3. Chia dữ liệu screen/confirm — 50/50 theo thời gian

Chia **mảng bar** làm hai nửa theo chỉ số ở `len(bars) // 2`, rồi chạy toàn bộ pipeline (gán nhãn → gộp chu kỳ → thống kê) **độc lập trên từng nửa**. Số bar lẻ thì bar dư thuộc **nửa sau**. Chu kỳ nằm vắt qua điểm chia sẽ thiếu bar ở nửa nào cũng vậy và bị luật `min_bars` loại tự nhiên — không cần xử lý riêng.

**Tại sao 50/50 mà không 70/30 như optimizer.** Optimizer dùng 70/30 vì OOS ở đó chỉ là **cổng pass/fail** cho một combo đã chọn. Ở đây **cả hai nửa đều làm việc thật**: nửa đầu phải xếp hạng được bốn biến thể, nửa sau phải có đủ lực để kiểm định. Ước lượng: ~1.994 chu kỳ pooled mỗi nửa ở tầng q90.

Lưới null: **cùng một bộ offset** (cùng seed) áp cho cả hai nửa, để hai nửa so được với nhau.

---

## 4. Hai đường, mỗi đường đúng một kiểm định cuối

**Đường A — V1.** Không qua vòng sàng: nó đã được định trước nên sàng nó là vô nghĩa. Kiểm **trực tiếp** trên nửa sau.

**Đường B — V2, V3, V4, V5.** Sàng cả bốn trên **nửa đầu**, **không tuyên bố gì tại đó** (percentile nửa đầu chỉ để xếp hạng, không phải bằng chứng), lấy cái percentile cao nhất, kiểm **đúng một cái đó** trên nửa sau.

Vòng sàng xếp hạng theo percentile **tầng q90**, cùng tầng với kiểm định cuối. Xếp hạng ở một tầng rồi kiểm ở tầng khác sẽ làm vòng sàng vô nghĩa.

Tổng cộng **2 kiểm định cuối** ⇒ Bonferroni giữ sai số toàn họ 5% với α = **2,5%** mỗi kiểm định.

Nếu hai biến thể ở đường B đồng percentile cao nhất trên nửa đầu, chọn cái có **n lớn hơn**; vẫn đồng thì chọn theo thứ tự V2 → V3 → V4 → V5. Luật tie-break chốt ở đây để không phải quyết sau khi thấy số.

---

## 5. Tầng chính và ngưỡng — con số thật

**Tầng chính: q90.** Phase 1 §8.2 đã kết luận nó ít bị confound mốc 18:00 hơn (chỉ 1 trong 16 biên mỗi ngày trùng mốc broker mở lại, so với 1 trong 4 ở tầng session). Tầng session **chỉ báo mô tả, không tuyên bố gì** — nó không tham gia luật §6, nên không tính vào số kiểm định.

**Ngưỡng, tính ra số nguyên.** Với N lưới null, p-value một phía đạt được là `(k+1)/(N+1)`, k = số null có giá trị ≥ giá trị thật. Tầng q90 có **69** lưới null (Phase 1: chu kỳ 21600 s ÷ bar 300 s = 72 mốc, trừ lân cận 0 còn 69). α ≤ 2,5% đòi:

```
(k+1)/70 <= 0,025  =>  k+1 <= 1,75  =>  k = 0
```

**Giá trị thật phải vượt CẢ 69 lưới null**, tức p = 1/70 = 1,43%.

Đây là bar rất cao, và nó cao vì **độ phân giải null ở q90 thô** — hệ quả của số học 21600/300, không phải lựa chọn. **Hệ quả phải chấp nhận: một hiệu ứng thật nhưng vừa phải sẽ không qua nổi bar này.** Ngưỡng được chốt ở đây và **không được nới sau khi thấy số**, kể cả khi một biến thể ra 68/69.

---

## 6. Luật chốt TRƯỚC khi chạy

> Một đường **pass** khi và chỉ khi giá trị thật của nó trên **nửa sau**, tầng **q90**, **vượt cả 69 lưới null**.

- Hai đường pass **độc lập**. Cả hai pass ⇒ Phase 2 lấy đường có percentile nửa sau cao hơn; đường kia ghi làm kết quả phụ. Đồng nhau ⇒ ưu tiên đường B, vì nó là phát hiện còn đường A chỉ là kiểm định độ ổn định (§7).
- **Không đường nào pass ⇒ Quarterly Theory đóng lại với repo này.** Ghi thành kết luận trong `results/` và trong README, không phải một vòng thử nữa. Không có Phase 1c.
- Pass **vẫn không** nghĩa là có lãi. Nghiên cứu này không tính cost; spread XAUUSDc trong `config/default.yaml` là 260 points = 0,26 USD. Y như Phase 1 §8.1.

---

## 7. Điều đường A KHÔNG chứng minh được

V1 = 1 − ⑥ trên **đúng cùng tập con chu kỳ**. Phép biến đổi đó là đơn điệu giảm, nên `percentile(V1) = 100 − percentile(⑥)` một cách máy móc. Trên toàn dữ liệu V1 sẽ ra ~97 — và **con số đó vô giá trị**, vì ⑥ đã được xem trước khi V1 được nghĩ ra.

Giá trị duy nhất của đường A là câu hỏi hẹp hơn: **chiều continuation có giữ được trên riêng nửa sau hay không** — dữ liệu mà chưa ai đo riêng. Đó là **kiểm định độ ổn định qua thời gian**, không phải phát hiện.

Nếu đường A pass, câu được phép nói là *"chiều continuation ổn định qua hai nửa lịch sử"*. Câu **không** được phép nói là *"đã tìm ra một edge"*. §9.2 ghi giới hạn nhiễm dữ liệu đầy đủ.

---

## 8. File

| File | Việc |
|---|---|
| `rsi_fvg/quarter_variants.py` (tạo) | Năm hàm thống kê + `VARIANTS` dict + phép chia nửa + hai đường |
| `scripts/study_quarter_variants.py` (tạo) | CLI: nạp, chia, sàng, kiểm, ghi `results/`, in phán quyết §6 tính bằng máy |
| `tests/test_quarter_variants.py` (tạo) | Test từng biến thể trên bảng chu kỳ dựng tay; test median trượt không lookahead; test phép chia; test luật tie-break |
| `rsi_fvg/quarter_stats.py` (sửa) | Thêm tham số `stats: dict = STATS` cho `run_grid` và `run_null`. Mặc định giữ hành vi Phase 1 **không đổi một bit** — có test khẳng định điều đó. |

Dùng lại không sửa: `aggregate_cycles`, `make_offsets`, `percentile_of`, `MIN_BARS_PER_QUARTER`, `label_quarters`, `server_to_ny`, `verify_server_tz`.

Cổng chặn timezone (Phase 1 §3.2) chạy **trước** như cũ, thoát khác 0 nếu fail.

---

## 9. Giới hạn đã biết

1. **Kế thừa toàn bộ giới hạn của Phase 1 §8**: không tính cost; confound mốc 18:00 đã xác nhận bằng dữ liệu; null model chỉ kiểm "lưới này có đặc biệt so với lưới lệch"; một symbol một broker một khoảng thời gian; cổng chặn quyết định bằng mode nên một đoạn lệch có thể lọt; tầng micro bị loại.
2. **Nửa sau KHÔNG trong sạch.** Phase 1 đã chạy trên toàn bộ 2017–2026, nên tôi biết ⑥ ≈ 0,473 trên toàn kỳ trước khi thiết kế Phase 1b. Kiến thức đó đủ để làm lệch việc **chọn** biến thể. Đường A bị nhiễm nặng nhất (§7). Đường B nhiễm nhẹ hơn — V2–V5 thêm điều kiện mà giá trị của chúng chưa từng được đo — nhưng **không cái nào là out-of-sample thật**. Cách duy nhất để có holdout trong sạch là symbol khác hoặc broker khác, mà repo không có.
3. **Ngưỡng "vượt cả 69 null" có thể loại oan một hiệu ứng thật vừa phải** (§5). Đây là cái giá của việc kiểm soát đa kiểm định trên một tầng có độ phân giải null thô, chấp nhận có ý thức.
4. **Năm biến thể là một lựa chọn, không phải một tập đầy đủ.** Còn cách hình thức hoá khác. Số bị khoá ở 5 để §1.3 có nghĩa; việc đó cố ý đánh đổi độ phủ lấy tính kỷ luật.
5. **Nếu Phase 1b fail, kết luận là "năm cách hình thức hoá này không đứng trên XAUUSDc M5"** — không phải "Quarterly Theory sai". Phân biệt này quan trọng và §6 không được đọc rộng hơn thế.
