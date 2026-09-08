# RSI-FVG Pullback Strategy — Design Spec

**Ngày:** 2026-09-08
**Trạng thái:** Đã duyệt thiết kế, chờ implementation plan
**Deliverable:** (1) Python backtest, (2) Pine Script strategy, (3) EA MQL5, (4) Python live bot kết nối MT5

---

## 1. Mục tiêu

Xây dựng và đánh giá chiến lược "RSI overbought/oversold → pullback → xác nhận vào lệnh" trên XAUUSD (M5/M15/H1), với 3 phương án vào lệnh và 5 mức TP để so sánh. Cùng một bộ logic phải chạy được trên 4 nền tảng và cho ra cùng tín hiệu trên cùng data.

**Nguyên tắc thiết kế cốt lõi:** module `strategy.py` là nguồn sự thật duy nhất. Backtest và live bot Python gọi đúng một hàm. EA MQL5 và Pine là bản port từng dòng, có kiểm tra parity.

---

## 2. Đặc tả logic chiến lược

### 2.1 Indicator

| Indicator | Định nghĩa | Ghi chú parity |
|---|---|---|
| RSI(14) | Wilder smoothing | Khớp `ta.rsi` (Pine) và `iRSI` (MT5) |
| ATR(14) | Wilder RMA của True Range | Khớp `ta.atr` (Pine). **MT5 `iATR` dùng SMA → EA phải tự tính Wilder** |
| Màu nến | xanh: `close > open`; đỏ: `close < open`; doji: không màu | Doji phá chuỗi 3 nến |
| Pivot high/low | `high[i]` cao hơn `pivot_len` nến mỗi bên; xác nhận tại `i + pivot_len` | `pivot_len` mặc định 2. Khớp `ta.pivothigh(len,len)` |

Tham số RSI: overbought `75`, oversold `25`, mid-high `60`, mid-low `40`.

### 2.2 FVG

Phát hiện tại close của nến C3 = bar `t`; C2 = `t-1`; C1 = `t-2`.

- **FVG bull:** C1, C2, C3 đều xanh **và** `high[t-2] < low[t]`. Zone = `[high[t-2], low[t]]`.
- **FVG bear:** C1, C2, C3 đều đỏ **và** `low[t-2] > high[t]`. Zone = `[high[t], low[t-2]]`.

### 2.3 State machine (chiều BUY; SELL đối xứng)

Hai state machine BUY và SELL chạy độc lập, song song. Tất cả sự kiện đánh giá tại close bar `t`.

| Trạng thái | Sự kiện | Chuyển sang |
|---|---|---|
| IDLE | `RSI[t-1] ≤ 75` và `RSI[t] > 75` (cross up) | ARMED, `anchor = t` |
| ARMED | cross up 75 lần nữa | ARMED, `anchor = t` (reset) |
| ARMED | `RSI[t] < 60` | WAIT (cờ chờ-buy bật), `wait_start = t` |
| WAIT | cross up 75 lần nữa | ARMED, `anchor = t` (cờ xóa) |
| WAIT | entry trigger theo variant (2.4) | **phát Signal** → IDLE |
| WAIT | `max_wait_bars > 0` và `t − wait_start > max_wait_bars` | IDLE (hết hạn) |

Thứ tự ưu tiên khi nhiều sự kiện xảy ra cùng bar trong WAIT: re-cross 75 → hết hạn → entry trigger. Entry trigger chỉ được đánh giá từ nến **sau** nến chuyển ARMED→WAIT (tức `t > wait_start`).

**Quy tắc:** một lần cross up 75 → tối đa một Signal. State machine **không biết về vị thế**: khi trigger, nó luôn phát Signal và về IDLE. Việc có thực thi Signal hay không (đang có lệnh cùng chiều → bỏ qua, log `blocked`) là trách nhiệm của engine/bot. Điều này cho phép live bot chạy lại state machine từ đầu mỗi nến (replay) mà không cần lưu trạng thái.

`max_wait_bars` mặc định `0` (tắt) theo yêu cầu; có để backtest thử.

**SELL mirror:** cross down 25 (`RSI[t-1] ≥ 25` và `RSI[t] < 25`) → ARMED; `RSI[t] > 40` → WAIT; trigger đối xứng; SL = `max(high[anchor..t]) + atr_mult × ATR[t]`.

### 2.4 Entry trigger (chỉ đánh giá trong WAIT)

| Variant | BUY trigger tại bar `t` | SELL trigger |
|---|---|---|
| **A** — FVG | FVG bull phát hiện tại `t` | FVG bear tại `t` |
| **B** — RSI reclaim | `RSI[t-1] < 60` và `RSI[t] ≥ 60` | `RSI[t-1] > 40` và `RSI[t] ≤ 40` |
| **C** — Break pivot | `close[t] >` pivot high gần nhất đã xác nhận, có index `≥ anchor` | `close[t] <` pivot low gần nhất đã xác nhận, index `≥ anchor` |

Variant C: nếu chưa có pivot nào xác nhận trong `[anchor, t]` → không trigger.

### 2.5 Signal

```
Signal:
  direction     BUY | SELL
  variant       A | B | C
  signal_bar    t
  anchor_bar    anchor
  ref_price     close[t]
  sl_price      (2.6)
  bars_in_wait  t − wait_start
  fvg_zone      (lo, hi) nếu variant A, else None
  pivot_price   nếu variant C, else None
```

### 2.6 SL / TP / fill

- `SL_buy = min(low[anchor..t]) − atr_mult × ATR[t]`; `SL_sell = max(high[anchor..t]) + atr_mult × ATR[t]`. `atr_mult` mặc định `1.0`. `anchor` = bar cross-up 75 mới nhất — rộng hơn "từ đỉnh RSI", an toàn hơn, không đổi kết quả vì đáy pullback nằm sau đỉnh RSI.
- **Fill:** Signal tính tại close bar `t` → fill tại `open[t+1]`. Buy fill tại ask = `bid + spread`; Sell fill tại bid. Cả 4 nền tảng dùng quy ước này.
- **TP:** `TP = fill + R × (fill − SL)` với R ∈ {1, 1.5, 2, 3, 4}; mặc định 3. TP tính từ **giá fill thực**, không từ `ref_price`.
- **Kiểm tra SL/TP:** theo `high/low` mỗi nến. Buy: SL/TP chạm theo bid (candle gốc). Sell: chạm theo ask = bid + spread. Cùng nến chạm cả hai → **SL trước**. Nếu `open` đã gap qua SL/TP → fill tại `open`.
- Nếu SL nằm sai phía so với fill (ví dụ giá gap mạnh làm `fill ≤ SL_buy`) → không vào lệnh, log `rejected_invalid_sl`.
- Live: nếu `|fill − SL| < stops_level` của broker → không đặt lệnh, log `rejected_stops_level`.

### 2.7 Sizing & chi phí

- `lots = floor((equity × risk_pct) / (|fill − SL| × contract_size) / lot_step) × lot_step`, kẹp trong `[min_lot, max_lot]`. XAUUSD `contract_size = 100`. `risk_pct` mặc định 1%. Nếu lots tính ra `< min_lot` → dùng `min_lot` (rủi ro thực > risk_pct, ghi cờ `oversized` trong trade log).
- Chi phí (tham số): `spread_points`, `commission_per_lot_rt` USD, `slippage_points` (cộng vào bất lợi ở cả entry và exit).
- **Symbol spec (`point, digits, contract_size, min/max/step lot, stops_level`) đọc từ MT5 `symbol_info` lúc kéo data và lưu sidecar JSON cạnh parquet; backtest dùng spec đó.** Broker hiện tại (Exness cent): symbol `XAUUSDc`, `point = 0.001`, `contract_size = 1.0`, spread ~260 points. Config có fallback nếu không có sidecar.

### 2.8 Concurrency

- Mặc định `hedge`: tối đa 1 lệnh BUY + 1 lệnh SELL cùng lúc. Cần tài khoản MT5 hedging mode.
- `single`: tối đa 1 lệnh bất kể chiều; signal ngược chiều khi đang có lệnh → `blocked`. Dùng để so sánh với Pine (Pine không hedge).

### 2.9 Ngoài phạm vi (cố ý)

Filter phiên/giờ, filter tin, trailing stop, break-even, partial TP, max daily loss, exit theo RSI. Có thể thêm sau khi có số liệu baseline.

---

## 3. Kiến trúc Python

### 3.1 Cấu trúc thư mục

```
AI BOT TRADING NEW FLOW/
├── config/
│   ├── default.yaml            # symbol, TF list, strategy params, costs, sizing, engine
│   └── live.yaml               # symbol, tf, variant, tp_r, risk_pct, magic, enable_buy/sell, lookback_bars
├── rsi_fvg/
│   ├── __init__.py
│   ├── params.py               # StrategyParams, CostParams, SizingParams dataclasses + load_yaml
│   ├── indicators.py           # rsi_wilder, atr_wilder, candle_color, pivot_high, pivot_low (numpy)
│   ├── fvg.py                  # detect_fvg(o,h,l,c) → bull[], bear[], zone_lo[], zone_hi[]
│   ├── strategy.py             # DirectionStateMachine, Strategy.run(bars, params, variant) → list[Signal]
│   ├── sizing.py               # lots_for_risk(equity, risk_pct, sl_dist, spec)
│   ├── data/
│   │   ├── mt5_loader.py       # fetch(symbol, tf, start=None) → DataFrame; cache parquet
│   │   └── csv_loader.py
│   ├── backtest/
│   │   ├── engine.py           # run(bars, signals, params, tp_r, concurrency) → BacktestResult
│   │   ├── metrics.py          # compute(trades, equity) → dict
│   │   ├── report.py           # summary.csv/md, equity png, heatmap png
│   │   └── runner.py           # grid TF × variant × TP, IS/OOS split
│   └── live/
│       ├── mt5_broker.py       # wrapper MetaTrader5
│       └── bot.py              # poll loop
├── scripts/
│   ├── fetch_data.py
│   ├── run_backtest.py
│   ├── run_live.py
│   └── compare_mt5.py          # parity Python ↔ EA debug CSV
├── pine/rsi_fvg_strategy.pine
├── mql5/RsiFvgEA.mq5
├── tests/
├── data/                       # parquet cache (gitignore)
├── results/                    # output backtest (gitignore)
├── logs/                       # live journal (gitignore)
├── docs/superpowers/specs/
├── requirements.txt
└── README.md
```

### 3.2 Ranh giới module

| Module | Làm gì | Phụ thuộc | Không biết về |
|---|---|---|---|
| `indicators`, `fvg` | Tính mảng vectorized từ OHLC | numpy | strategy, vị thế |
| `strategy` | State machine → `list[Signal]` | indicators, fvg | vị thế, tiền, MT5, backtest |
| `sizing` | lots từ equity/risk/SL/spec | — | strategy |
| `backtest.engine` | Fill, exit, equity, trade log | strategy, sizing | MT5, plotting |
| `backtest.metrics/report` | Thống kê, file output | pandas, matplotlib | engine internals |
| `live.mt5_broker` | I/O với MT5 | MetaTrader5 | strategy |
| `live.bot` | Kết nối strategy ↔ broker | strategy, sizing, mt5_broker | backtest |

`Strategy.run(bars: OHLC arrays, params, variant) → list[Signal]` là hàm thuần, xác định, không side effect.

### 3.3 Engine — thứ tự xử lý mỗi bar `t`

1. Fill signal chờ từ bar `t-1` tại `open[t]` (+spread/slippage). Nếu đã có lệnh cùng chiều (hoặc bất kỳ lệnh nào trong mode `single`) → ghi `blocked`. Tính lots, TP từ fill thực, trừ commission.
2. Kiểm tra SL/TP cho lệnh đang mở theo `high[t]/low[t]` (kể cả lệnh vừa fill ở bước 1). Cùng nến chạm cả hai → SL. Gap qua → fill tại `open[t]`.
3. Ghi equity mark-to-market tại `close[t]`.
4. Signal của bar `t` (đã được `Strategy.run()` tính trước) trở thành signal chờ cho `t+1`.

Kết thúc data: lệnh còn mở đóng tại `close` cuối, `exit_reason = end`.

Equity ban đầu 10.000 USD (tham số). Sizing dùng equity tại thời điểm fill (compounding).

### 3.4 Trade log

Mỗi lệnh 1 dòng: `entry_time, exit_time, direction, variant, tp_r, entry_price, exit_price, sl_price, tp_price, lots, sl_dist, r_multiple, pnl_usd, commission, exit_reason (SL|TP|end), bars_held, bars_in_wait, anchor_time, oversized`. Signal bị `blocked` / `rejected_*` ghi bảng riêng `skipped_signals`.

### 3.5 Metrics

Tổng và tách BUY/SELL, theo năm, IS/OOS: `n_trades, win_rate, avg_r, expectancy_r, profit_factor, max_dd_usd, max_dd_pct, sharpe_daily, cagr, avg_bars_held, n_blocked`. Cảnh báo nếu `n_trades < 30`.

### 3.6 Runner & báo cáo

`python scripts/run_backtest.py --tf M5 M15 H1 --variant A B C --tp 1 1.5 2 3 4 [--concurrency hedge|single] [--max-wait-bars N]`

Output `results/<YYYYMMDD_HHMMSS>/`:
- `summary.csv` — 1 dòng / combo (45 mặc định) + metrics, có cột IS/OOS (split 80/20 theo thời gian)
- `trades_<TF>_<variant>_<R>R.csv`
- `equity_<TF>_<variant>.png` — 5 đường TP trên một chart
- `heatmap_<TF>.png` — expectancy R theo variant × TP
- `summary.md` — top 10 combo theo expectancy OOS, cảnh báo n_trades, lệch BUY/SELL

### 3.7 Data

`fetch_data.py --symbol XAUUSD --tf M5 M15 H1` kéo `copy_rates_from` lùi theo chunk 50.000 nến cho đến khi MT5 trả rỗng → `data/XAUUSD_<TF>.parquet` (cột `time, open, high, low, close, tick_volume, spread`). Cảnh báo nếu số nến trùng giới hạn *Max bars in chart* của terminal. Tham số `--start` để cắt.

### 3.8 Dependencies

`numpy, pandas, pyarrow, MetaTrader5, matplotlib, pyyaml, pytest`. Không dùng lib backtest ngoài.

---

## 4. Live

### 4.1 Cách tiếp cận chung: replay

Mỗi nến đóng → lấy `lookback_bars` (mặc định 2000) nến đã đóng → chạy state machine từ đầu → chỉ hành động nếu Signal có `signal_bar == index cuối`. Không lưu trạng thái giữa các nến. Áp dụng cho cả Python bot và EA.

### 4.2 Python bot

**`mt5_broker.py`:** `connect/ensure_connected` (retry), `get_closed_bars(symbol, tf, n)` (bỏ nến index 0 đang hình thành), `symbol_spec()` (point, digits, contract_size, volume_min/max/step, stops_level, filling_mode), `account_info()` (equity, margin_mode), `positions(magic, direction)`, `market_order(direction, lots, sl, tp, comment) → deal_price`, `modify_tp(ticket, tp)`.

**`bot.py`:**
1. Khởi động: kiểm tra `margin_mode`. Nếu không phải HEDGING và config có cả 2 chiều → cảnh báo và chuyển `concurrency = single`.
2. Poll mỗi 1s `time` của nến index 0; đổi → nến trước đã đóng.
3. `get_closed_bars` → `Strategy.run()` → Signal tại index cuối?
4. Có lệnh cùng chiều (theo magic) → log `blocked`. Không → `lots = sizing(...)`, kiểm tra `stops_level`, gửi market order với SL và TP tạm (từ ask hiện tại).
5. Đọc deal price → `TP = fill + R × (fill − SL)` → `modify_tp`.
6. Journal `logs/trades.jsonl`; log file; `--dry-run` chỉ in.

### 4.3 EA MQL5 (`RsiFvgEA.mq5`)

- **Inputs:** `Variant (enum A/B/C), TP_R, RiskPercent, RsiPeriod=14, Overbought=75, Oversold=25, MidHigh=60, MidLow=40, AtrPeriod=14, AtrMult=1.0, PivotLen=2, MaxWaitBars=0, Magic, EnableBuy, EnableSell, LookbackBars=2000, SlippagePoints, ExportDebug=false`.
- **OnTick:** chạy logic 1 lần khi `iTime(_Symbol,_Period,0)` đổi.
- **Indicator:** RSI qua `iRSI` handle + `CopyBuffer`. ATR **tự tính Wilder** từ TR (không dùng `iATR`).
- **State machine:** `RunStateMachine(dir, rsi[], atr[], rates[], variant) → Signal` — port từng dòng từ `strategy.py`, cùng tên biến.
- **Đặt lệnh:** `CTrade`; `NormalizeDouble(_Digits)`; kiểm tra `SYMBOL_TRADE_STOPS_LEVEL`; lots theo `SYMBOL_VOLUME_STEP/MIN/MAX`; sau fill đọc `POSITION_PRICE_OPEN` → `PositionModify` TP đúng R. Lọc theo `Magic + POSITION_TYPE`, tối đa 1 lệnh/chiều.
- **ExportDebug:** ghi CSV `time, rsi, atr, state_buy, state_sell, signal` mỗi nến (dùng trong Strategy Tester để parity).
- Comment lệnh: `RSIFVG_<variant>_<R>R`.

---

## 5. Pine Script (v6)

- `strategy("RSI-FVG Pullback", overlay=true, pyramiding=0, calc_on_every_tick=false, initial_capital=10000, commission_type=strategy.commission.cash_per_contract, commission_value=0.035, slippage=<input>)`. Fill mặc định open nến kế → khớp.
- **Inputs:** Variant, TP_R, Risk %, RSI/ATR period, 4 mốc RSI, ATR mult, Pivot len, Max wait bars, Enable Buy/Sell, Block opposite while in trade (mặc định true).
- **Logic:** `ta.rsi`, `ta.atr`, `ta.pivothigh/low(len,len)`; state machine bằng biến `var` mỗi chiều, đúng bảng 2.3.
- **Sizing:** `qty = strategy.equity × risk% / |close − SL|` (1 contract = 1 oz).
- **Exit đúng R:** lúc signal → `strategy.entry` + `strategy.exit(stop=SL, limit=TP_ước_tính)`. Nến sau khi khớp → gọi lại `strategy.exit` cùng id với `limit = avg_price + R × (avg_price − SL)`.
- **Lệch có chủ đích:** (1) không hedge → `Block opposite` bỏ qua signal ngược chiều; so với Python mode `single`. (2) không có spread → `slippage ≈ spread/2`.
- **Hiển thị:** `box.new` vùng FVG; `bgcolor` khi ARMED/WAIT; đường SL/TP lệnh mở; marker entry nhãn variant.
- **Alert:** `alert()` JSON `{symbol, tf, direction, variant, sl, tp_r, ref_price}`; `alertcondition` Buy/Sell.

---

## 6. Testing & parity

### 6.1 Unit test (pytest, synthetic, không cần MT5)

- `test_indicators.py` — RSI/ATR Wilder so với tính tay; pivot confirm đúng độ trễ; doji không màu.
- `test_fvg.py` — 3 xanh + gap ✓; 3 xanh không gap ✗; 2 xanh + doji ✗; gap nhưng lẫn đỏ ✗; bear mirror.
- `test_state_machine.py` — mỗi dòng bảng 2.3 một test; mỗi variant trigger; `max_wait_bars`; SL công thức; sau Signal về IDLE; SELL mirror; variant C không có pivot → không trigger.
- `test_engine.py` — fill open+spread; SL trước TP cùng nến; gap qua SL; `blocked` cùng chiều; hedge 2 chiều; `single` chặn ngược chiều; sizing rounding; commission; `r_multiple` đúng; đóng cuối data; `rejected_invalid_sl`.
- `test_metrics.py` — trade list biết trước → stats biết trước.

### 6.2 Integration (skip nếu MT5 không mở)

- `test_mt5_loader.py` — kéo 500 nến, schema đúng, time không trùng/thiếu.
- `test_mt5_broker.py` — connect, symbol_spec, get_closed_bars bỏ nến 0.

### 6.3 Parity

1. **Python ↔ MQL5 (bắt buộc):** chạy EA trong Strategy Tester với `ExportDebug=true` → `scripts/compare_mt5.py` so với Python trên cùng khoảng: RSI/ATR sai số `< 1e-6`, signal bar khớp 100%.
2. **Python engine ↔ MT5 Strategy Tester:** cùng data broker, so `n_trades, win_rate, pnl`; ghi con số lệch và nguyên nhân (spread thực vs cố định, mô phỏng tick).
3. **Python ↔ Pine:** không so được tự động (TV không nhập CSV, feed khác). Review code song song + spot-check thủ công 20 signal gần nhất nếu TV có feed đúng broker. Ghi giới hạn trong README.

### 6.4 Definition of done

- `pytest` xanh.
- Grid 45 combo chạy hết, `results/` đầy đủ, `summary.md` có nhận xét.
- EA compile 0 warning; parity 6.3.1 khớp.
- Bot Python `--dry-run` trên demo bắt được ≥ 1 nến đóng và in đúng trạng thái.
- Pine: người dùng paste vào TradingView, compile không lỗi (tôi không chạy được TV trực tiếp).
- README: cài đặt, kéo data, chạy backtest, chạy live, quy trình parity, giới hạn đã biết.

---

## 7. Quyết định đã chốt (tóm tắt)

| Câu hỏi | Quyết định |
|---|---|
| FVG | 3 nến cùng màu + wick gap |
| Chiều | Cả BUY và SELL, đối xứng |
| Symbol/TF | XAUUSD — M5, M15, H1 |
| Vòng đời cờ | 1 cross = 1 lệnh; cờ bật khi RSI < 60; xóa khi phát Signal; không hết hạn (tham số tắt) |
| Re-cross 75 khi cờ treo | Reset: anchor mới, cờ xóa |
| Entry variants | A FVG, B RSI reclaim 60, C break pivot pullback |
| TP | 1 / 1.5 / 2 / 3 / 4 R, mặc định 3 |
| Concurrency | 1 lệnh/chiều, hedge; mode `single` để so Pine |
| Sizing | % rủi ro/lệnh, mặc định 1% |
| Chi phí | Spread cố định + commission + slippage, tham số |
| Engine | Tự viết, event-driven, core dùng chung |
| Live | Cả EA MQL5 và Python bot, replay stateless |
| Pine | `strategy()` + alert, 1 file |
| Data | Tối đa broker cho phép, cache parquet |
| Môi trường | MT5 terminal đã login demo trên máy này |
