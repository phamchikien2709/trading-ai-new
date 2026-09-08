# RSI2 Swing + EMA Trend — Strategy, Generic Optimizer — Design Spec

**Ngày:** 2026-09-08
**Trạng thái:** Đã duyệt thiết kế
**Kế thừa:** `2026-09-08-rsi2-swing-backtest-optimizer-design.md` (cấu trúc swing RSI2 §2.2, engine §2.5, metrics §3, đánh giá/khuyến nghị §4.2–4.3, export §5) và `2026-09-08-rsi-fvg-pullback-strategy-design.md` §2.6–2.8. Spec này mô tả (1) strategy mới và (2) việc tổng quát hoá optimizer để nhận nhiều strategy.

---

## 1. Mục tiêu

1. Strategy **RSI2 Swing + EMA Trend**: vào lệnh tại mỗi swing xác nhận của RSI(2) 90/10, lọc bằng xu hướng EMA 20/100. Có bản Pine để test tay và plugin Python để backtest/grid.
2. Optimizer/export/CLI dùng **strategy adapter** thay cho tham số hardcode của RSI2-swing, để strategy thứ ba trở đi chỉ cần một file. Kết quả của RSI2-swing hiện tại phải tái lập không đổi.
3. Chạy grid 384 combo/TF trên XAUUSDc M5/M15/H1, risk 1%, xuất báo cáo như hiện có.

---

## 2. Strategy `rsi2_ema_swing`

### 2.1 Indicator
- `rsi_fast = RSI(rsi_fast)` Wilder, mặc định 2; mốc `fast_hi/fast_lo` = 90/10. Cross và cấu trúc swing **dùng lại** `cross_up/cross_down/swing_structure` của `rsi2_swing.py` (spec RSI2 §2.2: đoạn HIGH/LOW xen kẽ, bar biên thuộc cả hai đoạn, swing xác nhận khi đoạn kết thúc).
- `ema_fast = EMA(ema_fast)`, `ema_slow = EMA(ema_slow)` trên close, mặc định 20/100. EMA seed = giá close đầu tiên, `α = 2/(n+1)` (khớp `ta.ema` Pine và `iMA` MODE_EMA MT5 sau warm-up; parity so sánh từ bar `5×ema_slow` trở đi).
- `ATR(14)` Wilder.

### 2.2 Tín hiệu (không có state machine chờ)
Tại bar `t`:
- **BUY** nếu `swing low xác nhận tại t` (RSI2 cross up `fast_hi` kết thúc đoạn LOW) **và** `ema_fast[t] > ema_slow[t]`:
  `sl = swing_low − atr_mult × ATR[t]`, `ref_price = close[t]`, `swing_price = swing_low`, `bars_in_wait = t − seg_start` (độ dài đoạn LOW), `variant = "EMASWING"`, `anchor_bar = seg_start`.
- **SELL** nếu `swing high xác nhận tại t` **và** `ema_fast[t] < ema_slow[t]`: `sl = swing_high + atr_mult × ATR[t]`.
- `ema_fast == ema_slow` → không tín hiệu. NaN ở RSI/EMA/ATR → bỏ bar.
- Mỗi swing đúng chiều là một tín hiệu; việc đang có lệnh → `blocked` là của engine (hedge: tối đa 1 lệnh/chiều). Không look-ahead: chỉ dùng dữ liệu ≤ `t`.
- Fill open nến sau, TP = fill ± R × risk, mọi quy tắc engine kế thừa nguyên (kể cả ruin floor, capped/oversized, min-SL filter, HTF gate tuỳ chọn).

### 2.3 Params
```
Rsi2EmaParams:
  rsi_fast=2, fast_hi=90.0, fast_lo=10.0
  ema_fast=20, ema_slow=100
  atr_len=14, atr_mult=1.5
  htf_seconds=0, htf_rsi_len=14, htf_level=50.0   # cổng H1 tuỳ chọn, cùng semantics rsi2_swing
```
Mặc định run: `tp_r = 8.0`, `risk_pct = 1.0`, `concurrency = hedge`.

### 2.4 Pine `pine/rsi2_ema_swing_strategy.pine`
Cùng khung với `rsi2_swing_strategy.pine`: inputs (RSI nhanh + mốc, EMA nhanh/chậm, ATR len/mult, TP R, risk %, enable buy/sell, block opposite, min SL ticks, H1 filter), khối cấu trúc swing giữ nguyên, **bỏ** state machine RSI14, khối execution: khi `swingLowConf and emaFast > emaSlow` → entry BUY với SL/TP như trên (SELL đối xứng), cơ chế re-arm TP đúng R và nhãn `blocked` giữ nguyên. Vẽ 2 EMA, marker swing, zigzag, SL/TP lệnh mở, bảng trạng thái (RSI, EMA fast/slow, đoạn hiện tại). Mặc định input = §2.3.

---

## 3. Optimizer tổng quát (`rsi_fvg/backtest/optimize.py`)

### 3.1 Strategy adapter
```
class StrategyAdapter(Protocol):
    name: str                          # "rsi2_swing" | "rsi2_ema_swing"
    key_cols: tuple[str, ...]          # trục grid, KHÔNG gồm tf và tp_r
    robust_axes: tuple[str, str]       # ("tp_r", "atr_mult")
    default_axes: dict[str, tuple]     # giá trị mặc định mỗi trục
    default_tp_r: tuple[float, ...]
    def make_params(self, base, **axis_values) -> params
    def run_strategy(self, bars, params) -> list[Signal]
    def base_params(self, **overrides) -> params   # từ CLI run-level (htf_seconds, ...)
```
- Adapter `rsi2_swing`: `key_cols = ("rsi_fast","ob","os","f_hi","f_lo","atr_mult")`, trục `rsi_fast`, `rsi_slow_levels` (→ ob/os), `rsi_fast_levels` (→ f_hi/f_lo), `atr_mult`. Trục dạng cặp được khai báo là một trục có giá trị tuple và **expand** ra hai cột.
- Adapter `rsi2_ema_swing`: `key_cols = ("rsi_fast","f_hi","f_lo","ema_fast","ema_slow","atr_mult")`; trục `rsi_fast ∈ {2,3,5}`, `rsi_fast_levels ∈ {(90,10),(95,5)}`, `ema ∈ {(20,100),(20,200),(50,200),(10,50)}`, `atr_mult ∈ {1,1.5,2,3}`; `default_tp_r = (2,4,6,8)` → 384 combo/TF.
- Registry `STRATEGIES = {"rsi2_swing": ..., "rsi2_ema_swing": ...}` trong `rsi_fvg/strategies/registry.py`.

### 3.2 GridSpec & run_optimization
- `GridSpec(axes: dict[str, tuple], tp_r: tuple[float, ...])`; `size()` = tích các trục × len(tp_r). Thứ tự lặp: tích Descartes các trục (signal tính một lần) → `tp_r` (engine mỗi giá trị).
- `run_optimization(strategy, bars_by_tf, spec_by_tf, grid, base, costs, sizing, concurrency, is_frac, min_sl_spread_mult, progress)`; cột output: `tf` + `key_cols` + `tp_r` + như hiện có.
- `add_robustness` lân cận: cùng mọi key col trừ `robust_axes[1]`, khoảng cách index ≤ 1 trên hai `robust_axes`. `compute_flags`, `recommend` không đổi logic; `recommend()["params"]` gồm `tf` + key_cols + `tp_r`.
- **Tái lập**: với adapter `rsi2_swing` và grid mặc định, `grid.csv` phải khớp hàm cũ trên fixture synthetic (test hồi quy so DataFrame).

### 3.3 Export & CLI
- Export: header Grid = `tf` + key_cols + `tp_r` + metrics; heatmap panel nhóm theo `key_cols` trừ `atr_mult`, tiêu đề = `"k=v · k=v"`; Recommendation hiển thị mọi key col.
- `scripts/optimize.py --strategy {rsi2_swing,rsi2_ema_swing} --tf ... --axis <name>=<v1>,<v2>,... (lặp) --tp ... --risk --concurrency --min-sl-mult --htf --is-frac --data-dir --out --offline`. Cặp viết `a/b`. Trục không nêu → giá trị mặc định của adapter. Output `results/<strategy>/<timestamp>/`.
- `scripts/run_rsi2_swing.py` giữ cờ cũ, gọi vào core mới (hành vi và output không đổi).

---

## 4. Runs

| Run | Lệnh | Ghi chú |
|---|---|---|
| 1 | `optimize.py --strategy rsi2_ema_swing --tf M5 M15 H1 --risk 1` | grid mặc định 384/TF |
| 2 | như 1 + `--htf 3600 --tf M5` | so tác dụng cổng H1 |

Báo cáo: `=== Recommendation ===`, top-5 mỗi TF, số combo cháy, cờ; xlsx/html như hiện có. Không bình luận "tốt/xấu" ngoài con số và cờ.

---

## 5. Testing

- `test_rsi2_ema_swing.py`: EMA khớp tham chiếu tính tay (5–10 bar); BUY tại swing low khi EMA fast > slow, không BUY khi ≤; SELL mirror; `bars_in_wait`/`anchor_bar` = đoạn swing; NaN prefix; prefix-invariance (look-ahead) trên random bars; HTF gate tắt/bật.
- `test_optimize.py`: GridSpec size với trục cặp; **hồi quy** adapter `rsi2_swing` vs kết quả cũ (fixture 4 combo, so cột chính bằng `assert_frame_equal`); adapter mới chạy grid nhỏ; robustness với `robust_axes`; `recommend` params gồm đủ key cols.
- `test_export.py`: header generic cho cả 2 adapter; heatmap panel với 5 key cols.
- `test_cli.py`: `optimize.py` smoke cho cả 2 strategy trên parquet synthetic; `run_rsi2_swing.py` smoke giữ nguyên.
- Pine: không compile được ở đây; người dùng paste và báo lỗi.

---

## 6. Quyết định đã chốt

| Câu hỏi | Quyết định |
|---|---|
| Phạm vi | Pine + Python backtest/grid |
| SL/TP | SL = swing ∓ ATR×k (k=1.5), TP theo R (mặc định 8R), risk 1% |
| Grid | EMA pairs, ATR mult, TP R, RSI nhanh + mốc → 384/TF |
| Kiến trúc | Strategy adapter + registry; optimizer/export/CLI generic; CLI cũ giữ tương thích |
| Ngoài phạm vi | lọc giá vs EMA, trailing, session, EA/live |
