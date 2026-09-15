"""Test cho orfade_oracle — fade cu pha range phien.

Spec: docs/superpowers/specs/2026-09-15-nas-open-range-fade-design.md

Oracle nhan san nhan phien va nhan cua so: mui gio la viec cua hour(time, tz)
trong Pine, khong phai thu dang co rui ro. Thu co rui ro la MAY TRANG THAI va
THU TU sau buoc trong mot nen.

Moi test dung min_range_bars=2 cho gon; mac dinh that la 30.
"""
from orfade_oracle import BUY, SELL, Bar, run


def mk(rows, sess="S1", n_window=2):
    """rows la list (o, h, l, c). n_window nen dau tien nam trong cua so gom."""
    bars = [Bar(*r) for r in rows]
    session = [sess] * len(rows)
    in_window = [i < n_window for i in range(len(rows))]
    return bars, session, in_window


def test_ban_day_du():
    """Cua so: nen 0-1 -> rh=110, rl=90.

    nen 3 do, close 102        -> last_dn = 102
    nen 4 dong 112 > 110       -> pha len, arm o muc 102
    nen 6 dong 101 < 102       -> TIN HIEU BAN, cho = 6 - 4 = 2
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (100, 104, 99, 103),      # 2 xanh, trong range
        (106, 107, 101, 102),     # 3 DO  -> last_dn = 102
        (103, 115, 102, 112),     # 4 pha len
        (112, 113, 108, 109),     # 5 do, ve trong range
        (109, 110, 100, 101),     # 6 do, xuyen muc -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    s = got[0]
    assert s.direction == SELL
    assert s.bar == 6
    assert s.level == 102
    assert s.close == 101
    assert s.wait == 2
    assert s.session == "S1"


def test_moc_la_nen_do_CUOI_CUNG_truoc_cu_pha():
    """Hai nen do truoc cu pha; cai sau thang.

    nen 2 do close 101, nen 3 do close 103 -> moc phai la 103.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (106, 107, 100, 101),     # 2 DO -> last_dn = 101
        (104, 105, 99, 103),      # 3 DO -> last_dn = 103
        (103, 115, 102, 112),     # 4 pha len -> arm o 103
        (112, 113, 100, 102),     # 5 do, 102 < 103 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].level == 103
    assert got[0].wait == 1


def test_nen_pha_la_nen_do_khong_tu_lay_minh_lam_moc():
    """Buoc 6 phai CUOI CUNG.

    nen 3 vua la nen DO vua dong tren bien (112 > 110). Moc phai la 102 (tu nen
    2), khong phai 112 (cua chinh no).

    Neu buoc 6 chay truoc buoc 4: moc = 112, va nen 4 (close 105) se xuyen ngay
    -> tin hieu o nen 4, muc 112, cho 1. Ban dung cho tin hieu o nen 5, muc 102,
    cho 2.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (105, 106, 100, 102),     # 2 DO -> last_dn = 102
        (115, 116, 111, 112),     # 3 DO va dong tren bien -> pha, arm o 102
        (112, 113, 104, 105),     # 4 do, 105 khong duoi 102; ve trong range
        (105, 106, 100, 101),     # 5 do, 101 < 102 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].bar == 5
    assert got[0].level == 102
    assert got[0].wait == 2


def test_phai_dong_trong_range_truoc_khi_tinh_cu_pha_moi():
    """Spec 3.2. Sau cu pha o nen 3, cac nen 4 va 5 van o tren bien nen KHONG
    duoc tinh la cu pha moi — moc giu nguyen 102.

    Neu bo dieu kien eligible: nen 5 se arm lai o muc 113 (last_dn cua nen 4),
    va nen 6 (close 105) xuyen ngay -> tin hieu o nen 6, muc 113, cho 1.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (105, 106, 100, 102),     # 2 DO -> last_dn = 102
        (103, 115, 102, 112),     # 3 pha len -> arm o 102, el = False
        (114, 116, 111, 113),     # 4 DO, van tren bien -> last_dn = 113
        (113, 115, 112, 114),     # 5 xanh, van tren bien -> khong arm lai
        (114, 115, 104, 105),     # 6 do, ve trong range -> el = True
        (105, 106, 100, 101),     # 7 do, 101 < 102 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].bar == 7
    assert got[0].level == 102
    assert got[0].wait == 4


def test_nen_dong_o_bien_kia_khong_bat_lai_eligible():
    """Spec 3.2 cau cuoi: dong DUOI rangeLow la o NGOAI range, khong phai trong.

    Ca nay doi moc phai nam DUOI rangeLow. Neu moc o gan bien tren nhu thuong
    le thi nen dong duoi rangeLow se xuyen moc va ban tin hieu NGAY, va trang
    thai eligible khong con quan sat duoc — mot test viet kieu do se pass vi ly
    do sai.

    moc = 85, duoi rl = 90. Nen 4 dong 88: duoi rl nhung TREN moc nen khong ban.
    Neu 88 bat lai up_el thi nen 5 arm lai o 88 va nen 6 (dong 86) ban voi
    cho = 1. Ban dung: khong arm lai, nen 7 (dong 84) moi ban, moc 85, cho = 4.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (95, 96, 84, 85),         # 2 DO, dong DUOI rl -> last_dn = 85
        (85, 115, 84, 112),       # 3 pha len -> arm o 85, up_el = False
        (112, 113, 87, 88),       # 4 DO, duoi rl nhung TREN moc -> khong ban
        (88, 115, 87, 112),       # 5 pha len lan hai -> KHONG duoc arm lai
        (112, 113, 85, 86),       # 6 do, 86 khong duoi 85
        (86, 87, 83, 84),         # 7 do, 84 < 85 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].bar == 7
    assert got[0].level == 85
    assert got[0].wait == 4


def test_moc_tren_bien_thi_khong_arm():
    """Spec 3.4 ve cuoi. Nen 2 la nen DO dong tren bien (112 > 110) nhung luc do
    last_dn con None nen khong arm. Sau buoc 6, last_dn = 112 > rangeHigh.

    Nen 3 dong tren bien lan nua: up_el van True (chua tung arm), nhung
    112 < 110 sai -> KHONG arm. Nen 4 dong 101, neu da arm o 112 thi no da ban.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (115, 116, 111, 112),     # 2 DO tren bien, last_dn con None -> khong arm
        (112, 114, 111, 113),     # 3 xanh tren bien, last_dn = 112 > 110 -> chan
        (113, 114, 100, 101),     # 4 neu da arm o 112 thi day da ban
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert got == []


def test_khong_co_nen_do_nao_thi_khong_arm():
    """last_dn con None thi cu pha khong arm duoc."""
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (100, 104, 99, 103),      # 2 xanh
        (103, 115, 102, 112),     # 3 pha len, last_dn = None -> khong arm
        (112, 113, 100, 101),     # 4 khong co gi de xuyen
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert got == []


def test_mua_guong_qua_bien_duoi():
    """Chieu xuong soi guong: nen xanh cuoi truoc cu pha xuong lam moc.

    nen 2 xanh close 99  -> last_up = 99
    nen 3 dong 86 < 90   -> pha xuong, arm o 99
    nen 4 dong 100 > 99  -> TIN HIEU MUA, cho = 1
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (95, 100, 94, 99),        # 2 XANH -> last_up = 99
        (95, 96, 85, 86),         # 3 pha xuong -> arm o 99
        (86, 102, 85, 100),       # 4 xanh, 100 > 99 -> MUA
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    b = got[0]
    assert b.direction == BUY
    assert b.bar == 4
    assert b.level == 99
    assert b.close == 100
    assert b.wait == 1


def test_phien_moi_xoa_sach_trang_thai():
    """Spec 3.7. Setup dang armed o cuoi phien 1 KHONG duoc song sang phien 2.

    Neu trang thai ro ri: nen 6 dong 49 < muc cu 102 -> mot tin hieu BAN gia.
    """
    bars = [Bar(100, 110, 90, 105), Bar(105, 108, 95, 100),
            Bar(105, 106, 100, 102), Bar(103, 115, 102, 112),
            Bar(50, 60, 40, 55), Bar(55, 58, 45, 50),
            Bar(50, 52, 48, 49)]
    session = ["S1", "S1", "S1", "S1", "S2", "S2", "S2"]
    in_window = [True, True, False, False, True, True, False]

    got = run(bars, session, in_window, min_range_bars=2)

    assert got == []


def test_cua_so_qua_it_nen_thi_phien_do_chet():
    """Spec 2.4. min_range_bars = 2 nhung cua so chi co 1 nen."""
    bars = [Bar(100, 110, 90, 105), Bar(105, 106, 100, 102),
            Bar(103, 115, 102, 112), Bar(112, 113, 100, 101)]
    session = ["S1"] * 4
    in_window = [True, False, False, False]

    got = run(bars, session, in_window, min_range_bars=2)

    assert got == []


def test_doji_khong_phai_do_cung_khong_phai_xanh():
    """Spec 3.3. Nen 3 co close == open nen khong cap nhat moc nao.

    Moc phai la 102 (tu nen 2), khong phai 103 (tu nen doji).
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (105, 106, 100, 102),     # 2 DO -> last_dn = 102
        (103, 104, 102, 103),     # 3 DOJI -> khong doi moc nao
        (103, 115, 102, 112),     # 4 pha len -> arm o 102
        (112, 113, 102, 103),     # 5 do, 103 khong duoi 102
        (103, 104, 100, 101),     # 6 do, 101 < 102 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].level == 102
    assert got[0].bar == 6


def test_dong_cua_dung_bang_moc_khong_ban():
    """Luat la `<` chat. Nen 5 dong dung 102 -> khong ban; nen 6 dong 101 -> ban."""
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (105, 106, 100, 102),     # 2 DO -> last_dn = 102
        (103, 115, 102, 112),     # 3 pha len -> arm o 102
        (112, 113, 101, 102),     # 4 dong DUNG BANG moc -> khong ban
        (102, 103, 100, 101),     # 5 dong 101 < 102 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].bar == 5


def test_tat_mot_chieu_khong_anh_huong_chieu_kia():
    """Hai co chi chan viec PHAT tin hieu, khong doi trang thai."""
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (106, 107, 101, 102),     # 2 DO -> last_dn = 102
        (103, 115, 102, 112),     # 3 pha len -> arm o 102
        (112, 113, 100, 101),     # 4 do, 101 < 102 -> BAN (neu bat)
    ])

    assert run(bars, sess, win, min_range_bars=2, enable_up=False) == []
    assert len(run(bars, sess, win, min_range_bars=2, enable_down=False)) == 1
