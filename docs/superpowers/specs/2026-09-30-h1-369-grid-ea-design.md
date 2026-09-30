# H1 369 Grid EA — design

EA MQL5 `mql5/Experts/H1_369_Grid_EA.mq5`, cho tài khoản MT5 cent (XAUUSDc), spread khoảng 0.2 giá.

## Quy tắc

- **Mốc số 9**: giá chia hết cho 9 (digital root = 9, ví dụ 4113).
- **Mỗi khi nến H1 mới mở** (phát hiện qua `iTime(H1, 0)` đổi):
  1. Xoá tất cả lệnh chờ của EA (lọc theo symbol + magic).
  2. Đọc trend từ nến H1 đã đóng (shift 1): RSI(14), EMA9 của RSI (`iMA` MODE_EMA trên handle RSI) và WMA45 của RSI (`iMA` MODE_LWMA). EMA > WMA là BULLISH, EMA < WMA là BEARISH. Nếu hai đường bằng nhau hoặc dữ liệu chưa sẵn sàng thì chờ tick sau.
  3. Tính mốc từ Open của H1 mới: `S1 = floor(Open/9)*9`, `R1 = S1 + 9`, `S2 = S1 - 9`, `S3 = S1 - 18`, `R2 = R1 + 9`, `R3 = R1 + 18`.
  4. Đặt 3 lệnh limit theo trend:
     - BULLISH: Buy Limit tại S1/S2/S3 + 0.2, TP = R1 − 0.2
     - BEARISH: Sell Limit tại R1/R2/R3 − 0.2, TP = S1 + 0.2
- Lệnh đã khớp giữ nguyên TP, EA không sửa.
- Không SL, không cắt lỗ theo equity.
- Nếu một mức limit sát hoặc vượt giá (khoảng cách nhỏ hơn stops level) thì bỏ mức đó và ghi log.

## Input

| Input | Mặc định | Ý nghĩa |
|---|---|---|
| InpLot | 0.1 | lot mỗi lệnh (chuẩn hoá theo min/max/step) |
| InpStep | 9 | bước mốc |
| InpLevels | 3 | số lệnh limit mỗi giờ |
| InpOffset | 0.2 | offset spread |
| InpTpMode | R1 chung | hoặc "mốc ngay trên/dưới từng lệnh" |
| InpLevelTf | H1 | khung lấy Open và reset lệnh |
| InpPlaceOnStart | true | đặt lệnh ngay khi gắn EA theo Open của giờ hiện tại |
| InpMaxPositions | 6 | lệnh mở tối đa của EA; lệnh mở + limit mới không vượt (0 = không giới hạn) |
| InpMagic | 369369 | magic number |
| InpTrendTf / RSI / EMA / WMA | H1 / 14 / 9 / 45 | filter trend |

## Kiểm thử

- Đã compile bằng MetaEditor: 0 lỗi, 0 cảnh báo.
- Người dùng tự chạy Strategy Tester (XAUUSDc, "Every tick based on real ticks"), sau đó chạy trên tài khoản cent. Claude không gắn EA và không đặt lệnh trên tài khoản thật.
- EMA trong MT5 khởi tạo khác một chút so với `ta.ema` của TradingView, nên trend có thể lệch với indicator Pine ở vài nến đầu lịch sử; sau khi đủ dữ liệu thì hội tụ.
