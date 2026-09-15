"""Fade cu pha range cua phien: gom range gio dau, cho pha, roi cho xuyen nguoc.

Spec: docs/superpowers/specs/2026-09-15-nas-open-range-fade-design.md

Ban goc de doi chieu voi pine/nas_open_range_fade.pine.

RUI RO SO MOT CUA FILE PINE LA THU TU TRONG MOT NEN. Sau buoc phai chay dung
thu tu nay:

    1. gom range / chot range
    2. kiem tin hieu        -> ban, disarm
    3. cap nhat eligible    (neu nen nay dong TRONG range)
    4. kiem pha LEN         -> arm
    5. kiem pha XUONG       -> arm
    6. cap nhat last_dn / last_up TU NEN NAY

Buoc 6 phai CUOI CUNG. Neu no chay truoc buoc 4 thi mot nen pha ma ban than no
la nen do se tu lay close cua chinh minh lam moc — pattern van chay, van ve, va
sai am tham.

Oracle nhan san `session` va `in_window` thay vi tu tinh mui gio: mui gio la
viec cua hour(time, tz) trong Pine, khong phai thu dang co rui ro.

`enable_up` / `enable_down` CHI chan viec PHAT tin hieu, khong doi trang thai.
Setup van arm va van bi tieu thu y het khi co tat. Nho vay hai co la bo loc hien
thi thuan tuy va khong tao ra mot may trang thai thu hai.
"""
from collections import namedtuple

Bar = namedtuple("Bar", "o h l c")
Signal = namedtuple("Signal", "direction bar level close wait session")

SELL = "SELL"
BUY = "BUY"

_NO_SESSION = object()


def run(bars, session, in_window, min_range_bars=30,
        enable_up=True, enable_down=True):
    """Tra ve danh sach Signal theo thu tu thoi gian.

    `session[i]` doi gia tri nghia la phien moi: xoa sach moi trang thai.
    `session[i] is None` nghia la nen chua thuoc phien nao — bo qua.
    """
    out = []
    cur = _NO_SESSION
    rh = rl = None
    n_win = 0
    finalized = False
    range_ok = False
    up_el = dn_el = False
    up_armed = dn_armed = False
    up_level = dn_level = None
    up_bar = dn_bar = None
    last_dn = last_up = None

    for i, bar in enumerate(bars):
        s = session[i]

        if s != cur:                       # phien moi: xoa sach (spec 3.7)
            cur = s
            rh = rl = None
            n_win = 0
            finalized = False
            range_ok = False
            up_el = dn_el = False
            up_armed = dn_armed = False
            up_level = dn_level = None
            up_bar = dn_bar = None
            last_dn = last_up = None

        if s is None:
            continue

        # ---- 1. gom range / chot range
        if in_window[i]:
            rh = bar.h if rh is None else max(rh, bar.h)
            rl = bar.l if rl is None else min(rl, bar.l)
            n_win += 1
            continue

        if not finalized:
            finalized = True
            range_ok = n_win >= min_range_bars
            up_el = dn_el = range_ok
            last_dn = last_up = None       # diem xoa thu hai (spec 3.3)

        if not range_ok:
            continue

        # ---- 2. tin hieu
        if up_armed and bar.c < up_level:
            if enable_up:
                out.append(Signal(SELL, i, up_level, bar.c, i - up_bar, s))
            up_armed = False
        if dn_armed and bar.c > dn_level:
            if enable_down:
                out.append(Signal(BUY, i, dn_level, bar.c, i - dn_bar, s))
            dn_armed = False

        # ---- 3. eligible: chi khi dong TRONG range
        if rl <= bar.c <= rh:
            up_el = dn_el = True

        # ---- 4. pha LEN
        if bar.c > rh and up_el and last_dn is not None and last_dn < rh:
            up_level = last_dn
            up_bar = i
            up_armed = True
            up_el = False

        # ---- 5. pha XUONG
        if bar.c < rl and dn_el and last_up is not None and last_up > rl:
            dn_level = last_up
            dn_bar = i
            dn_armed = True
            dn_el = False

        # ---- 6. cap nhat moc TU NEN NAY — phai CUOI CUNG
        if bar.c < bar.o:
            last_dn = bar.c
        elif bar.c > bar.o:
            last_up = bar.c

    return out
