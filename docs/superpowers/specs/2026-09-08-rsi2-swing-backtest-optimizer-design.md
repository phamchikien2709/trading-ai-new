# RSI2 Swing Pullback — Python Backtest, Optimizer & Export — Design Spec

**Ngày:** 2026-09-08
**Trạng thái:** Đã duyệt thiết kế
**Kế thừa:** `2026-09-08-rsi-fvg-pullback-strategy-design.md` §3 (kiến trúc Python), §2.6–2.8 (fill/SL/TP/sizing/concurrency). Spec này chỉ mô tả phần **khác** hoặc **thêm**.

---

## 1. Mục tiêu

1. Backtest strategy **RSI2 Swing Pullback** (bản Pine `pine/rsi2_swing_strategy.pine`) trên data XAUUSDc M5/M15/H1 kéo từ MT5, vốn 10.000 USD, risk 5%/lệnh.
2. Quét grid tham số, đánh giá theo IS/OOS và độ ổn định lân cận, **tự động đưa ra bộ tham số khuyến nghị** kèm lý do.
3. Export chuyên nghiệp: 1 workbook Excel + 1 báo cáo HTML tự chứa.

Hạ tầng (indicators, engine, metrics, data loader, runner) dùng chung với strategy RSI-FVG theo plan Phase 1; strategy là module cắm vào cùng interface `run_strategy(bars, params) -> list[Signal]`.

---

## 2. Logic strategy (port từng dòng từ Pine)

### 2.1 Indicator
- `rsi_slow = RSI(14)` Wilder; mốc `ob = 75`, `os = 25`.
- `rsi_fast = RSI(2)` Wilder; mốc `f_hi = 90`, `f_lo = 10`.
- `ATR(14)` Wilder.
- Cross: `f_up[t] = rsi_fast[t-1] <= f_hi < rsi_fast[t]`; `f_dn[t] = rsi_fast[t-1] >= f_lo > rsi_fast[t]`; `s_up`, `s_dn` tương tự với `ob`/`os`.

### 2.2 Cấu trúc swing RSI2 (luôn chạy, độc lập với lệnh)
- `seg ∈ {0: chưa xác định, +1: HIGH, −1: LOW}`.
- Mỗi bar: nếu `seg=+1` → `seg_high = max(seg_high, high[t])` (ghi bar); nếu `seg=−1` → `seg_low = min(seg_low, low[t])`.
- `f_up[t]`: nếu `seg=−1` → **swing low xác nhận** = `seg_low`; rồi `seg=+1`, `seg_high = high[t]`.
- `f_dn[t]`: nếu `seg=+1` → **swing high xác nhận** = `seg_high`; rồi `seg=−1`, `seg_low = low[t]`.
- Bar biên thuộc cả hai đoạn liền kề. Swing high/low xen kẽ theo cấu trúc.

### 2.3 State machine BUY (SELL đối xứng)

| Trạng thái | Sự kiện tại bar `t` | → |
|---|---|---|
| IDLE | `s_up` | ARMED, `anchor = t` |
| ARMED / TRACKING | `s_up` | ARMED, `anchor = t` (reset, bỏ đoạn đang theo) |
| ARMED / TRACKING | `max_wait > 0` và `t − anchor > max_wait` | IDLE |
| ARMED | `f_dn` | TRACKING, `run_low = low[t]` |
| TRACKING | mỗi bar | `run_low = min(run_low, low[t])` |
| TRACKING | `f_up` | **Signal BUY**: `sl = run_low − atr_mult × ATR[t]`, `ref_price = close[t]`, `swing_price = run_low`, `bars_since_flag = t − anchor` → IDLE |

Thứ tự ưu tiên trong một bar: re-cross → hết hạn → chuyển trạng thái/trigger. SELL: `s_dn` → ARMED; `f_up` → TRACKING với `run_high`; `f_dn` → Signal SELL, `sl = run_high + atr_mult × ATR[t]`.

Một `s_up` = tối đa một Signal. State machine không biết vị thế; `blocked`/`rejected_*` là việc của engine (kế thừa).

### 2.4 Params

```
Rsi2SwingParams:
  rsi_slow=14, ob=75.0, os=25.0
  rsi_fast=2,  f_hi=90.0, f_lo=10.0
  atr_len=14,  atr_mult=1.0
  max_wait=0
```
`Signal` kế thừa dataclass Phase 1, thêm trường tùy chọn `swing_price: float | None` (dùng `fvg_zone=None, pivot_price=None`; trường `variant` = `"SWING"`).

### 2.5 Fill / SL / TP / sizing / chi phí / concurrency
Y nguyên spec RSI-FVG §2.6–2.8. Mặc định lần này: `risk_pct = 5.0`, `tp_r = 2.0`, `concurrency = hedge` (có `single` để so với Pine).

---

## 3. Metrics bổ sung (thêm vào `metrics.compute_metrics`)

| Key | Định nghĩa |
|---|---|
| `avg_win_r`, `avg_loss_r` | trung bình R của lệnh thắng / thua |
| `expectancy_usd` | `net_pnl / n_trades` |
| `sortino_daily` | mean/downside-std lợi nhuận ngày × √252 |
| `calmar` | `cagr / max_dd_pct` (0 nếu DD = 0) |
| `max_consec_losses` | chuỗi thua dài nhất |
| `time_in_market_pct` | % bar có ≥1 lệnh mở |
| `monthly_returns` | DataFrame năm × tháng, % thay đổi equity (không nằm trong dict phẳng; trả riêng qua `monthly_table(equity)`) |

---

## 4. Optimizer (`rsi_fvg/backtest/optimize.py`)

### 4.1 Grid
```
tp_r      ∈ {1, 1.5, 2, 3, 4}
atr_mult  ∈ {0, 0.5, 1, 1.5, 2}
(ob, os)  ∈ {(70,30), (75,25), (80,20)}
(f_hi,f_lo) ∈ {(85,15), (90,10), (95,5)}
```
225 combo/TF × 3 TF = 675 backtest. Tính signal **một lần** cho mỗi bộ (ob/os, f_hi/f_lo, atr_mult) → engine chạy cho từng `tp_r`. (ATR mult ảnh hưởng SL nên nằm trong signal; TP chỉ ở engine.) → 45 lần `run_strategy` + 225 lần engine mỗi TF.

### 4.2 Đánh giá
- **IS/OOS**: chia theo thời gian, IS = 70% đầu, OOS = 30% cuối. Backtest chạy trên toàn bộ data; metrics tính riêng cho lệnh có `entry_time` trước/sau mốc chia. Không tối ưu lại trên OOS.
- **Xếp hạng chính**: `is_expectancy_r` (avg R) với điều kiện `is_n_trades ≥ 30`. Cột OOS luôn hiển thị cạnh.
- **Robustness score**: với mỗi combo, lấy các combo lân cận trong grid (±1 bước ở `tp_r` và `atr_mult`, cùng bộ RSI) → `robust_r = median(is_avg_r của lân cận)`; `robust_ratio = robust_r / is_avg_r` (kẹp [0, 1.5]). Đỉnh nhọn có ratio thấp.
- **Cờ**: `n<30`, `oos_sign_flip` (IS > 0 nhưng OOS < 0), `buy_sell_imbalance` (tỉ lệ > 2), `oversized_share > 10%` (nhiều lệnh dùng min-lot vượt risk).

### 4.3 Khuyến nghị tự động
1. Lọc combo: `is_n_trades ≥ 30`, `is_avg_r > 0`, `oos_avg_r > 0`, không cờ `oversized`.
2. Điểm = `0.5 × oos_avg_r + 0.3 × robust_r + 0.2 × is_avg_r` (chuẩn hóa z-score trong TF).
3. Chọn top-1 mỗi TF; nếu không combo nào qua lọc → ghi rõ "không có bộ tham số đáng tin trên TF này" thay vì gợi ý ép.
4. Lý do in kèm: n lệnh IS/OOS, avg R hai bên, robust ratio, DD, win rate, BUY/SELL split.

Đây là nội dung mục **Recommendation** trong cả xlsx và html.

---

## 5. Export (`rsi_fvg/backtest/export.py`)

Thư mục `results/rsi2_swing/<YYYYMMDD_HHMMSS>/`.

### 5.1 `report_<symbol>.xlsx` (openpyxl)
| Sheet | Nội dung |
|---|---|
| `Summary` | Khuyến nghị mỗi TF + key stats; cấu hình chạy (symbol, TF, data range, vốn, risk, chi phí, concurrency) |
| `Grid` | 675 dòng: tf, ob, os, f_hi, f_lo, atr_mult, tp_r, metrics đầy đủ, is_*, oos_*, robust_*, flags. Conditional formatting màu theo `oos_avg_r`. Freeze header, autofilter |
| `Trades_<TF>` | Trade log đầy đủ của combo khuyến nghị mỗi TF (cột như Phase 1 + `swing_price`, `bars_since_flag`) |
| `Monthly_<TF>` | Bảng năm × tháng %, tô màu xanh/đỏ |
| `Equity_<TF>` | time, equity, drawdown của combo khuyến nghị |
| `Params` | Toàn bộ grid values + cost/sizing params + version code (git hash) |

### 5.2 `report_<symbol>.html` (Plotly, `include_plotlyjs="cdn"` để nhẹ; có tùy chọn `--offline` nhúng js)
Sections: (1) Recommendation; (2) Equity + drawdown cho combo khuyến nghị mỗi TF; (3) Phân phối R; (4) Heatmap `tp_r × atr_mult` cho từng (RSI14, RSI2) và TF; (5) Scatter IS avg R vs OOS avg R, điểm tô theo n_trades; (6) Top-10 table; (7) Warnings.

### 5.3 Vẫn giữ `summary.csv` + `trades_*.csv` cho máy đọc.

---

## 6. CLI

```
python scripts/run_rsi2_swing.py [--tf M5 M15 H1] [--risk 5] [--concurrency hedge|single]
                                 [--tp 1 1.5 2 3 4] [--atr-mult 0 0.5 1 1.5 2]
                                 [--rsi14 70/30 75/25 80/20] [--rsi2 85/15 90/10 95/5]
                                 [--max-wait 0] [--offline]
```
Data lấy từ cache `data/XAUUSDc_<TF>.parquet` (kéo bằng `scripts/fetch_data.py` nếu thiếu).

---

## 7. Cấu trúc file (phần thêm so với plan Phase 1)

```
rsi_fvg/strategies/__init__.py
rsi_fvg/strategies/rsi2_swing.py       # Rsi2SwingParams, SwingTracker, run_strategy
rsi_fvg/backtest/optimize.py           # build_grid, run_optimization, robustness, recommend
rsi_fvg/backtest/export.py             # write_xlsx, write_html
scripts/run_rsi2_swing.py
tests/test_rsi2_swing.py, tests/test_optimize.py, tests/test_export.py
```
`rsi_fvg/strategy.py` (RSI-FVG) được dời vào `rsi_fvg/strategies/rsi_fvg.py`; `Signal`, `Direction` dời ra `rsi_fvg/signals.py` để hai strategy dùng chung. Engine chỉ import từ `signals.py`.

Dependencies thêm: `openpyxl`, `plotly`.

---

## 8. Testing

- `test_rsi2_swing.py`: swing tracker (đoạn xen kẽ, bar biên thuộc hai đoạn, seg=0 trước cross đầu); từng dòng bảng 2.3 với RSI inject; `s_up` khi TRACKING → reset; `max_wait`; SELL mirror; smoke deterministic trên random data (sl < swing_price cho BUY).
- `test_optimize.py`: grid nhỏ (2×2×1×1) synthetic → đúng số dòng, IS+OOS = tổng, robust_r đúng median trên grid tay, recommend trả None khi không combo nào qua lọc.
- `test_export.py`: xlsx có đủ sheet tên đúng, `Grid` đúng số dòng; html tồn tại, chứa chuỗi "Recommendation" và div plotly.
- Parity với Pine: so tay 20 tín hiệu gần nhất trên chart TradingView (feed OANDA khác Exness nên chỉ so thời điểm và cấu trúc, không so giá).

---

## 9. Quyết định đã chốt

| Câu hỏi | Quyết định |
|---|---|
| Strategy | RSI2 Swing Pullback, port từ Pine đã chạy |
| Data | XAUUSDc từ MT5 (Exness), M5/M15/H1, cache parquet |
| Vốn / risk | 10.000 USD, 5%/lệnh, TP mặc định 2R |
| Export | Excel workbook + HTML report (Plotly) + CSV |
| Tham số quét | TP_R, ATR mult, mốc RSI14, mốc RSI2 (225 combo/TF) |
| Chống overfit | IS 70 / OOS 30, robustness lân cận, lọc n ≥ 30, khuyến nghị theo cao nguyên |
| Kiến trúc | Dùng chung engine Phase 1; strategy là plugin |
