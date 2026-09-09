"""Năm biến thể của phép đo ⑥, cộng hai đường kiểm định của Phase 1b.

Spec: docs/superpowers/specs/2026-09-09-quarterly-theory-variants-study-design.md

Phase 1 đo MỘT cách hình thức hoá ý tưởng sweep-reclaim và nó thất bại
(percentile 3,0 ở tầng session và 2,9 ở q90). Module này đo năm cách khác.

Điều quan trọng nhất về file này: năm biến thể **bắt buộc** dùng đúng
`base_trigger`. Nếu từng biến thể tự định nghĩa điều kiện sweep thì chúng
không còn so sánh được với nhau và vòng sàng ở §4 của spec trở thành so táo
với cam — nghiên cứu vẫn ra số, nhưng số đó vô nghĩa.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .quarter_stats import MIN_BARS_PER_QUARTER


def _mean_or_nan(x: np.ndarray) -> float:
    """Bản sao của hàm cùng tên trong quarter_stats.

    Để cục bộ có ý: spec 1b §Phạm vi cho phép sửa quarter_stats ĐÚNG MỘT chỗ
    (tham số `stats`). Nâng một hàm private của module đó thành public là chỗ
    sửa thứ hai. Hai dòng trùng lặp rẻ hơn việc nới phạm vi.
    """
    return float(np.mean(x)) if x.size else float("nan")


def base_trigger(w: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Trigger chung của mọi biến thể, y nguyên ⑥ của Phase 1 §4.2.

    Trả về `(up, dn)` đã LOẠI chu kỳ sweep cả hai phía: lý thuyết không đưa ra
    kỳ vọng hướng nào cho trường hợp đó, và giữ nó lại sẽ đếm một chu kỳ hai
    lần với hai kỳ vọng trái nhau.

    So sánh là `>` và `<`, không phải `>=` và `<=`: chạm đúng biên không phải
    sweep, và `q2_close` bằng đúng biên là hoà nên không tính reclaim.
    """
    q1h = w["q1_high"].to_numpy()
    q1l = w["q1_low"].to_numpy()
    q2h = w["q2_high"].to_numpy()
    q2l = w["q2_low"].to_numpy()
    q2c = w["q2_close"].to_numpy()
    swept_up = (q2h > q1h) & (q2c < q1h)
    swept_dn = (q2l < q1l) & (q2c > q1l)
    both = swept_up & swept_dn
    return swept_up & ~both, swept_dn & ~both


def q3_dir(w: pd.DataFrame) -> np.ndarray:
    """Hướng của Q3. 0 là hoà và bị `pooled` loại."""
    return np.sign(w["q3_close"].to_numpy() - w["q3_open"].to_numpy())


def pooled(up: np.ndarray, dn: np.ndarray, direction: np.ndarray,
           against: bool) -> dict[str, float]:
    """Gộp hai phía sweep thành một xác suất, chuẩn hoá theo hướng.

    `against=True`  -> P(direction đi NGƯỢC hướng sweep)  — ⑥ và V2..V5
    `against=False` -> P(direction đi CÙNG hướng sweep)   — V1

    `direction == 0` là hoà và bị loại (spec 1b §2). Không loại thì `np.sign`
    cho 0 và quan sát đó rơi vào nhánh "không đạt" một cách tuỳ ý.
    """
    live = direction != 0
    u, d = up & live, dn & live
    if against:
        hits = np.concatenate([direction[u] < 0, direction[d] > 0])
    else:
        hits = np.concatenate([direction[u] > 0, direction[d] < 0])
    return {"p": _mean_or_nan(hits), "n": float(hits.size),
            "n_up": float(u.sum()), "n_dn": float(d.sum())}


def variant_v1(w: pd.DataFrame) -> dict[str, float]:
    """V1 — Q3 đi CÙNG hướng sweep, tức đảo thesis của ⑥.

    Lý do: số Phase 1 nói Q3 đi cùng hướng sweep 52,7% số lần.

    CẢNH BÁO (spec 1b §7): V1 = 1 − ⑥ trên đúng cùng tập con, nên
    `percentile(V1) = 100 − percentile(⑥)` một cách máy móc. Trên toàn dữ liệu
    nó sẽ ra ~97 và con số đó VÔ GIÁ TRỊ, vì ⑥ đã được xem trước khi V1 được
    nghĩ ra. Giá trị duy nhất của V1 là kiểm độ ổn định qua thời gian trên nửa
    sau — không phải phát hiện.
    """
    up, dn = base_trigger(w)
    return pooled(up, dn, q3_dir(w), against=False)


def variant_v3(w: pd.DataFrame) -> dict[str, float]:
    """V3 — reclaim quyết đoán: Q2 đóng VƯỢT TRUNG ĐIỂM range Q1.

    Lý do: ICT nhấn displacement, còn "đóng lại trong range" của ⑥ nhận cả một
    cú reclaim sát biên.

    Luật loại `both` giữ nguyên như mọi biến thể (spec 1b §2), dù điều kiện của
    V3 khiến `up` và `dn` không thể cùng đúng — một giá đóng không thể vừa dưới
    vừa trên trung điểm. Không đổi luật loại giữa các biến thể, nếu không chúng
    mất tính so sánh được.
    """
    up, dn = base_trigger(w)
    mid = (w["q1_high"].to_numpy() + w["q1_low"].to_numpy()) / 2.0
    q2c = w["q2_close"].to_numpy()
    return pooled(up & (q2c < mid), dn & (q2c > mid), q3_dir(w), against=True)


def variant_v4(w: pd.DataFrame) -> dict[str, float]:
    """V4 — chân trời đo là Q3+Q4 thay vì Q3 một mình.

    Lý do: hai profile AMDX và XAMD dịch vai trò các quarter (spec indicator
    §2.2), nên payoff hướng có thể không gói trong Q3.
    """
    up, dn = base_trigger(w)
    direction = np.sign(w["q4_close"].to_numpy() - w["q3_open"].to_numpy())
    return pooled(up, dn, direction, against=True)


def variant_v5(w: pd.DataFrame) -> dict[str, float]:
    """V5 — lọc theo phía True Open (= open của bar đầu Q2).

    Lý do: §2.4 True Open, kết hợp hai yếu tố được nhắc nhiều nhất của lý thuyết.

    Sweep lên kỳ vọng Q3 giảm nên đòi đầu Q3 ở premium (trên TO); sweep xuống
    đòi đầu Q3 ở discount (dưới TO). Bằng đúng TO là hoà nên bị loại.
    """
    up, dn = base_trigger(w)
    side = np.sign(w["q3_open"].to_numpy() - w["q2_open"].to_numpy())
    return pooled(up & (side > 0), dn & (side < 0), q3_dir(w), against=True)
