"""Dò timezone của nguồn dữ liệu bằng khe nghỉ hằng ngày — cổng CHẶN.

Spec: docs/superpowers/specs/2026-09-09-h4-kill-both-ends-study-design.md §6.1.

`quarters.verify_server_tz` hardcode nguồn là UTC vì epoch của MT5 đã được kiểm
là UTC thật. CSV export từ Trading Station thì theo timezone HIỂN THỊ của
platform — người dùng đặt sao nó ra vậy, và nghiên cứu này không được giả định.
Lệch một giờ nghĩa là đo một lưới khác.

Tiêu chí là khe nghỉ hằng ngày (17:00->18:00 NY), không phải mốc mở tuần. Đo
trên 3.299.723 bar M1 của XAUUSDc:

    khe nghỉ: N = 2290
    P(bar cuối trước khe ở giờ 16 NY) = 0,8179
    P(bar đầu sau khe  ở giờ 18 NY) = 0,9109
    score đọc đúng 0,8644 | lệch -1h 0,0020 | +1h 0,0155 | -2h 0,0094 | +2h 0,0181

Mốc mở tuần tệ hơn hẳn: chỉ 331 mẫu sạch, 81% rơi vào giờ kỳ vọng, cửa sổ hai
giờ rộng nên offset ±1h vẫn lọt qua. Bộ dữ liệu này còn có 163 bar Thứ Bảy lạc
làm sai 22% phép đếm khe cuối tuần.

Ngưỡng 0,70 chứ không phải 0,90 vì cách đọc ĐÚNG trên dữ liệu thật chỉ đạt
0,8644 — ngày lễ rút ngắn ăn vào phần còn lại. Đặt 0,90 là tự chặn chính mình.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..quarters import NY_TZ

DAILY_GAP_MAX = 86400
BEFORE_HOUR = 16
AFTER_HOUR = 18
MIN_SCORE = 0.70
MIN_MARGIN = 0.30
MIN_GAPS = 30
# Một offset cố định được coi là "mảnh vỡ đáng kể" của zone thắng khi điểm của
# nó >= ngưỡng này. 0,20 chọn theo số đo thật ở docstring trên: cách đọc SAI
# lệch ±1h/±2h chỉ đạt 0,0020–0,0181, nên 0,20 cách nền nhiễu hơn mười lần và
# không thể do trùng hợp. Mặt trên thì một nguồn có DST chia năm thành hai
# mảnh cỡ 0,3–0,6, nên 0,20 không cắt nhầm mảnh nhỏ hơn của cặp.
SPLIT_MIN_SHARE = 0.20
CANDIDATE_OFFSETS = tuple(range(-12, 15))
CANDIDATE_ZONES = ("America/New_York", "Europe/Athens")


@dataclass(frozen=True)
class TzDetect:
    best: str
    score: float
    runner_up: str
    runner_up_score: float
    table: tuple[tuple[str, float], ...]
    n_gaps: int
    ok: bool
    notes: tuple[str, ...]


def candidate_labels() -> list[str]:
    """Offset 0 chỉ xuất hiện một lần, dưới tên "UTC"."""
    offs = [f"{k:+03d}:00" for k in CANDIDATE_OFFSETS if k != 0]
    return ["UTC"] + offs + list(CANDIDATE_ZONES)


def to_ny(time: np.ndarray, label: str) -> pd.DatetimeIndex:
    """Đọc `time` theo cách `label` mô tả rồi convert sang giờ New York.

    "UTC" và "+hh:00" nghĩa là nhãn thời gian là giờ treo tường của offset cố
    định đó, nên instant thật là `t - offset`. Zone có tên thì localize trực tiếp
    (nguồn có DST riêng); giờ nhập nhằng hoặc không tồn tại thành NaT và bị tính
    là TRƯỢT, không bị bỏ qua — bỏ qua sẽ thổi điểm của một cách đọc sai.
    """
    naive = pd.to_datetime(np.asarray(time, dtype="int64"), unit="s")
    if label == "UTC":
        return naive.tz_localize("UTC").tz_convert(NY_TZ)
    if label[0] in "+-":
        hours = int(label[:3])
        return (naive - pd.Timedelta(hours=hours)).tz_localize("UTC").tz_convert(NY_TZ)
    return naive.tz_localize(label, ambiguous="NaT",
                             nonexistent="NaT").tz_convert(NY_TZ)


def _hour_hits(ny: pd.DatetimeIndex, idx: np.ndarray, want: int) -> float:
    """Tỉ lệ, KHÔNG phải mode: mode ẩn mất chuyện một đoạn lịch sử bị lệch, và
    đó chính là lỗ hổng đã ghi ở §8 mục 5 spec Quarterly Theory Phase 1."""
    if idx.size == 0:
        return 0.0
    # `.hour` cho float64 với NaN ở vị trí NaT, và NaN không bao giờ bằng
    # `want`, nên giờ nhập nhằng/không tồn tại tự động tính là TRƯỢT. Đó là
    # điều ta muốn: bỏ qua chúng sẽ thổi điểm của một cách đọc sai.
    hour = np.asarray(ny[idx].hour, dtype="float64")
    return float(np.mean(hour == want))


def _zone_win_note(best: str, bs: float,
                   scored: list[tuple[str, float]]) -> str:
    """Câu giải thích VÌ SAO một zone có tên thắng — spec §6.1 đòi cổng in ra.

    "Zone thắng" tự nó không nói gì. Cái đáng in là cơ chế: nguồn có DST nên
    mọi offset cố định chỉ khớp được một nửa năm, điểm của chúng bị chia đôi,
    còn zone có tên gộp cả hai nửa lại. Không in cái này thì người đọc báo cáo
    không phân biệt được "zone thắng vì nguồn đúng là zone đó" với "zone thắng
    vì may rủi trên một bộ dữ liệu rác".
    """
    parts = [(lab, s) for lab, s in scored
             if lab not in CANDIDATE_ZONES and s >= SPLIT_MIN_SHARE]
    if len(parts) < 2:
        return (f"zone {best!r} thang voi {bs:.4f} nhung khong co hai offset co "
                f"dinh nao dat >= {SPLIT_MIN_SHARE}: khong co bang chung DST "
                f"chia doi")
    body = " va ".join(f"{lab!r}={s:.4f}" for lab, s in parts)
    return (f"nguon co DST: {body} bi chia doi, zone {best!r} gop lai duoc "
            f"{bs:.4f}")


def detect_source_tz(time: np.ndarray, bar_seconds: int) -> TzDetect:
    t = np.asarray(time, dtype="int64")
    if t.size < 2:
        return TzDetect("", float("nan"), "", float("nan"), (), 0, False,
                        ("chuoi qua ngan",))
    d = np.diff(t)
    after = np.flatnonzero((d > bar_seconds) & (d <= DAILY_GAP_MAX)) + 1
    if after.size < MIN_GAPS:
        return TzDetect("", float("nan"), "", float("nan"), (), int(after.size),
                        False, (f"chi co {after.size} khe trong ngay, "
                                f"can >= {MIN_GAPS}",))

    scored: list[tuple[str, float]] = []
    for label in candidate_labels():
        try:
            ny = to_ny(t, label)
        except Exception:                         # zone không có trên máy này
            continue
        score = 0.5 * _hour_hits(ny, after - 1, BEFORE_HOUR) \
            + 0.5 * _hour_hits(ny, after, AFTER_HOUR)
        scored.append((label, score))
    scored.sort(key=lambda x: -x[1])

    best, bs = scored[0]
    runner, rs = scored[1]
    notes: list[str] = []
    if best in CANDIDATE_ZONES:
        notes.append(_zone_win_note(best, bs, scored))
    if bs < MIN_SCORE:
        notes.append(f"diem tot nhat {bs:.4f} < nguong {MIN_SCORE}")
    if bs - rs < MIN_MARGIN:
        notes.append(f"bien {bs - rs:.4f} < {MIN_MARGIN}: {best!r} va {runner!r} "
                     f"khong phan biet duoc")
    ok = bs >= MIN_SCORE and (bs - rs) >= MIN_MARGIN
    return TzDetect(best=best, score=bs, runner_up=runner, runner_up_score=rs,
                    table=tuple(scored), n_gaps=int(after.size), ok=ok,
                    notes=tuple(notes))
