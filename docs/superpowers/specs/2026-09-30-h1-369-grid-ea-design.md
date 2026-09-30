# H1 369 Grid EA — design

EA MQL5 `mql5/Experts/H1_369_Grid_EA.mq5`, cho tài khoản MT5 cent (XAUUSDc), spread khoảng 0.2 giá.

## Quy tắc

- **Mốc số 9**: giá chia hết cho 9 (digital root = 9, ví dụ 4113).
- **Mỗi khi nến H1 mới mở** (phát hiện qua `iTime(H1, 0)` đổi):
  1. Xoá tất cả lệnh chờ của EA (lọc theo symbol + magic).
  2. Đọc trend từ nến H1 đã đóng (shift 1): RSI(14), EMA9 của RSI (`iMA` MODE_EMA trên handle RSI) và WMA45 của RSI (`iMA` MODE_LWMA). EMA > WMA là BULLISH, EMA < WMA là BEARISH. Nếu hai đường bằng nhau hoặc dữ liệu chưa sẵn sàng thì chờ tick sau.
  3. Tính mốc từ Open của H1 mới: `S1 = floor(Open/9)*9`, `R1 = S1 + 9`, `S2 = S1 - 9`, `S3 = S1 - 18`, `R2 = R1 + 9`, `R3 = R1 + 18`.
  4. Đặt 3 lệnh limit theo trend:
     - BULLISH: Buy Limit tại S1/S2/S3 + 0.2, TP = mốc ngay trên − 0.2 (S1→R1, S2→S1, S3→S2)
     - BEARISH: Sell Limit tại R1/R2/R3 − 0.2, TP = mốc ngay dưới + 0.2 (R1→S1, R2→R1, R3→R2)
- **Kéo TP** (`InpTpPull`, mặc định bật): chỉ áp dụng cho lệnh của EA. Mỗi tick, lệnh EA sâu nhất mỗi chiều (buy có giá vào thấp nhất, sell có giá vào cao nhất) quyết định TP chung, và mọi lệnh EA cùng chiều được sửa về TP đó.
  - S1 + S2 khớp: TP của S1 thành S1 − 0.2. Tổng khoảng +8.2 giá × lot.
  - S3 khớp: TP của S1, S2 thành S2 − 0.2. Tổng khoảng −1.2 giá × lot; người dùng chấp nhận để thoát nhanh.
  - Nếu TP mới sát giá hơn stops level thì bỏ qua. Nếu sửa lỗi thì chờ 10 giây rồi thử lại.
  - Lệnh đặt tay không bị sửa. Tắt `InpTpPull` thì lệnh đã khớp giữ nguyên TP.
- **Trong giờ:** khi một lệnh của EA đóng do chạm TP (`OnTradeTransaction`, `DEAL_REASON_TP`), EA đặt lại limit ở các mốc còn trống của giờ hiện tại, cùng trend và cùng mốc. Mốc đã có limit hoặc đã có lệnh mở thì bỏ qua. Tổng lệnh mở + lệnh chờ + limit mới không vượt `InpMaxPositions`.
- Không SL, không cắt lỗ theo equity.
- Nếu một mức limit sát hoặc vượt giá (khoảng cách nhỏ hơn stops level) thì bỏ mức đó và ghi log.

## Input

| Input | Mặc định | Ý nghĩa |
|---|---|---|
| InpLot | 0.1 | lot mỗi lệnh (chuẩn hoá theo min/max/step) |
| InpStep | 9 | bước mốc |
| InpLevels | 3 | số lệnh limit mỗi giờ |
| InpOffset | 0.2 | offset spread |
| InpTpMode | mốc kế bên | TP_NEXT_LEVEL (mặc định) hoặc TP_R1_COMMON (R1/S1 chung) |
| InpTpPull | true | kéo TP mọi lệnh EA cùng chiều về TP lệnh sâu nhất |
| InpLevelTf | H1 | khung lấy Open và reset lệnh |
| InpPlaceOnStart | true | đặt lệnh ngay khi gắn EA theo Open của giờ hiện tại |
| InpMaxPositions | 6 | lệnh mở tối đa trên symbol; lệnh mở + limit mới không vượt (0 = không giới hạn) |
| InpMaxCountAll | true | giới hạn tính cả lệnh đặt tay / EA khác |
| InpMagic | 369369 | magic number |
| InpTrendTf / RSI / EMA / WMA | H1 / 14 / 9 / 45 | filter trend |

## Bảng hiển thị

Thay cho `Comment()`: bảng nền tối (OBJ_RECTANGLE_LABEL + OBJ_LABEL, font Consolas) ở góc trên trái, cập nhật mỗi giây qua `OnTimer`, và vẽ lại ngay khi có giao dịch trên symbol.

- Tiêu đề: symbol, trend (▲ BULLISH / ▼ BEARISH), đồng hồ đếm ngược tới lần reset giờ tới.
- Mốc của giờ hiện tại theo chiều lưới.
- Lệnh đang mở trên symbol (EA + tay): Loại, Nguồn, Lot, Giá vào, TP, Lời/lỗ (gồm swap), sắp xếp giá cao → thấp. Có đếm x / InpMaxPositions.
- Lệnh chờ trên symbol: loại, nguồn, giá, TP, khoảng cách tới giá hiện tại.
- Tổng lời/lỗ, equity, DD hiện tại = (balance − equity) / balance.
- Đường mốc S1..Sn / R1..Rn kéo từ đầu giờ tới cuối giờ, có nhãn giá.
- Input: InpShowPanel, InpShowLevels, InpPanelX/Y, InpPanelFont, InpPanelMaxPos (8), InpPanelMaxPend (6).
- Tester không bật visual thì không vẽ, cho chạy nhanh.

## Kiểm thử

- Đã compile bằng MetaEditor: 0 lỗi, 0 cảnh báo.
- Người dùng tự chạy Strategy Tester (XAUUSDc, "Every tick based on real ticks"), sau đó chạy trên tài khoản cent. Claude không gắn EA và không đặt lệnh trên tài khoản thật.
- EMA trong MT5 khởi tạo khác một chút so với `ta.ema` của TradingView, nên trend có thể lệch với indicator Pine ở vài nến đầu lịch sử; sau khi đủ dữ liệu thì hội tụ.
