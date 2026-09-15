"""Setup RSI theo xu huong: thung 25 roi hoi ve 50 thi ban.

Spec: docs/superpowers/specs/2026-09-15-rsi-trend-pullback-design.md

Ban goc de doi chieu voi pine/rsi_trend_pullback_indicator.pine va
pine/rsi_trend_pullback_strategy.pine.

RUI RO SO MOT CUA FILE PINE LA THU TU TRONG MOT NEN. Ba buoc phai chay dung
thu tu nay cho moi chieu:

    1. noi cuc tri dang chay   (chi khi SEEKING)
    2. kiem tin hieu           (chi khi SEEKING)
    3. mo pha moi              (chi khi IDLE)

Buoc 1 truoc buoc 2 vi dinh nghia lay day "cho toi nen entry", tuc low cua
chinh nen vao lenh phai duoc tinh vao. Dao hai buoc nay thi TP lech mot nen —
pattern van chay, van ve, va sai am tham.

Buoc 2 truoc buoc 3 de mot tin hieu vua ban khong mo lai pha ngay tren cung
mot nen.
"""
from collections import namedtuple

Bar = namedtuple("Bar", "h l c")
Signal = namedtuple("Signal", "direction bar entry sl tp rr wait")

SELL = "SELL"
BUY = "BUY"

IDLE = 0
SEEKING = 1


def run(bars, rsi, atr, lo=25.0, mid=50.0, hi=75.0,
        sl_mult=3.0, tp_mult=1.0, enable_sell=True, enable_buy=True):
    """Tra ve danh sach Signal theo thu tu thoi gian.

    `rsi[i]` hoac `atr[i]` bang None nghia la chua du lieu (warm-up): khong
    trang thai nao doi va khong tin hieu nao ban.

    Mau so cua rr la `sl_mult * atr`. Khi no bang 0 thi rr khong tinh duoc va
    TIN HIEU KHONG BAN — khong do duoc rui ro thi khong danh dau. Nhung setup
    VAN BI TIEU THU (ve IDLE), giong het khi chieu do bi tat: xem spec 2.7.
    """
    out = []
    s_st, s_low, s_xbar = IDLE, None, None
    b_st, b_high, b_xbar = IDLE, None, None

    for i, bar in enumerate(bars):
        r, a = rsi[i], atr[i]
        ok = r is not None and a is not None

        # ---------------------------------------------------------- chieu BAN
        if s_st == SEEKING and bar.l < s_low:
            s_low = bar.l

        if s_st == SEEKING and ok and r > mid:
            s_risk = sl_mult * a
            if enable_sell and s_risk > 0:
                s_entry = bar.c
                s_tp = s_low - tp_mult * a
                out.append(Signal(SELL, i, s_entry, s_entry + s_risk, s_tp,
                                  (s_entry - s_tp) / s_risk, i - s_xbar))
            s_st = IDLE

        if s_st == IDLE and ok and r < lo:
            s_st, s_low, s_xbar = SEEKING, bar.l, i

        # ---------------------------------------------------------- chieu MUA
        if b_st == SEEKING and bar.h > b_high:
            b_high = bar.h

        if b_st == SEEKING and ok and r < mid:
            b_risk = sl_mult * a
            if enable_buy and b_risk > 0:
                b_entry = bar.c
                b_tp = b_high + tp_mult * a
                out.append(Signal(BUY, i, b_entry, b_entry - b_risk, b_tp,
                                  (b_tp - b_entry) / b_risk, i - b_xbar))
            b_st = IDLE

        if b_st == IDLE and ok and r > hi:
            b_st, b_high, b_xbar = SEEKING, bar.h, i

    return out
