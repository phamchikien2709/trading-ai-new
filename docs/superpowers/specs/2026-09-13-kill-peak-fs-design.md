# Kill Peak + Failure Swing (`kill_peak_fs`) — Design Spec

Ngày: 2026-09-13
Trạng thái: chờ duyệt
Nguồn: hội thoại brainstorming 2026-09-13

Ghép hai engine đã có trong repo. M3 cung cấp **cửa sổ** và **đích**;
M1 cung cấp **thời điểm bóp cò**.

---

## 1. Mục tiêu

Mua khi thị trường còn nợ một cú lên quét đỉnh đã bỏ lại, và chỉ bóp cò
đúng lúc phe bán trên M1 kiệt sức.

Chuỗi sự kiện, chiều BUY:

1. **M3** — RSI(14) cắt lên 70. Bắt đầu đo đỉnh.
2. **M3** — RSI(14) hồi về, cắt xuống 50. Chốt `killHigh` = đỉnh cao nhất
   của đoạn đo. Đó là **thanh khoản treo**: thị trường đã đi qua vùng đó
   trong trạng thái quá mua rồi bỏ lại.
3. **M1** — chờ một setup failure swing đầy đủ: RSI(14) xuống dưới 30 →
   hồi lên trên 50 → giá phá thủng đáy của pha hồi mà RSI **không** phá
   đáy RSI tương ứng → xác nhận khi RSI cắt lên 50 một lần nữa.
4. **Vào lệnh** tại close nến xác nhận. SL dưới đáy chân 2.
   **TP = `killHigh`.**

Chiều SELL soi gương hoàn toàn.

Điểm khác `kill_peak`: tầng M1 không còn là zigzag RSI(2) + higher low,
mà là máy trạng thái failure swing của `rsi_failure_swing`.

---

## 2. Kiến trúc

Ba tầng, chạy theo thứ tự trong mỗi nến:

| Tầng | Nguồn | Vai trò |
|---|---|---|
| Bối cảnh M3 | `kill_peak_indicator.pine:82-173` | `killHigh`/`killLow`, `flagBuy`/`flagSell` |
| Máy trạng thái M1 | `rsi_failure_swing_indicator.pine:98-284` **trừ hai thân bước 3** | 4 trạng thái, phát hiện failure swing |
| Khối nối | **viết mới** | gate cờ + cửa sổ + RR, đặt TP = mức chờ kill |

Script chạy **trên chart M1**, kéo M3 bằng `request.security`.
`htfTf` mặc định `"3"`.

### 2.1 Bỏ hẳn tầng zigzag RSI(2)

`kill_peak_indicator.pine:177-239` (`seg`, `segHigh`, `segLow`,
`lastLowP`, `prevLowP`, `lastHighP`, `prevHighP` và toàn bộ phần vẽ
zigzag) **không mang sang**. Máy failure swing thay thế trọn vẹn vai
trò đó. Hệ quả: script mới không dài hơn `kill_peak` dù ghép hai thứ,
vì nó xoá một tầng nguyên vẹn.

`fastLen`/`fHi`/`fLo` và nhóm input `Swing (khung chart)` biến mất theo.

### 2.2 Hai file

- `pine/kill_peak_fs_indicator.pine` — để soi tay trên chart
- `pine/kill_peak_fs_strategy.pine` — để backtest

Quan hệ giữa hai file giống cặp `rsi_failure_swing_*`: strategy chép
nguyên văn mọi khối logic, bỏ phần vẽ trừ mũi tên, thêm sizing và đặt
lệnh. Bộ lọc vị thế nằm **ngoài** mọi khối chép.

---

## 3. Tầng M3 — đoạn đo và cờ chờ kill

Chép nguyên văn từ `kill_peak_indicator.pine`. Vùng đánh dấu
`---- KHOI BOI CANH HTF ----` … `---- HET KHOI BOI CANH ----`.

### 3.1 Nguồn RSI, không repaint

```pine
float ctxRsi = request.security(syminfo.tickerid, htfTf, ta.rsi(close, ctxLen)[1],
     barmerge.gaps_off, barmerge.lookahead_on)
```

`[1]` + `lookahead_on` là thành ngữ chuẩn: lấy giá trị của nến M3 **đã
đóng**, và lấy nó ngay từ nến M1 đầu tiên của nến M3 kế tiếp. Bỏ `[1]`
là nhìn trộm tương lai; bỏ `lookahead_on` là giá trị nhảy lùi khi chạy
realtime so với lịch sử.

### 3.2 Mốc

```pine
cUp70 = ctxRsi[1] <= ctxHi  and ctxRsi > ctxHi     // mở đoạn đo đỉnh
cDn50 = ctxRsi[1] >= ctxMid and ctxRsi < ctxMid    // chốt đỉnh, bật cờ BUY
cUp50 = ctxRsi[1] <= ctxMid and ctxRsi > ctxMid    // chốt đáy, bật cờ SELL
cDn30 = ctxRsi[1] >= ctxLo  and ctxRsi < ctxLo     // mở đoạn đo đáy
```

### 3.3 State

```
measHi, runHigh, killHigh, killHighBar, flagBuy, flagBuyBar, flagBuyUsed
measLo, runLow,  killLow,  killLowBar,  flagSell, flagSellBar, flagSellUsed
```

`seedHigh = ta.highest(high, n)`, `seedLow = ta.lowest(low, n)` với
`n = ceil(timeframe.in_seconds(htfTf) / timeframe.in_seconds())` — dùng
để mồi `runHigh`/`runLow` tại nến mở đoạn đo. `ta.*` phải ở top level.

`math.ceil` chứ không phải chia số nguyên: Pine cắt cụt phép chia
int/int. Với M3 trên chart M1 thì `n = 3`.

### 3.4 Thứ tự trong một nến — bắt buộc

1. **Nối cực trị** — `measHi` → `runHigh := max(runHigh, high)`
2. **Chạm mức** — `flagBuy and high >= killHigh` → cờ tắt, lý do `KILL`
3. **`cDn50` + `measHi`** → chốt `killHigh := runHigh`, bật `flagBuy`
4. **`cUp50` + `measLo`** → chốt `killLow := runLow`, bật `flagSell`
5. **`cDn30`** → `flagBuy` chết (`RSIOUT`), `flagSell` chết (`NEWLEVEL`),
   mở `measLo`
6. **`cUp70`** → `flagSell` chết (`RSIOUT`), `flagBuy` chết (`NEWLEVEL`),
   mở `measHi`

Bước 2 trước bước 3 là có chủ ý: nếu trong cùng một nến giá đã chạm
`killHigh` thì không còn gì để giao dịch, cờ chết trước khi tầng M1 kịp
dùng nó.

### 3.5 Bất biến: hai cờ không bao giờ cùng bật

`flagBuy` chỉ bật ở bước 3, và `measHi` chỉ mở ở bước 6 (`cUp70`) — mà
`cUp70` giết `flagSell`. Đối xứng cho chiều kia. Nên không cần luật ưu
tiên chiều.

---

## 4. Tầng M1 — máy trạng thái failure swing

Chép nguyên văn từ `rsi_failure_swing_indicator.pine`, **trừ hai thân
bước 3**. Xem §5.1.

### 4.1 Bốn trạng thái (chiều BUY; SELL soi gương qua `obLevel`)

| Từ | Sự kiện | Sang | Ghi |
|---|---|---|---|
| IDLE (0) | RSI cắt **xuống** `osLevel` | SEEKING (1) | `bP1 := low`, `bR1 := rsi` |
| SEEKING | theo dõi | SEEKING | `bP1` = low thấp nhất, `bR1` = RSI thấp nhất |
| SEEKING | RSI cắt **lên** `midLevel` | ARMED (2) | chốt `bP1`/`bR1`, mồi `bP2`/`bR2` |
| ARMED | giá thủng `bP1` | BROKEN (3) | |
| BROKEN | RSI cắt **lên** `midLevel` | IDLE | **ra tín hiệu** |

### 4.2 Huỷ cứng — áp cho cả ARMED lẫn BROKEN

- RSI ≥ `cancelHi` (BUY) / ≤ `cancelLo` (SELL) — thị trường đã rời chế
  độ đó đáy, tiền đề của setup mất
- quá `maxWait` nến kể từ lúc ARM

### 4.3 Vô hiệu — chỉ ở BROKEN, và **không** vứt setup đi

Nếu `bR2 < bR1` — RSI của chân 2 còn tệ hơn chân 1, tức **không có phân
kì** — thì chân 2 trở thành chân 1 mới (`bP1 := bP2`, `bR1 := bR2`) và
quay về SEEKING.

Ngưỡng là `bR1`, **không** phải mức 30 cố định. `bR1` luôn dưới
`osLevel` theo định nghĩa, nên chân 2 được phép xuống dưới 30 miễn còn
cao hơn chân 1. Đây là luật đã được sửa ở commit `6dae91b` theo đúng ý
người dùng ("đỉnh đáy 2, rsi k phá đỉnh đáy 1 là được") — chép sang đây
nguyên vẹn, không được diễn giải lại.

`requireR2Beyond` (mặc định **tắt**) bật thêm điều kiện chân 2 phải nằm
trong `r2Lo`/`r2Hi`.

### 4.4 Thứ tự trong một nến — bắt buộc

```
1.  nối cực trị (bP1/bR1 ở SEEKING; bP2/bR2 ở ARMED+BROKEN)
2.  huỷ cứng
2b. vô hiệu (chỉ BROKEN)
3.  TÍN HIỆU            <- khối nối, §5
4.  giá phá chân 1
5.  mở pha quá bán
6.  chốt chân 1, vũ trang
```

Bước 3 **trước** bước 4 là thứ thực thi luật "một lần nữa": một nến đảo
chiều mạnh vừa thủng `bP1` vừa đóng cửa trên 50 chỉ đạt trạng thái
BROKEN, **không** ra tín hiệu. Phải chờ nhịp sau. Đảo hai bước là đổi
hành vi — oracle đã có test bắt đúng chuyện này.

---

## 5. Khối nối — vào lệnh

Đây là toàn bộ code mới của dự án. Nó thay thế thân bước 3 của
`rsi_failure_swing`.

### 5.1 Vì sao phải viết lại chứ không chép

Bước 3 gốc tính `bTp = e + tpR * (e - s)`. TP giờ là `killHigh`, và cần
thêm gate cờ + cửa sổ + bộ lọc RR. Mà bước 3 **không bê ra ngoài máy
trạng thái được** vì vị trí của nó trước bước 4 là load-bearing (§4.4).

Nên vùng chép nguyên văn của M1 tách làm ba mảnh:

```
[M1-A]   series + khai báo state + BUY bước 1, 2, 2b
  J-BUY    BUY bước 3                                  <- mới
[M1-B]   BUY bước 4, 5, 6 + SELL bước 1, 2, 2b
  J-SELL   SELL bước 3                                 <- mới
[M1-C]   SELL bước 4, 5, 6
```

Ba mảnh chép được đối chiếu máy về file gốc; hai khối nối là code riêng
của script này và **không** đối chiếu được — đó là đường may, đúng chỗ
hai engine gặp nhau.

### 5.2 Bốn biến mới, khai báo ngoài vùng chép

`bRr`, `bRejRr`, `sRr`, `sRejRr` **không có** trong
`rsi_failure_swing_indicator.pine` (đã kiểm: 0 lần xuất hiện). Chúng chỉ
phục vụ bộ lọc RR, vốn là thứ mới của script này.

Khai báo ngay **trước** mốc `KHOI M1-A`, cùng chỗ với các biến per-bar
khác:

```pine
float bRr    = na
bool  bRejRr = false
float sRr    = na
bool  sRejRr = false
```

Đặt chúng trong vùng chép là làm hỏng bất biến §12 ngay từ dòng đầu.

### 5.3 J-BUY

```pine
if bSt == 3 and xUpMid
    bool gate = enableBuy and flagBuy and not na(killHigh)
         and (not requireLeg2AfterFlag or bP2Bar >= flagBuyBar)
         and not (oneTradePerFlag and flagBuyUsed)
    if gate
        float e = close
        float s = bP2 - slAtrMult * atr
        bool  slOk = not (minSlTicks > 0 and e - s < minSlTicks * syminfo.mintick)
        if e - s > 0 and slOk and killHigh - e > 0
            float r = (killHigh - e) / (e - s)
            if r >= minRR and (maxRR <= 0 or r <= maxRR)
                bSig        := true
                bEntry      := e
                bSl         := s
                bTp         := killHigh
                bRr         := r
                flagBuyUsed := true
            else
                bRejRr := true
                bRr    := r
    bSt := 0
```

`bSt := 0` nằm **ngoài** mọi `if` con: setup bị loại vì bất cứ lý do gì
vẫn bị tiêu. Giống hệt `rsi_failure_swing` gốc và có test phủ.

`flagBuyUsed := true` đặt **bên trong** nhánh ra tín hiệu, sau khi mọi
bộ lọc đã qua. Đây là bài học từ vòng soát cuối của `kill_peak`
(commit `d7f625b`): một lệnh bị loại mà vẫn tiêu cờ sẽ làm bộ đếm đọc
sai, và bộ đếm chính là phép đo của dự án.

Dòng nối tiếp thụt **5 dấu cách** — Pine đọc thụt chia hết cho 4 là
khối mới.

### 5.4 SELL soi gương

`sBad`, `flagSell`, `killLow`, `sP2Bar >= flagSellBar`,
`s = sP2 + slAtrMult * atr`, `e - killLow > 0`,
`r = (e - killLow) / (s - e)`, `sTp := killLow`.

### 5.5 "Nến xác nhận phải trong cửa sổ" là tự động

Không cần kiểm riêng. `flagBuy` đang bật tại nến này, mà `flagBuy` chỉ
bật ở nến `flagBuyBar` và chỉ tắt khi chết — nên `flagBuyBar <=
bar_index` luôn đúng. Chỉ **đáy chân 2** cần kiểm tường minh.

Trường hợp biên: cờ bật **cùng nến** với xác nhận M1
(`flagBuyBar == bar_index`). Khi đó `bP2Bar < bar_index` nên
`requireLeg2AfterFlag` chặn. Đúng ý muốn — chân 2 hình thành trước khi
mức chờ kill tồn tại.

### 5.6 Cờ chết giữa chừng: không nối vào máy M1

Nếu `flagBuy` chết lúc máy M1 đang ở BROKEN, máy M1 **vẫn chạy tiếp**.
Không reset, không ghi nhớ. Tín hiệu đơn giản là không qua được gate.

Lý do không cần xử lý gì thêm: nếu sau đó có cờ mới, `flagBuyBar` của
nó lớn hơn `bP2Bar` cũ, nên `requireLeg2AfterFlag` chặn. Setup cũ tự
chết mà không cần một dòng code nào.

---

## 6. Thứ tự toàn cục trong một nến

```
1. ctxRsi, atr, rsi, seedHigh, seedLow       (ta.* top level)
2. KHỐI BỐI CẢNH HTF   — §3.4 bước 1..6
3. KHỐI M1             — §4.4 bước 1..6, với J-BUY / J-SELL chèn ở bước 3
4. Vẽ
5. Bảng
6. Alert / đặt lệnh
```

Tầng M3 **phải** chạy trước tầng M1: khối nối đọc `flagBuy`/`killHigh`
của **nến hiện tại**.

---

## 7. Vẽ (indicator)

`overlay=true` — pane giá. Khác `rsi_failure_swing` (pane RSI riêng).

Lý do: câu chuyện của setup này là **mức chờ kill trên giá**, không
phải hình dạng RSI. Muốn xem pane RSI thì nạp thêm
`rsi_failure_swing_indicator.pine` lên cùng chart — hai script dùng
chung luật M1 nên trạng thái khớp nhau.

Hệ quả: đường phân kì chỉ vẽ **bên giá** (chân 1 → chân 2), không có
bản trên RSI.

| Đối tượng | Điều kiện | Input |
|---|---|---|
| Đường `killHigh`/`killLow` kéo dài trong lúc cờ bật | `flagBuy`/`flagSell` | `showCtx` |
| Tô nền theo trạng thái M1 | `bSt`/`sSt` khác 0 | `showState` |
| Đường phân kì chân 1 → chân 2 | tại nến tín hiệu | `showDiv` |
| Mũi tên + nhãn entry + đường SL/TP | `bSig`/`sSig` | `showSig` |
| Nhãn setup bị loại vì RR (ghi R thực tế) | `bRejRr`/`sRejRr` | `showRejected` |
| Nhãn lý do cờ chết (`KILL`/`RSIOUT`/`NEWLEVEL`) | `buyEnd`/`sellEnd` | `showCtx` |

**Bất biến vẽ:** mọi predicate dùng để vẽ phải **giống hệt** predicate
dùng để ra tín hiệu. Đây là lỗi Critical đã mắc ở `kill_peak` Task 6
(phần vẽ dùng `lastLowP > prevLowP`, phần tín hiệu dùng
`+ hlMarginAtr * atr`, chart vẽ nhãn xanh mà strategy không đồng ý).
Một công cụ soi tay vẽ sai là một công cụ nói dối.

**Guard bắt buộc:** không gọi `line.set_x2` trên handle `na`. Đó là
runtime error giết script giữa chart — đã mắc một lần ở `kill_peak`.

`max_lines_count=500, max_labels_count=500` ở cả hai file. `strategy()`
mặc định **50** label, phải truyền tường minh.

---

## 8. Hai bảng

### 8.1 Bảng trạng thái (`showTable`)

| Hàng | Nội dung |
|---|---|
| `RSI M3` | giá trị `ctxRsi` |
| `Cờ` | `CHỜ KILL BUY @ <killHigh>` / `CHỜ KILL SELL @ <killLow>` / `—` |
| `Chờ (nến)` | `bar_index - flagBuyBar` |
| `M1 BUY` | `CHỜ HỒI` / `SẴN SÀNG` / `ĐÃ PHÁ CHÂN 1` / `—` |
| `  chân 1 (giá / RSI)` | `bP1` / `bR1` |
| `  chân 2 (giá / RSI)` | `bP2` / `bR2` |
| `M1 SELL` | như trên |
| `RR nếu vào bây giờ` | `(killHigh - close) / (close - (bP2 - slAtrMult*atr))` |

Hàng cuối là hàng quan trọng nhất để soi tay — nó cho thấy RR đang teo
dần theo từng nến giá hồi lên.

### 8.2 Bảng đếm (`showCounters`)

Đây là **phép đo của dự án**, vì rủi ro lớn nhất đã biết là điểm vào
muộn làm RR kém (§11.1):

| Dòng | Ý nghĩa |
|---|---|
| Cờ bật | tổng số cờ BUY + SELL đã bật |
| Cờ chết: KILL | giá chạm mức mà **không** có setup M1 nào vào kịp |
| Cờ chết: RSIOUT / NEWLEVEL | bối cảnh mất trước khi giá quay lại |
| Setup M1 xong trong cửa sổ | số lần bước 3 chạy với `gate` đúng |
| **Loại vì RR** | `bRejRr`/`sRejRr` — con số phải nhìn đầu tiên |
| Loại vì SL quá ngắn | `minSlTicks` |
| Vào lệnh | `bSig`/`sSig` |

Dòng `Cờ chết: KILL` đối chiếu với `Vào lệnh` trả lời câu hỏi trung tâm:
*trong bao nhiêu lần thị trường thật sự quay lại quét mức, ta có mặt?*

---

## 9. File strategy

Theo đúng hình `rsi_failure_swing_strategy.pine` (commit `46aaaec`).

- Mọi khối có mốc (`KHOI BOI CANH HTF`, `M1-A`, `M1-B`, `M1-C`) **và**
  hai khối nối J-BUY/J-SELL chép nguyên văn từ indicator. Không ngoại lệ.
- Bộ lọc vị thế nằm **ngoài** mọi khối, ở chỗ đặt lệnh:
  `if bSig and strategy.position_size == 0`
- Sizing: `qty = equity * riskPct / 100 / (slDist * syminfo.pointvalue)`
- `bSl`/`bTp` đã là mức giá tuyệt đối → `strategy.entry` +
  `strategy.exit(stop=, limit=)` đặt **một lần**, không cần re-arm
- Bỏ toàn bộ phần vẽ trừ hai `plotshape`
- Alert JSON: `"setup":"KILLPEAKFS"`

**Hệ quả đã biết, có chủ ý:** máy trạng thái chạy y hệt dù đang có lệnh
hay không, nên cột trạng thái hai file luôn khớp; đổi lại, tín hiệu rơi
trúng lúc đang có vị thế sẽ không vào lệnh và biến mất khỏi bảng lệnh.
Mũi tên vẫn vẽ theo tín hiệu chứ không theo lệnh khớp.

---

## 10. Inputs

```
Boi canh (HTF)
  htfTf               timeframe  "3"
  ctxLen              int        14
  ctxHi               float      70
  ctxMid              float      50
  ctxLo               float      30

RSI (khung chart)
  rsiLen              int        14
  obLevel             float      70
  midLevel            float      50
  osLevel             float      30

Huy setup M1
  cancelHi            float      70
  cancelLo            float      30
  maxWait             int        150      (0 = tắt)
  requireR2Beyond     bool       false
  r2Lo                float      30
  r2Hi                float      70

Cua so cho kill
  requireLeg2AfterFlag bool      true
  oneTradePerFlag      bool      true

Rui ro
  atrLen              int        14
  slAtrMult           float      0.5
  minRR               float      1.0
  maxRR               float      0.0      (0 = không chặn)
  minSlTicks          int        10

Chieu
  enableBuy           bool       true
  enableSell          bool       true

Thuc thi lenh            (chỉ strategy)
  riskPct             float      1.0

Hien thi
  showCtx / showState / showDiv / showSig / showRejected
  showTable / showCounters
```

**Biến mất so với hai file nguồn:**

- `tpR` (của `rsi_failure_swing`) — TP giờ là `killHigh`
- `fastLen`, `fHi`, `fLo` (của `kill_peak`) — không còn zigzag
- `hlMarginAtr`, `requireSwing2AfterFlag` (của `kill_peak`) — thay bằng
  `requireLeg2AfterFlag`

---

## 11. Rủi ro đã biết

### 11.1 Điểm vào muộn → RR kém một cách hệ thống

`rsi_failure_swing` bóp cò khi RSI(14) cắt lên 50 **lần thứ hai**. Muốn
RSI(14) từ vùng quá bán lên tới 50 thì giá đã hồi khá xa. So với
`kill_peak` (cò bật khi leg RSI(2) kết thúc) điểm vào này muộn hơn hẳn.

Cộng dồn hai chiều: `killHigh − entry` nhỏ đi (TP ngắn), còn SL vẫn treo
ở `bP2` tận đáy cú phá (SL dài). `minRR` sẽ loại nhiều setup.

Đã trình bày với người dùng trước khi chốt luật; người dùng chọn giữ
nguyên luật xác nhận. Đo bằng dòng **Loại vì RR** ở bảng đếm. Nếu con số
đó áp đảo thì hai nước đi tiếp theo, theo thứ tự: hạ `minRR`, hoặc thêm
input cho phép vào tại nến phá chân 1 (đã có sẵn trạng thái, chỉ là
thêm nhánh).

### 11.2 Tần suất có thể rất thấp

Một setup failure swing **đầy đủ** (RSI<30 → >50 → phá → >50) nằm gọn
trong cửa sổ chờ kill, với đáy chân 2 sau nến bật cờ, là điều kiện
nhiều tầng. Số lệnh có thể ít tới mức không đọc được thống kê.

Phải đo trước khi kết luận. Nới đầu tiên là tắt `requireLeg2AfterFlag`.

### 11.3 Entry ở close, khớp ở open nến sau

Rủi ro thật mỗi lệnh là `riskPct * (open[N+1] - SL) / (close[N] - SL)`.
Trên XAU một cú gap có thể làm lệch vài phần trăm. Đã biết, có chủ ý
không xử lý — giống hai file nguồn.

### 11.4 Không compile được Pine ở máy này

Mọi thứ chỉ qua checker tĩnh, oracle Python và đọc tay. **Không được
viết "đã test"** ở bất cứ đâu. `force_overlay` không dùng ở file này
(overlay=true) nên bớt được một chỗ ngờ so với `rsi_failure_swing`.

---

## 12. Bất biến chép nguyên văn

Năm vùng có mốc, trên hai file:

| Vùng | Nguồn gốc |
|---|---|
| `KHOI BOI CANH HTF` | `kill_peak_indicator.pine` |
| `KHOI M1-A` | `rsi_failure_swing_indicator.pine` |
| `KHOI M1-B` | `rsi_failure_swing_indicator.pine` |
| `KHOI M1-C` | `rsi_failure_swing_indicator.pine` |
| tất cả vùng trên + J-BUY + J-SELL | `kill_peak_fs_indicator.pine` → `_strategy.pine` |

Rủi ro thật của hướng thi công này là **trôi phiên bản**: khối HTF sẽ
tồn tại ở 4 file, khối M1 ở 4 file. Chống trôi bằng máy chứ không bằng
trí nhớ:

**`scratchpad/blockdiff.py`** — tổng quát hoá `rfs_blockdiff.py`. Quét
toàn bộ `pine/`, tìm mọi cặp mốc `---- KHOI <ten> ----` /
`---- HET KHOI <ten> ----`, gom theo tên, so từng dòng giữa mọi file
chứa cùng một tên. In `LECH` + unified diff, thoát mã 1 nếu có lệch.
Một lệnh kiểm được cả năm vùng trên chín file pine.

Luật làm việc: **sửa luật thì sửa ở file gốc rồi chép lại**, không sửa
riêng một bên.

---

## 13. Kiểm chứng

Pine không compile được ở máy này. Ba lớp thay thế:

### 13.1 Checker tĩnh

`scratchpad/kp_check.py` trên cả hai file mới. Phải in `SACH`.
Bắt: thụt dòng nối tiếp chia hết cho 4, `ta.*` trong `if`, ngoặc lệch.

### 13.2 Oracle Python

Xây `kpfs_oracle.py` bằng cách ghép:

- **Máy M1** — `import` thẳng `step_side` từ `rfs_oracle.py` đã có, với
  20 test xanh. Không viết lại.
- **Máy HTF** — mới: `measHi`/`runHigh`/`killHigh`/`flagBuy` + sáu bước
  §3.4, lấy chuỗi `ctx_rsi` làm đầu vào trực tiếp (không mô phỏng
  `request.security`; ánh xạ M3→M1 nằm ngoài phạm vi oracle).
- **Khối nối** — mới: gate + RR, đúng §5.3.

`step_side` của `rfs_oracle` tính TP bên trong, nhưng **không được sửa
nó**: 20 test hiện có khẳng định đúng giá trị TP đó, sửa là phá.

Thay vào đó **bọc ngoài**. `step_side` trả về `sig` (hoặc `None`) và
luôn đặt `st = IDLE` bất kể kết quả. Oracle mới gọi nó, rồi:

- nếu `sig is None` → không có gì làm
- nếu có `sig` → áp gate §5.3. Gate trượt thì **vứt `sig` đi**; `st` đã
  về IDLE rồi nên trạng thái vẫn khớp Pine.
- gate qua → thay `sig["tp"]` bằng `kill_high`, tính `r`, áp
  `min_rr`/`max_rr`, đặt `flag_used`.

Tương đương quan sát được với Pine: ở Pine khi `gate` sai thì `e`/`s`
không được tính và `bSig` không bao giờ bật; ở oracle chúng được tính
rồi vứt. Kết quả nhìn từ ngoài y hệt, mà `rfs_oracle.py` không phải
động tới một dòng.

Truyền `min_sl_dist = minSlTicks * mintick` vào `P` — tham số đó đã có
sẵn, thêm ở commit `46aaaec`.

Test bắt buộc, tối thiểu:

1. Cờ BUY bật đúng nến `cDn50`, `killHigh` bằng đỉnh cao nhất đoạn đo
2. Cờ chết vì `KILL` khi giá chạm mức
3. Cờ chết vì `RSIOUT`, vì `NEWLEVEL`
4. Hai cờ không bao giờ cùng bật (§3.5)
5. Setup M1 đủ + cờ bật → ra lệnh, TP đúng bằng `killHigh`
6. Setup M1 đủ + **không** cờ → không lệnh, nhưng `bSt` vẫn về 0
7. `requireLeg2AfterFlag`: chân 2 trước cờ → chặn; sau cờ → qua
8. Cờ bật cùng nến xác nhận → chặn (§5.5)
9. `oneTradePerFlag`: lệnh thứ hai trong cùng cờ bị chặn
10. Loại vì `minRR`, loại vì `maxRR`, loại vì `minSlTicks` — và cả ba
    trường hợp **vẫn tiêu setup** (`bSt == 0`)
11. Loại vì RR **không** tiêu cờ (`flagBuyUsed` còn `false`) — §5.3
12. Cờ chết giữa lúc M1 ở BROKEN → M1 chạy tiếp, không lệnh (§5.6)
13. Chiều SELL soi gương cho các mục 1, 5, 7, 10
14. Hai chiều độc lập: dữ liệu chỉ có setup BUY thì phía SELL im lặng

### 13.3 Mutation testing

Với mỗi luật mới ở §5, cố tình phá oracle và chứng minh có test đỏ.
Bắt buộc thử tối thiểu:

- đảo `bP2Bar >= flagBuyBar` thành `>`
- bỏ `flagBuy` khỏi `gate`
- chuyển `flagBuyUsed := true` ra ngoài nhánh ra tín hiệu
- đổi `bTp := killHigh` thành `bTp := e + 3 * (e - s)`
- đảo `r >= minRR` thành `r > minRR`
- đưa `bSt := 0` vào trong `if gate`

Kinh nghiệm hai dự án trước: **mutation liên tục lộ ra test rỗng**. Trên
Windows phải xoá `__pycache__` trước mỗi lần chạy — hai lệnh `cp` liên
tiếp cho mtime giống hệt nhau và Python dùng lại bytecode cũ.

### 13.4 Đối chiếu khối

`blockdiff.py` phải in `GIONG HET` cho cả năm vùng, trên mọi file.

---

## 14. Ngoài phạm vi

- **Bản Python** (`rsi_fvg/strategies/`) — như `kill_peak`, hoãn tới khi
  luật được xác nhận trên chart thật.
- **Tối ưu tham số** — không grid search trong dự án này.
- **Vào lệnh tại nến phá chân 1** — đã cân nhắc và loại ở bước
  brainstorming. Chỉ mở lại nếu §11.1 đo ra số xấu.
- **Chia lệnh làm hai phần TP** — đã cân nhắc và loại.
