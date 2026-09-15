"""Test cho orfade_oracle — fade cu pha range phien.

Spec: docs/superpowers/specs/2026-09-15-nas-open-range-fade-design.md

Oracle nhan san nhan phien va nhan cua so: mui gio la viec cua hour(time, tz)
trong Pine, khong phai thu dang co rui ro. Thu co rui ro la MAY TRANG THAI va
THU TU sau buoc trong mot nen.

Moi test dung min_range_bars=2 cho gon; mac dinh that la 30.
"""
from orfade_oracle import BUY, SELL, Bar, Signal, run


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


def test_dn_moc_duoi_bien_khong_arm():
    """F2a: moc chieu xuong phai o TREN bien duoi (last_up > rl), khong chi
    khac None.

    nen 2 XANH dong 82 < rl(90) -> last_up = 82, la mot moc SAI PHIA (duoi
    ca bien duoi). nen 3 do dong 85 < rl -> pha xuong, nhung last_up(82)
    khong > rl(90) nen KHONG duoc arm. Neu bo dieu kien nay (chi con
    last_up is not None) thi no se arm o muc 82 va nen 4 (dong 90 > 82) se
    ban MUA gia.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (80, 85, 78, 82),         # 2 XANH, dong duoi rl -> last_up = 82 (sai phia)
        (88, 89, 80, 85),         # 3 do, pha xuong nhung moc sai phia -> khong arm
        (85, 95, 84, 90),         # 4 neu da arm o 82 thi day da MUA gia (90 > 82)
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert got == []


def test_eligible_bat_hai_chieu():
    """F3: ve trong range phai reset CA HAI chieu eligible, khong chi
    upEligible.

    nen 3 pha xuong arm o L1=97 (chua ban). nen 4 dong trong range -> phai
    reset ca hai chieu. nen 5 xanh dat moc moi L2=93. nen 6 pha xuong LAN
    HAI phai duoc tinh la cu pha moi (vi dn_el da duoc reset o nen 4) ->
    re-arm o L2=93, bar=6. nen 7 dong 100 > 93 -> MUA, level=93, wait=7-6=1.

    Neu dn_el khong duoc reset (chi up_el=True) thi nen 6 khong duoc tinh
    la cu pha moi, muc van la L1=97, bar van la 3 -> MUA se co level=97,
    wait=4 thay vi level=93, wait=1.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (95, 100, 94, 97),        # 2 xanh -> last_up = 97 = L1
        (92, 93, 84, 86),         # 3 do, pha xuong -> arm o 97, dn_el = False
        (98, 99, 94, 95),         # 4 do, ve trong range -> reset ca hai chieu
        (91, 94, 90, 93),         # 5 xanh, trong range -> last_up = 93 = L2
        (93, 94, 80, 85),         # 6 do, pha xuong LAN HAI -> re-arm o L2 = 93
        (85, 105, 84, 100),       # 7 xanh, dong 100 > 93 -> MUA
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    s = got[0]
    assert s.direction == BUY
    assert s.level == 93
    assert s.bar == 7
    assert s.wait == 1
    assert s.close == 100


def test_pha_len_lan_hai_ghi_de_moc_dang_armed():
    """F1: cu pha len LAN HAI phai GHI DE moc dang armed, khong bi khoa boi
    up_armed cu.

    nen 3 pha len lan 1 -> arm o A=100 (chua ban). nen 4 xanh dong trong
    range -> reset up_el (khong doi up_armed, van dang cho). nen 5 do trong
    range -> last_dn = B = 103 (moc moi, khac A). nen 6 pha len LAN HAI
    (up_el da True) phai re-arm o B=103, bar=6. nen 7 dong 101: 101 < 103
    (B) nen BAN ngay, level=103, wait=1.

    Neu up_armed bi khoa (khong re-arm duoc vi da dang armed) thi moc van
    la A=100 va nen 7 (101) khong xuyen A=100 -> khong co tin hieu nao ca.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (105, 106, 99, 100),      # 2 do -> last_dn = 100 = A
        (105, 115, 104, 112),     # 3 pha len lan 1 -> arm o A=100, up_el=False
        (100, 106, 99, 105),      # 4 xanh, trong range -> reset up_el
        (115, 116, 101, 103),     # 5 do, trong range -> last_dn = 103 = B
        (105, 115, 104, 112),     # 6 pha len lan 2 -> re-arm o B=103
        (112, 113, 100, 101),     # 7 dong 101 < 103 -> BAN, level=103, wait=1
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    s = got[0]
    assert s.direction == SELL
    assert s.level == 103
    assert s.bar == 7
    assert s.wait == 1
    assert s.close == 101


def test_pha_xuong_lan_hai_khi_chua_eligible_khong_rearm():
    """F2b: cu pha xuong LAN HAI khi dn_el con False (gia chua ve trong
    range) KHONG duoc tinh la cu pha moi -> khong re-arm, wait tinh tu cu
    pha DAU.

    nen 3 pha xuong lan 1 -> arm o 99, dn_bar=3, dn_el=False. nen 4 van o
    NGOAI range (dong 80 < rl) va dn_el con False nen KHONG duoc re-arm du
    dieu kien `close < rl` lai dung. nen 5 dong 100 > 99 -> MUA, level=99
    (khong doi), wait = 5 - 3 = 2.

    Neu bo dieu kien dn_el thi nen 4 re-arm lai (dn_bar=4, level van 99 vi
    last_up khong doi) -> nen 5 se MUA voi wait = 5 - 4 = 1 thay vi 2.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (95, 100, 94, 99),        # 2 xanh -> last_up = 99
        (92, 93, 84, 86),         # 3 do, pha xuong lan 1 -> arm o 99, dn_bar=3
        (85, 86, 78, 80),         # 4 do, van ngoai range -> KHONG duoc re-arm
        (80, 105, 79, 100),       # 5 xanh, dong 100 > 99 -> MUA
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    s = got[0]
    assert s.direction == BUY
    assert s.level == 99
    assert s.bar == 5
    assert s.wait == 2
    assert s.close == 100


def test_nen_none_khong_gop_gi_vao_may_trang_thai():
    """F4: `session[i] is None` phai bo qua nen HOAN TOAN — khong gom range,
    khong lap moc, khong ban tin hieu — du du lieu nen do co du hinh dang
    mot setup hop le.

    Nen 0-6 co session=None va lap lai NGUYEN VAN hinh dang cua mot ca BAN
    day du (cua so -> nen do lam moc -> pha len -> ve trong range -> xuyen
    moc). Vi tat ca deu None nen ban dung phai KHONG sinh tin hieu nao tu
    doan nay. Nen 7-11 la mot phien S2 that, lap lai chinh xac cung hinh
    dang, va PHAI sinh dung mot tin hieu BAN.

    Neu `if s is None: continue` bi doi thanh `pass`, doan None (nen 0-6)
    se duoc xu ly y het mot phien that va tu no sinh ra mot tin hieu BAN ma
    khong ai muon — tin hieu do se nam LAN trong danh sach ket qua cung voi
    tin hieu that cua S2.
    """
    bars = [
        Bar(100, 110, 90, 105),   # 0 None, cua so
        Bar(105, 108, 95, 100),   # 1 None, cua so
        Bar(100, 104, 99, 103),   # 2 None, trong range
        Bar(106, 107, 101, 102),  # 3 None, do -> lai moc 102
        Bar(103, 115, 102, 112),  # 4 None, pha len -> (se arm neu khong bi bo qua)
        Bar(112, 113, 108, 109),  # 5 None, do, ve trong range
        Bar(109, 110, 100, 101),  # 6 None, do, xuyen moc (se BAN neu khong bi bo qua)
        Bar(100, 110, 90, 105),   # 7 S2, cua so
        Bar(105, 108, 95, 100),   # 8 S2, cua so
        Bar(105, 106, 100, 102),  # 9 S2, do -> lai moc 102
        Bar(103, 115, 102, 112),  # 10 S2, pha len -> arm o 102
        Bar(112, 113, 100, 101),  # 11 S2, do, xuyen moc -> BAN that
    ]
    session = [None] * 7 + ["S2"] * 5
    in_window = [True, True, False, False, False, False, False,
                 True, True, False, False, False]

    got = run(bars, session, in_window, min_range_bars=2)

    assert got == [Signal(SELL, 11, 102, 101, 1, "S2")]


def test_ban_disarm_sau_khi_ban_da_ban_khong_ban_lai():
    """F1 (vong soat cuoi). Sau khi tin hieu BAN da ban, up_armed phai tat
    (disarm). Neu khong, MOI nen tiep theo dong duoi up_level se lai sinh
    them mot tin hieu BAN trung lap cho CUNG mot cu pha — tren chart that,
    mot nhip troi nhieu nen duoi upLevel se sinh nhieu mui ten va nhieu
    alert() trung nhau cho cung mot setup.

    Noi tiep test_ban_day_du: sau nen 6 (BAN, level=102, close=101), them
    nen 7 dong 97, van duoi 102. Neu up_armed khong bi tat o buoc 2 thi
    nen 7 cung ban -> len(got) == 2. Dung phai chi co 1 tin hieu cho ca
    chuoi.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (100, 104, 99, 103),      # 2 xanh, trong range
        (106, 107, 101, 102),     # 3 DO  -> last_dn = 102
        (103, 115, 102, 112),     # 4 pha len
        (112, 113, 108, 109),     # 5 do, ve trong range
        (109, 110, 100, 101),     # 6 do, xuyen muc -> BAN
        (101, 102, 96, 97),       # 7 do, van duoi 102 -> KHONG duoc ban lai
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].bar == 6


def test_mua_disarm_sau_khi_mua_da_ban_khong_ban_lai():
    """F1 (vong soat cuoi), chieu MUA soi guong. Sau khi tin hieu MUA da
    ban, dn_armed phai tat. Neu khong, nen tiep theo dong tren dn_level se
    sinh them mot tin hieu MUA trung lap cho CUNG mot cu pha.

    Noi tiep test_mua_guong_qua_bien_duoi: sau nen 4 (MUA, level=99,
    close=100), them nen 5 dong 100, van tren 99. Neu dn_armed khong bi tat
    thi nen 5 cung ban -> len(got) == 2.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (95, 100, 94, 99),        # 2 XANH -> last_up = 99
        (95, 96, 85, 86),         # 3 pha xuong -> arm o 99
        (86, 102, 85, 100),       # 4 xanh, 100 > 99 -> MUA
        (98, 101, 97, 100),       # 5 xanh, van tren 99 -> KHONG duoc ban lai
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    assert got[0].bar == 4


def test_doji_khong_duoc_dat_last_up_va_lam_hong_muc_pha_xuong():
    """F4 (vong soat cuoi). Spec 3.3: doji (close == open) khong duoc cap
    nhat last_dn CUNG KHONG duoc cap nhat last_up.

    nen 2 XANH close=99 -> last_up that = 99 (X).
    nen 3 DOJI open=close=102 -> khong doi gi (dung). Neu dieu kien
    `elif bar.c > bar.o` bi doi thanh `else` (bat ky nen nao khong DO deu
    duoc coi la XANH) thi doji nay se dat last_up = 102 (Y), sai vi no
    khong phai nen xanh that.
    nen 4 do, dong 85 < rl(90) -> pha xuong, arm o last_up hien co
    (X=99 dung, hoac Y=102 neu hong).
    nen 5 xanh dong 100: 100 > 99 (X) -> MUA ngay, level=99, wait=1.
    Neu moc la 102 (Y) thi 100 khong > 102 -> KHONG ban gi ca o day.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (95, 100, 94, 99),        # 2 XANH -> last_up = 99 = X
        (102, 105, 99, 102),      # 3 DOJI open=close=102 -> khong doi gi
        (91, 92, 84, 85),         # 4 do, pha xuong -> arm o last_up
        (95, 101, 94, 100),       # 5 xanh, dong 100
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    s = got[0]
    assert s.direction == BUY
    assert s.level == 99
    assert s.bar == 5
    assert s.wait == 1
    assert s.close == 100


def test_dong_dung_bang_bien_tren_bat_lai_up_eligible():
    """F5 (vong soat cuoi). Spec 3.2: `upEligible` bat lai khi
    `rangeLow <= close <= rangeHigh` — bao ham CA HAI bien, khong phai
    khoang mo.

    nen 3 pha len lan 1 -> arm o 102 (tu nen 2), up_bar=3, up_el=False.
    nen 4 xanh dong DUNG BANG rangeHigh (110) -> neu dung `<=` (dung) thi
    up_el bat lai True; neu dung `<` chat (hong) thi up_el van False.
    nen 5 dong 115 > rh, pha len LAN HAI: chi duoc tinh la cu pha moi (va
    re-arm, doi up_bar tu 3 sang 5) NEU up_el dang True tu nen 4.
    nen 6 dong 101 < 102 -> BAN. Dung: up_bar=5 nen wait = 6-5 = 1. Neu
    khong bat lai duoc up_el o nen 4 thi up_bar van la 3, wait = 6-3 = 3.
    """
    bars, sess, win = mk([
        (100, 110, 90, 105),      # 0 cua so
        (105, 108, 95, 100),      # 1 cua so
        (106, 107, 101, 102),     # 2 DO -> last_dn = 102
        (103, 115, 102, 112),     # 3 pha len lan 1 -> arm o 102, up_bar=3
        (105, 111, 104, 110),     # 4 xanh, dong DUNG BANG rangeHigh (110)
        (105, 116, 104, 115),     # 5 dong 115 > rh -> pha len lan 2 (neu duoc)
        (112, 113, 100, 101),     # 6 do, 101 < 102 -> BAN
    ])

    got = run(bars, sess, win, min_range_bars=2)

    assert len(got) == 1
    s = got[0]
    assert s.direction == SELL
    assert s.level == 102
    assert s.bar == 6
    assert s.wait == 1
