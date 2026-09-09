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

from .bars import Bars
from .quarter_stats import (MIN_BARS_PER_QUARTER, percentile_of, run_grid,
                            run_null)


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


TRAILING_WINDOW = 20


def trailing_tight(r1: pd.Series, window: int) -> np.ndarray:
    """`range(Q1)` nhỏ hơn median TRƯỢT của `window` chu kỳ TRƯỚC ĐÓ.

    `shift(1)` là thứ chặn lookahead, và nó là dòng quan trọng nhất của hàm
    này: thiếu nó thì chu kỳ hiện tại tham gia vào median của chính nó, tức
    điều kiện "Q1 hẹp" được quyết bằng thông tin của chính chu kỳ đang xét.

    Chu kỳ chưa đủ `window` chu kỳ trước đó cho median NaN; `NaN` so sánh ra
    False nên chúng bị loại — đúng ý.

    So sánh `<` chặt: bằng đúng median là hoà nên loại.

    Yêu cầu: `r1` theo thứ tự thời gian. `aggregate_cycles` groupby với
    `sort=True` nên index đã sắp theo `cycle_id`, tức đã theo thời gian.
    """
    med = r1.shift(1).rolling(window).median()
    return (r1 < med).to_numpy()


def variant_v2(w: pd.DataFrame) -> dict[str, float]:
    """V2 — chỉ tính chu kỳ có Q1 hẹp so với quá khứ gần.

    Lý do: chính phát biểu ④ của lý thuyết — "Q1 dictates the quarters which
    follow", Q1 hẹp báo Q2 giãn, nên cú manipulation ở Q2 "thật" hơn.

    Đáng lưu ý: Phase 1 đo ④ và thấy tương quan range Q1 với range Q2 là
    DƯƠNG (+0,71..+0,77), tức ngược hẳn điều lý thuyết đòi. V2 vẫn được thử vì
    ④ đo tương quan tuyến tính đơn điệu trên toàn bộ chu kỳ, còn V2 hỏi một
    câu khác và hẹp hơn: trong tập con Q1 hẹp, tín hiệu sweep có tốt hơn không.
    """
    r1 = w["q1_high"] - w["q1_low"]
    tight = trailing_tight(r1, TRAILING_WINDOW)
    up, dn = base_trigger(w)
    return pooled(up & tight, dn & tight, q3_dir(w), against=True)


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


VARIANTS = {
    "V1": variant_v1, "V2": variant_v2, "V3": variant_v3,
    "V4": variant_v4, "V5": variant_v5,
}

# Đường A: V1 KHÔNG qua vòng sàng — nó đã được định trước nên sàng nó là vô
# nghĩa (spec 1b §4). Đường B: bốn biến thể còn lại.
DIRECT_VARIANT = "V1"
SCREEN_VARIANTS = ("V2", "V3", "V4", "V5")

# Tie-break chốt trong spec §4 để không phải quyết sau khi thấy số.
TIE_BREAK = SCREEN_VARIANTS

# Tầng chính: q90 ít bị confound mốc 18:00 hơn (Phase 1 §8.2). Tầng session
# chỉ báo mô tả, không tuyên bố gì, không tính vào số kiểm định.
PRIMARY_TIER = "q90"


def split_halves(bars: Bars) -> tuple[Bars, Bars]:
    """Chia mảng bar làm hai tại `len//2`; bar dư thuộc NỬA SAU (spec 1b §3).

    Toàn bộ pipeline chạy độc lập trên từng nửa. Chu kỳ vắt qua điểm chia sẽ
    thiếu bar ở nửa nào cũng vậy và bị luật `min_bars` loại tự nhiên — không
    cần xử lý riêng.
    """
    n = len(bars)
    mid = n // 2
    return bars.slice(0, mid), bars.slice(mid, n)


def screen(bars_first: Bars, tier: str, offsets: np.ndarray,
           min_bars: int = MIN_BARS_PER_QUARTER) -> pd.DataFrame:
    """Xếp hạng V2–V5 trên nửa đầu.

    KHÔNG TUYÊN BỐ GÌ TẠI ĐÂY. Percentile trả về chỉ để xếp hạng; nó không
    phải bằng chứng và không được đọc thành "biến thể này pass" (spec 1b §4).
    """
    subset = {k: VARIANTS[k] for k in SCREEN_VARIANTS}
    real = run_grid(bars_first, tier, min_bars=min_bars, stats=subset)
    nulls = run_null(bars_first, tier, offsets, min_bars=min_bars, stats=subset)
    rows = []
    for name in SCREEN_VARIANTS:
        key = f"{name}.p"
        rows.append({"variant": name, "real": real[key], "n": real[f"{name}.n"],
                     "percentile": percentile_of(real[key], nulls[key].to_numpy())})
    return pd.DataFrame(rows)


def pick_winner(screened: pd.DataFrame) -> str:
    """Percentile cao nhất → `n` lớn hơn → thứ tự `TIE_BREAK` (spec 1b §4).

    NaN percentile xuống cuối: một biến thể loại hết chu kỳ không được thắng.
    """
    d = screened.copy()
    d["_order"] = [TIE_BREAK.index(v) for v in d["variant"]]
    d = d.sort_values(["percentile", "n", "_order"],
                      ascending=[False, False, True], na_position="last")
    return str(d.iloc[0]["variant"])


def confirm(bars_second: Bars, tier: str, offsets: np.ndarray, variant: str,
            min_bars: int = MIN_BARS_PER_QUARTER) -> dict:
    """Kiểm định cuối của ĐÚNG MỘT biến thể trên nửa sau.

    `beat_all_nulls` là cờ quyết định, không phải `percentile`. Spec 1b §5:
    tầng q90 có 69 lưới null nên α ≤ 2,5% đòi k = 0, tức giá trị thật phải
    vượt CẢ 69 lưới. Dùng `percentile > 95` sẽ nới ngưỡng một cách âm thầm —
    percentile 96 trên 69 lưới vẫn còn 2 lưới null vượt giá trị thật.
    """
    subset = {variant: VARIANTS[variant]}
    real = run_grid(bars_second, tier, min_bars=min_bars, stats=subset)
    nulls = run_null(bars_second, tier, offsets, min_bars=min_bars, stats=subset)
    value = real[f"{variant}.p"]
    col = nulls[f"{variant}.p"].to_numpy(dtype="float64")
    finite = col[np.isfinite(col)]
    return {
        "variant": variant, "real": value, "n": real[f"{variant}.n"],
        "percentile": percentile_of(value, col),
        "n_nulls": int(finite.size),
        "beat_all_nulls": bool(finite.size > 0 and np.isfinite(value)
                               and np.all(finite < value)),
    }


def verdict(track_a: dict, track_b: dict) -> tuple[str | None, str]:
    """Luật §6 của spec 1b, tính bằng máy — không để người đọc tự kết luận.

    Trả về `(tên đường thắng, văn bản)`. `None` nghĩa là không đường nào pass,
    và khi đó Quarterly Theory ĐÓNG LẠI với repo này: không có Phase 1c.
    """
    lines = ["## Phan quyet spec 1b section 6", ""]
    for name, t in (("A", track_a), ("B", track_b)):
        lines.append(
            f"- duong **{name}** ({t['variant']}): real={t['real']:.4f}, "
            f"percentile={t['percentile']:.1f}, n={t['n']:.0f}, "
            f"nulls={t['n_nulls']} -> "
            f"{'VUOT CA MOI LUOI NULL' if t['beat_all_nulls'] else 'khong vuot'}")

    a_ok, b_ok = bool(track_a["beat_all_nulls"]), bool(track_b["beat_all_nulls"])
    if a_ok and b_ok:
        # Đồng percentile thì ưu tiên đường B: nó là phát hiện, còn đường A chỉ
        # là kiểm độ ổn định của một con số đã biết (spec 1b §6, §7).
        winner = "A" if track_a["percentile"] > track_b["percentile"] else "B"
    elif a_ok:
        winner = "A"
    elif b_ok:
        winner = "B"
    else:
        winner = None

    lines.append("")
    if winner is None:
        lines.append(
            "**KHONG duong nao pass. Quarterly Theory dong lai voi repo nay.** "
            "Day la ket luan, khong phai mot vong thu nua: khong co Phase 1c "
            "(spec 1b section 6).")
    elif winner == "A":
        lines.append(
            f"**Duong A pass** ({track_a['variant']}). Cau duoc phep noi la "
            "'chieu continuation on dinh qua hai nua lich su'. Cau KHONG duoc "
            "phep noi la 'da tim ra mot edge' — xem spec 1b section 7.")
    else:
        lines.append(
            f"**Duong B pass** ({track_b['variant']}). Phase 2 duoc phep viet "
            "spec cho bien the nay.")
    lines += ["", (
        "Pass VAN KHONG nghia la co lai. Nghien cuu nay khong tinh cost; spread "
        "XAUUSDc trong config/default.yaml la 260 points = 0,26 USD "
        "(spec 1b section 6).")]
    return winner, "\n".join(lines)
