# Đỉnh Chờ Kill (`kill_peak`) — Indicator + Strategy hai khung — Design Spec

**Ngày:** 2026-09-12
**Trạng thái:** Đã duyệt thiết kế
**Phạm vi bản này:** chỉ hai file Pine. Port Python + registry + tests để sau khi luật ổn định qua test tay.
**Kế thừa:** cấu trúc swing RSI(2) 90/10 của `2026-09-08-rsi2-swing-backtest-optimizer-design.md` §2.2 (bản đã vá, xem §4.1); idiom MTF không repaint của `pine/rsi2_swing_strategy.pine:83`; khung execution của `pine/rsi2_ema_swing_strategy.pine`.

---

## 1. Mục tiêu

Bắt cú quét thanh khoản: khung M5 chỉ ra **cái đỉnh mà thị trường còn nợ**, khung M1 chờ giá tạo **higher low** rồi vào BUY, chốt lời đúng tại cái đỉnh đó. Chiều SELL soi gương.

Giao hai file:

| File | Vai trò |
|---|---|
| `pine/kill_peak_indicator.pine` | `overlay=true`, không đặt lệnh. Vẽ đủ để soi tay từng cú và đếm thống kê. |
| `pine/kill_peak_strategy.pine` | cùng khối tín hiệu, thêm sizing/exit/alert. |

Không đụng file nào đang có trong repo.

---

## 2. Kiến trúc

Script chạy trên **chart M1**. Đúng **một** lời gọi `request.security` kéo RSI bối cảnh từ M5 về; toàn bộ máy trạng thái chạy trên trục M1.

```pine
float ctxRsi = request.security(syminfo.tickerid, htfTf, ta.rsi(close, ctxLen)[1],
     barmerge.gaps_off, barmerge.lookahead_on)
```

Cặp `[1]` + `lookahead_on` là idiom không repaint đã dùng trong repo: `lookahead` lấy ô của nến HTF ngay khi nó mở, `[1]` đẩy về nến HTF **đã đóng** liền trước. Giá trị vì vậy chỉ đổi 5 nến M1 một lần và không bao giờ sửa lại quá khứ.

**Lý do chọn hướng này** thay vì nhét cả máy trạng thái M5 vào trong `request.security`: file indicator sinh ra để soi tay, nên mọi biến trạng thái phải plot được trên chart M1. Đặt state trong ngữ cảnh HTF là giấu nó đi đúng chỗ cần nhìn nhất.

**Cái giá phải trả và cách vá.** Lúc phát hiện cú cắt lên 70, nến M5 gây ra cú cắt đó đã đóng — phần cao của chính nó nằm ở `n` nến M1 vừa qua. Nên khi mở đoạn đo phải seed:

```
n       = math.max(1, math.round(timeframe.in_seconds(htfTf) / timeframe.in_seconds()))
runHigh = ta.highest(high, n)
```

Nếu `timeframe.in_seconds(htfTf) <= timeframe.in_seconds()` → `runtime.error()`, vì khung bối cảnh phải lớn hơn khung chart.

---

## 3. Tầng M5 — đoạn đo và cờ chờ

### 3.1 Mốc

| | mở đoạn đo | chốt mức + bật cờ | huỷ cờ |
|---|---|---|---|
| **BUY** | cắt lên `ctxHi` (70) | cắt xuống `ctxMid` (50) → **đỉnh chờ kill** | cắt xuống `ctxLo` (30) · cắt lên 70 lần nữa · `high >= killHigh` |
| **SELL** | cắt xuống `ctxLo` (30) | cắt lên `ctxMid` (50) → **đáy chờ kill** | cắt lên `ctxHi` (70) · cắt xuống 30 lần nữa · `low <= killLow` |

Không có luật hết hạn theo số nến, không có chặn dưới theo giá.

Cùng một sự kiện làm hai việc khác nhau tuỳ trạng thái: cắt lên 70 **khi đoạn đo còn mở** thì giữ nguyên đoạn, chỉ tiếp tục mở rộng đỉnh; cắt lên 70 **khi cờ đang bật** thì mở đoạn đo mới và vứt đỉnh cũ.

### 3.2 State

```
measHi, runHigh, killHigh, killHighBar, flagBuy,  flagBuyBar,  flagBuyUsed
measLo, runLow,  killLow,  killLowBar,  flagSell, flagSellBar, flagSellUsed
```

Sự kiện, tính trên trục M1 từ chuỗi `ctxRsi`:

```
cUp70 = ctxRsi[1] <= ctxHi  and ctxRsi > ctxHi
cDn50 = ctxRsi[1] >= ctxMid and ctxRsi < ctxMid
cUp50 = ctxRsi[1] <= ctxMid and ctxRsi > ctxMid
cDn30 = ctxRsi[1] >= ctxLo  and ctxRsi < ctxLo
```

### 3.3 Thứ tự xử lý trong một nến — bắt buộc đúng thứ tự này

1. **Nới cực trị.** `measHi` mở → `runHigh := math.max(runHigh, high)`. `measLo` mở → `runLow := math.min(runLow, low)`.
2. **Chạm mức.** `flagBuy and high >= killHigh` → tắt cờ, lý do `KILL`. `flagSell and low <= killLow` → tắt, lý do `KILL`.
3. **`cDn50`** → nếu `measHi` thì `killHigh := runHigh`, `measHi := false`, `flagBuy := true`, `flagBuyBar := bar_index`, `flagBuyUsed := false`.
4. **`cUp50`** → mirror cho `flagSell`.
5. **`cDn30`** → nếu `flagBuy` thì tắt, lý do `RSI30`; nếu `flagSell` thì tắt, lý do `NEWLEVEL` (đáy mới sắp thay đáy cũ). Sau đó: `measLo` đang mở thì giữ; chưa mở thì mở và seed `runLow := ta.lowest(low, n)`.
6. **`cUp70`** → nếu `flagSell` thì tắt, lý do `RSI70`; nếu `flagBuy` thì tắt, lý do `NEWLEVEL`. Sau đó: `measHi` đang mở thì giữ; chưa mở thì mở và seed `runHigh := ta.highest(high, n)`.

Ba lý do tắt cờ, dùng chung cho cả hai chiều: `KILL` · `RSIOUT` (`RSI30` cho BUY, `RSI70` cho SELL) · `NEWLEVEL`.

**Vì sao thứ tự quan trọng.** `ctxRsi` nhảy 5 nến M1 một lần nên một bước nhảy lớn có thể kích hoạt hai sự kiện cùng nến. Chỉ hai cặp là có thể xảy ra — `{cDn50, cDn30}` và `{cUp50, cUp70}` — và cả hai đều phải **chốt trước, huỷ sau**: RSI rơi thẳng từ 75 xuống 25 thì cờ BUY sinh ra và chết ngay trong cùng nến, đúng ý (momentum đã mất, không được vào lệnh). Hai cặp còn lại bất khả: `cDn50` cần `ctxRsi < 50` còn `cUp70` cần `ctxRsi > 70`; `cUp50` cần `> 50` còn `cDn30` cần `< 30`.

### 3.4 Bất biến: hai cờ không bao giờ cùng bật

Muốn có `flagSell` thì phải có `measLo`; `measLo` chỉ mở bằng `cDn30`; mà `cDn30` giết `flagBuy` (bước 5). Đối xứng cho chiều kia. Hệ quả: **không cần luật ưu tiên chiều** ở tầng vào lệnh.

---

## 4. Tầng M1 — swing bằng RSI(2)

### 4.1 Cấu trúc leg xen kẽ

Dùng lại nguyên khối của `pine/rsi2_divergence_indicator.pine`, kèm bản vá đã có ở đó:

- `rsiF = ta.rsi(close, fastLen)`, mốc `fHi`/`fLo` = 90/10.
- Leg LOW mở khi cắt xuống `fLo`, chạy tới khi cắt lên `fHi`; swing low = `low` **thấp nhất cả leg**, xác nhận tại nến cắt lên `fHi`. Leg HIGH soi gương.
- **Cắt lại theo hướng đã mở leg hiện tại thì không làm gì** — RSI(2) chọc xuống dưới 10 lần nữa khi đang trong leg LOW không khởi động lại việc theo dõi đáy. (Đây là chỗ `rsi2_swing` và `rsi2_ema_swing` còn sai, xem commit `96ddb5d`.)

Ghi rõ để khỏi nhầm với tài liệu nguồn: đặc tả v2 ban đầu định nghĩa swing theo **"đợt"** — chỉ đoạn RSI(2) nằm dưới 10. Đã chốt **không** dùng cách đó, dùng leg xen kẽ. Hệ quả: swing low theo leg luôn `<=` swing low theo đợt, nên SL xa hơn và R:R nhỏ hơn con số trong hình minh hoạ của tài liệu; đổi lại cấu trúc zigzag sạch và không cần luật khoảng cách tối thiểu giữa hai swing.

### 4.2 Bỏ hẳn khối nến neo

Đặc tả nói thẳng "không ràng buộc gì về RSI tại hai swing đó". Toàn bộ máy móc anchor (`bullRsi`/`bearRsi`, `segHighAnc`, …) của file divergence **không** mang sang.

### 4.3 State lưu

`lastLowP, lastLowBar, prevLowP, prevLowBar, lowConf` và bộ mirror cho high.

---

## 5. Vào lệnh

BUY nổ tại nến xác nhận một swing low, khi đủ cả sáu:

1. `lowConf` và `enableBuy` và `not na(prevLowP)`
2. `flagBuy` đang bật
3. `lastLowP > prevLowP + hlMarginAtr * atr` — higher low
4. `lastLowBar >= flagBuyBar` — **nến đáy** của swing này nằm sau lúc cờ bật (swing trước được phép nằm trước cờ). Tắt được bằng `requireSwing2AfterFlag`.
5. `not flagBuyUsed` khi `oneTradePerFlag` bật; và đang không có lệnh nào mở
6. `rr >= minRR` và (`maxRR == 0` or `rr <= maxRR`)

```
entry = close
sl    = lastLowP - slAtrMult * atr        (yêu cầu entry - sl > 0)
tp    = killHigh
rr    = (tp - entry) / (entry - sl)
```

SELL soi gương: `lastHighP < prevHighP - hlMarginAtr*atr`, `sl = lastHighP + slAtrMult*atr`, `tp = killLow`.

**Quyết định đã chốt, ghi lại để khỏi mở lại:**

| | |
|---|---|
| i | Một cờ tối đa một lệnh (`oneTradePerFlag`, mặc định bật), theo tiền lệ `rsi_fvg`. |
| ii | "Swing thứ hai sau cờ" = **nến đáy** sau cờ, không phải nến xác nhận — nến xác nhận thì hiển nhiên sau rồi, điều kiện sẽ vô nghĩa. |
| iii | "Chạm đỉnh chờ kill" dùng `high >= killHigh`, râu chạm là tính — khớp cách lệnh TP limit được khớp. |
| iv | `hlMargin` đo bằng ×ATR, không phải %, cho đồng bộ với repo. |
| v | Đang có lệnh mà tín hiệu ngược chiều nổ thì bỏ qua, không đảo lệnh. |
| vi | So higher low với **swing liền trước**, không phải đáy thấp nhất trong N swing. |
| vii | Bỏ hẳn chế độ phân kì của v1 — repo đã có file riêng cho phân kì. |

---

## 6. Vẽ (indicator)

Ba lớp, bật tắt riêng.

**Bối cảnh M5.** `bgcolor` nhạt suốt lúc đoạn đo mở (hồng = đo đỉnh, xanh = đo đáy). Đỉnh chờ kill là đường ngang amber dày từ nến chốt kéo sang phải, dừng đúng nến cờ tắt, kèm label ghi **lý do tắt** theo ba tên ở §3.3 — chiều BUY hiện `KILL ✓` / `RSIOUT 30` / `NEWLEVEL 70`. Label này là thứ đáng giá nhất khi soi tay — nó cho thấy mỗi cú hỏng là hỏng kiểu gì.

Hạn chế đã biết: `overlay=true` nên không plot được RSI(14) M5 thành đường ở pane riêng. Giá trị live nằm trong bảng, trạng thái đọc qua `bgcolor`. Muốn nhìn đường thật thì kéo thêm một RSI thường và đặt tf `5`.

**Swing M1.** Chấm tại nến đáy/đỉnh thật kèm giá; zigzag nối các swing liên tiếp. Có higher low thì nối hai đáy bằng đường xanh dày + label `HIGHER LOW 102.38 → 103.26`. Swing mới *không* higher trong lúc cờ bật thì vẫn nối nhưng xám mảnh, để thấy setup trượt ở đâu.

**Lệnh.** Mũi tên + giá; đường SL đỏ đứt và TP amber kéo tới lúc chạm; label `R:R 9.3` tại nến entry. Trường hợp qua hết điều kiện nhưng **bị loại vì RR** thì vẫn vẽ, màu xám, label `RR 0.6 < min` — không vẽ thì không phân biệt được "không có tín hiệu" với "có mà bị lọc".

---

## 7. Hai bảng

**Bảng trạng thái** (2 cột): chart TF / HTF · `ctxRsi` · trạng thái M5 (`ĐANG ĐO ĐỈNH` / `CHỜ KILL 111.29, 34 nến` / `ĐANG ĐO ĐÁY` / `—`) · `rsiF` · swing low gần nhất và trước đó · swing high gần nhất và trước đó · tín hiệu gần nhất kèm RR.

**Bảng đếm** (3 cột: chỉ tiêu · BUY · SELL) — đây là số để so v1 với v2:

```
                       BUY
cờ đã bật              18
  kết thúc vì KILL      11      ← mức thật sự bị quét
    đã kịp vào lệnh      7
    KILL MÀ HỤT          4      ← con số cần so với v1
  chết vì RSIOUT         5
  chết vì NEWLEVEL       2
```

`flagBuyUsed` bật khi có lệnh vào trong cờ đó; lúc cờ tắt với lý do `KILL` thì cộng vào `đã kịp vào lệnh`. Nó cũng chính là biến `oneTradePerFlag` đọc ở §5 điều 5 — một biến, hai công dụng. Cùng một khoảng chart, cùng tầng M5, chỉ khác tầng vào lệnh — so đúng dòng **KILL MÀ HỤT**. Đó là lý do đổi sang RSI(2) nên phải đo, không tin suông.

---

## 8. File strategy

Khung execution bê từ `pine/rsi2_ema_swing_strategy.pine`: sizing theo `riskPct`, guard `minSlTicks`, alert JSON (thêm trường `"setup":"KILLPEAK"`).

Một chỗ **đơn giản hơn** `rsi2_divergence`: ở đó TP là bội số R nên phải huỷ-rồi-đặt-lại `strategy.exit` để lấy R đúng từ giá khớp thật; ở đây SL và TP đều là **mức giá cố định**, đặt một lần là xong.

Đánh đổi còn lại, ghi trong header và không xử lý: tín hiệu ở close, lệnh khớp ở open nến sau, nên RR thật lệch chút so với RR đã qua cửa `minRR`. Chặn thêm một lớp nữa chỉ làm rối.

Bảng của file strategy gọn hơn: bỏ phần swing chi tiết, giữ trạng thái M5 + bảng đếm.

---

## 9. Inputs

```
Bối cảnh (HTF)   htfTf="5"  ctxLen=14  ctxHi=70  ctxMid=50  ctxLo=30
Swing (chart)    fastLen=2  fHi=90  fLo=10
Vào lệnh         enableBuy=true  enableSell=true  hlMarginAtr=0.0
                 requireSwing2AfterFlag=true  oneTradePerFlag=true
Rủi ro           atrLen=14  slAtrMult=0.2  minRR=1.0  maxRR=0.0
Hiển thị         showCtx  showSwings  showZigzag  showSignals  showRejected
                 showTable  showCounters
Chỉ strategy     riskPct=1.0  minSlTicks=10
```

`maxRR = 0` nghĩa là không chặn trên. `hlMarginAtr = 0` nghĩa là cao hơn đúng 1 tick cũng tính.

---

## 10. Không repaint

- `ctxRsi` là RSI của nến M5 **đã đóng** — không bao giờ sửa lại.
- Mọi luật swing chỉ đọc dữ liệu nến đã đóng; swing chỉ được biết khi leg kết thúc.
- Label/line vẽ tại nến xác nhận và không bao giờ dịch.
- Thứ duy nhất đổi trong nến đang chạy: `runHigh`/`runLow`, kiểm tra chạm mức, và bảng. Tín hiệu chỉ chốt ở close.
- Warm-up: chưa đủ `ctxLen`/`fastLen`/`atrLen` thì `na` → bỏ nến.

---

## 11. Kiểm chứng

Máy này **không compile được Pine**. Làm được ba việc, và chỉ ba việc đó:

1. Static check như các lần trước: cân ngoặc, không tab, chuỗi cân, nối dòng đúng luật thụt lề, grep khối execution.
2. Dựng lại cả hai máy trạng thái bằng Python trong scratchpad trên dữ liệu tổng hợp, test các bất biến: hai cờ không bao giờ cùng bật (§3.4) · cờ tắt đúng ba đường · `killHigh` đúng bằng highest high của đoạn kể cả phần seed · thứ tự chốt-trước-huỷ-sau ở nến nhảy kép (§3.3) · luật "swing 2 sau cờ" · `rr` và bộ đếm. Script này là đồ vứt, **không** vào repo.
3. Đọc soát tay.

**Hình 1 của tài liệu nguồn không dùng làm test vector được.** Các số trong đó (102.38 → 103.26, BUY 103.91, R:R 9.3) sinh từ định nghĩa "đợt" đã bị thay bằng leg xen kẽ ở §4.1. Phải tự dựng bộ dữ liệu tổng hợp mới làm mốc đối chiếu.

Compile thật và test tay trên TradingView là việc của người dùng, sau khi giao file.

---

## 12. Ngoài phạm vi

- Port Python (`rsi_fvg/strategies/kill_peak.py`), đăng ký `registry.py`, tests, grid optimizer — làm sau khi luật ổn định qua test tay. Port trước rồi sửa luật là làm hai lần.
- Luật hết hạn cờ theo số nến và luật huỷ theo cấu trúc giá — đã cân nhắc và loại.
- Chế độ swing theo "đợt" — đã loại ở §4.1.
