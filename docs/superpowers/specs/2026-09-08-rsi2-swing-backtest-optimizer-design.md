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

Bổ sung của engine (`run_backtest`):
- **Thứ tự exit trong 1 bar**: kiểm tra **open trước** — bar gap thẳng qua TP thì ăn TP dù range của nó cũng chạm SL. Chỉ khi open nằm giữa SL và TP mới xét intrabar, và ở đó SL thắng (giả định thận trọng, OHLC 1 bar không cho biết mức nào bị chạm trước).
- **Ruin floor** (`ruin_floor_pct`, mặc định 0.10): khi equity mark tại close của một bar tụt xuống ≤ 10% vốn ban đầu → đóng hết vị thế tại close đó với `exit_reason = "ruin"`, ngừng nhận fill, equity phẳng đến hết. `BacktestResult` có `ruined` / `ruin_time`. Không có nó, engine sizing trên số dư âm (`lots_for_risk` trả min-lot) và báo DD > 100%.
- **Sizing flags**: `lots_for_risk` trả `(lots, oversized, capped)`. `oversized` = bị nâng lên `min_lot` (risk **cao hơn** cấu hình); `capped` = bị chặn bởi `max_lot` (risk **thấp hơn** cấu hình). Cả hai đi vào trade log.
- **Sai lệch có chủ ý**: TP là limit fill nên **không** trừ slippage; SL và entry thì có.

### 2.6 Variants V1–V3 (thêm sau lần chạy grid đầu)

Bối cảnh: trên M5, SL của cấu trúc RSI(2) nằm quá sát giá (median $1.7 trên M1, $7.5 trên M15) và **mọi trục grid đều tốt dần về biên** — dấu hiệu tối ưu nằm ngoài grid. Ba biến thể dưới đây mở rộng vùng quét và thêm hai bộ lọc. Cả ba **mặc định TẮT** nên kết quả cũ tái lập nguyên trạng (grid mặc định vẫn 225 combo/TF).

**V1 — `rsi_fast` thành trục grid.** `GridSpec.rsi_fast: tuple[int, ...] = (2,)`, `size()` nhân thêm. Vòng lặp đặt `rsi_fast` **ngoài** (ob, os) nên signal vẫn tính một lần cho mỗi (rsi_fast, ob/os, f_hi/f_lo, atr_mult) và engine một lần cho mỗi `tp_r`. `KEY_COLS = [tf, rsi_fast, ob, os, f_hi, f_lo, atr_mult, tp_r]`; `ROBUST_KEYS` **có** `rsi_fast` — RSI(2) và RSI(5) cùng mốc là hai strategy khác nhau, không được gộp lân cận. `recommend()["params"]["rsi_fast"]` là `int`. Thử nghiệm: độ dài 5 là mức đầu tiên cho kết quả robust dương. CLI `--rsi-fast 2 5`.

**V2 — lọc khoảng cách SL tối thiểu theo bội spread.** `run_backtest(..., min_sl_spread_mult=0.0)`: tại thời điểm fill, sau khi có `sl_dist`, nếu `min_sl_spread_mult > 0` và `sl_dist < min_sl_spread_mult × spread` (spread theo giá = `costs.spread_points × spec.point`) → bỏ tín hiệu với lý do `rejected_min_sl` vào frame `skipped`, **không** mở vị thế. State machine không bị ảnh hưởng (flag đã bị tiêu thụ ngay ở bước trigger). Grid ghi `min_sl_mult` và `n_rejected_min_sl`. CLI `--min-sl-mult`. Pine: input `minSlTicks` "Min SL distance (ticks, 0 = off)", xử lý như `blocked`.

**V3 — cổng xu hướng RSI khung lớn.** `Rsi2SwingParams` thêm `htf_seconds = 0` (0 = tắt, 3600 = H1), `htf_rsi_len = 14`, `htf_level = 50.0`. `htf_rsi(bars, htf_seconds, period)`: gom bar theo `time // htf_seconds`; chuỗi close HTF = close **cuối** mỗi bucket; `rsi_wilder` trên chuỗi đó; **dịch một bucket** (bar trong bucket `b` đọc RSI của bucket `b−1`, tức bar HTF đã ĐÓNG); forward-fill về bar gốc; NaN trước bucket hoàn chỉnh đầu tiên. Nhờ vậy **không look-ahead** — có test prefix-invariance (`htf_rsi(bars[:k])[:k] == htf_rsi(bars)[:k]`). Cổng: khi `htf_seconds > 0`, BUY chỉ phát khi `htf[t] > htf_level`, SELL chỉ khi `htf[t] < htf_level`; NaN → trượt cổng. Trigger bị chặn **vẫn tiêu thụ flag** (state → IDLE, không Signal) — cùng ngữ nghĩa với `blocked`. Đây là công tắc mức run (đi theo `base`), **không** phải trục grid; grid ghi `htf_seconds`. CLI `--htf 3600`. Pine: `request.security(syminfo.tickerid, htfTf, ta.rsi(close, rsiSlowLen)[1], barmerge.gaps_off, barmerge.lookahead_on)` — idiom `[1]` + `lookahead_on` trả bar HTF đã đóng mà không repaint.

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
  - `is_max_dd_pct` / `oos_max_dd_pct` lấy từ **đường equity thật** cắt tại mốc chia (`dd = 1 - eq/eq.cummax()` trên đoạn đó, đỉnh reset ở đầu đoạn) — **không** dựng lại equity từ trade của đoạn rồi tính DD trên vốn ban đầu. Các cột còn lại (`n_trades`, `win_rate`, `avg_r`, `profit_factor`, `net_pnl`, `expectancy_usd`) vẫn là tổng theo trade trong đoạn.
- **Xếp hạng chính**: `is_expectancy_r` (avg R) với điều kiện `is_n_trades ≥ 30`. Cột OOS luôn hiển thị cạnh.
- **Robustness score**: với mỗi combo, lấy các combo lân cận trong grid (±1 bước ở `tp_r` và `atr_mult`, **cùng cả 4 mức RSI** `ob/os/f_hi/f_lo`) → `robust_r = median(is_avg_r của lân cận)`; `robust_ratio = robust_r / is_avg_r` (kẹp [0, 1.5]). Đỉnh nhọn có ratio thấp. Combo `ruined` bị loại khỏi pool lân cận và tự nhận `robust_r = 0`.
- **Cờ**: `ruined` (cháy tài khoản, xem §2.5), `n<30`, `oos_sign_flip` (IS > 0 nhưng OOS < 0), `buy_sell_imbalance` (tỉ lệ > 2), `oversized_share > 10%` (nhiều lệnh dùng min-lot vượt risk), `capped_share > 10%` (nhiều lệnh bị chặn bởi `max_lot` nên risk thực thấp hơn cấu hình), `grid_edge` (`tp_r` hoặc `atr_mult` nằm ở đầu/cuối grid — chưa thấy được đỉnh nào ở phía ngoài).

### 4.3 Khuyến nghị tự động
1. Lọc combo — phải **có lãi bằng tiền**, không chỉ dương R (107/675 combo của lần chạy đầu có `avg_r > 0` mà `net_pnl < 0`; bản M5 từng chọn lỗ $2,773 với DD 93.7%):
   `not ruined`, `is_n_trades ≥ 30`, `is_avg_r > 0`, `oos_avg_r > 0`, `oos_n_trades ≥ 10`,
   `net_pnl > 0`, `profit_factor > 1.0`, `max_dd_pct ≤ 0.50`, `oversized_share ≤ 0.10`, `capped_share ≤ 0.50`.
2. Điểm = `0.6 × z(is_avg_r) + 0.4 × z(robust_r)` (z-score trong TF). **OOS chỉ là cổng đậu/trượt** (`oos_avg_r > 0`, `oos_n_trades ≥ 10`), không tính điểm — cho OOS 50% trọng số chính là "tối ưu lại trên OOS" mà §4.2 cấm.
3. Chọn top-1 mỗi TF; nếu không combo nào qua lọc → ghi rõ "không có bộ tham số đáng tin trên TF này" thay vì gợi ý ép.
4. Lý do in kèm: `net_pnl`, `profit_factor`, `max_dd_pct`, n lệnh IS/OOS, avg R hai bên, robust_r, win rate, BUY/SELL split, `capped_share` (nếu > 0) và ghi chú `(grid edge)` khi combo được chọn nằm ở biên grid.

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
                                 [--rsi-fast 2] [--min-sl-mult 0] [--htf 0]
                                 [--max-wait 0] [--offline]
```
`--rsi-fast` (V1) là trục grid — nhiều giá trị nhân số combo. `--min-sl-mult` (V2) và `--htf` (V3, giây; 3600 = H1) là công tắc mức run, ghi vào `run_info` và mọi dòng grid.
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
