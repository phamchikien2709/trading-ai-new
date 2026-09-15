"""Test cho rsitp_oracle — setup RSI theo xu huong.

Spec: docs/superpowers/specs/2026-09-15-rsi-trend-pullback-design.md

Oracle nhan rsi/atr da tinh san: RSI va ATR la ham dung san cua TradingView,
khong phai thu dang co rui ro. Thu co rui ro la MAY TRANG THAI, THU TU trong
mot nen, va so hoc rr.
"""
from rsitp_oracle import BUY, SELL, Bar, run


def test_ban_day_du():
    """rsi thung 25 o nen 1, hoi len 55 o nen 4.

    day theo doi = min(100, 98, 99, 101) = 98
    entry = close nen 4 = 104
    SL    = 104 + 3*2 = 110
    TP    = 98  - 1*2 = 96
    rr    = (104 - 96) / (3*2) = 8/6
    cho   = 4 - 1 = 3 nen
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(101, 98, 99),
            Bar(102, 99, 100), Bar(105, 101, 104)]
    rsi = [60.0, 20.0, 22.0, 35.0, 55.0]
    atr = [2.0] * 5

    got = run(bars, rsi, atr)

    assert len(got) == 1
    s = got[0]
    assert s.direction == SELL and s.bar == 4
    assert s.entry == 104.0
    assert s.sl == 110.0
    assert s.tp == 96.0
    assert s.rr == 8 / 6
    assert s.wait == 3


def test_low_cua_chinh_nen_entry_duoc_tinh_vao_day():
    """Buoc 1 PHAI truoc buoc 2. Nen 2 vua tao day moi vua ban.

    day = min(100, 95) = 95 -> TP = 95 - 2 = 93, rr = (99-93)/6 = 1.0
    Neu buoc 1 chay SAU buoc 2 thi day van la 100 -> TP = 98, rr = 1/6.
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(100, 95, 99)]
    rsi = [60.0, 20.0, 55.0]
    atr = [2.0] * 3

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].tp == 93.0
    assert got[0].rr == 1.0


def test_day_la_min_ca_cua_so_chu_khong_phai_low_nen_entry():
    """day = min(100, 90, 97) = 90 -> TP = 88, rr = (101-88)/6 = 13/6.
    Neu chi lay low cua nen entry (97) thi TP = 95 va rr = 1.0."""
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(95, 90, 92),
            Bar(103, 97, 101)]
    rsi = [60.0, 20.0, 22.0, 55.0]
    atr = [2.0] * 4

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].tp == 88.0
    assert got[0].rr == 13 / 6


def test_thung_25_lan_nua_khong_mo_cua_so_moi():
    """Spec 2.3: cua so lien mach tu cu thung 25 DAU TIEN toi nen entry.
    RSI tut lai duoi 25 o nen 3 chi keo dai day dang theo doi.

    day = min(100, 95, 97) = 95 -> TP = 93, cho = 4 - 1 = 3.
    Neu nen 3 mo cua so moi thi day = min(97, 99) = 97, TP = 95, cho = 1.
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(99, 95, 98),
            Bar(101, 97, 99), Bar(105, 99, 103)]
    rsi = [60.0, 20.0, 40.0, 22.0, 55.0]
    atr = [2.0] * 5

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].tp == 93.0
    assert got[0].wait == 3


def test_rsi_dung_bang_muc_giua_khong_ban():
    """Luat la `>` chat. 50.0 chan; 50.5 moi ban."""
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(103, 99, 102),
            Bar(104, 100, 103)]
    rsi = [60.0, 20.0, 50.0, 50.5]
    atr = [2.0] * 4

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].bar == 3


def test_setup_bi_tieu_thu_sau_khi_ban():
    """Ban xong ve IDLE. Nen 3 co RSI 60 nhung khong con setup nao."""
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(105, 100, 104),
            Bar(108, 103, 107)]
    rsi = [60.0, 20.0, 55.0, 60.0]
    atr = [2.0] * 4

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].bar == 2


def test_mua_guong_qua_75():
    """dinh theo doi = max(200, 205) = 205
    entry = 198, SL = 198 - 6 = 192, TP = 205 + 2 = 207
    rr = (207 - 198) / 6 = 1.5, cho = 3 - 1 = 2
    """
    bars = [Bar(150, 145, 148), Bar(200, 195, 199), Bar(205, 198, 203),
            Bar(202, 196, 198)]
    rsi = [50.0, 80.0, 78.0, 45.0]
    atr = [2.0] * 4

    got = run(bars, rsi, atr)

    assert len(got) == 1
    b = got[0]
    assert b.direction == BUY and b.bar == 3
    assert b.sl == 192.0
    assert b.tp == 207.0
    assert b.rr == 1.5
    assert b.wait == 2


def test_rsi_nhay_tu_24_len_80_trong_mot_nen():
    """Khoi BAN chay TRUOC khoi MUA tren cung mot nen: ban ban ra roi pha mua
    moi mo. Hai chieu khong bao gio cung SEEKING.

    nen 2: BAN ban (day 100 -> TP 98), roi MUA mo pha voi dinh 210.
    nen 3: MUA ban, dinh = max(210, 208) = 210 -> TP = 212, cho = 1.
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(210, 102, 205),
            Bar(208, 200, 206)]
    rsi = [60.0, 24.0, 80.0, 40.0]
    atr = [2.0] * 4

    got = run(bars, rsi, atr)

    assert len(got) == 2
    assert got[0].direction == SELL and got[0].bar == 2 and got[0].tp == 98.0
    assert got[1].direction == BUY and got[1].bar == 3
    assert got[1].tp == 212.0
    assert got[1].wait == 1


def test_atr_bang_0_khong_ban_nhung_van_tieu_thu_setup():
    """Mau so cua rr bang 0 -> khong do duoc rui ro -> khong danh dau. Nhung
    setup VAN bi tieu thu, nen cu thung 25 o nen 4 mo mot cua so MOI.

    `cho == 1` la bang chung: neu setup cu con song thi cho se la 5 - 1 = 4.
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(105, 100, 104),
            Bar(108, 103, 107), Bar(103, 99, 100), Bar(104, 100, 103)]
    rsi = [60.0, 20.0, 55.0, 60.0, 20.0, 55.0]
    atr = [0.0, 0.0, 0.0, 0.0, 2.0, 2.0]

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].bar == 5
    assert got[0].wait == 1


def test_tat_mot_chieu_khong_anh_huong_chieu_kia():
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(105, 100, 104)]
    rsi = [60.0, 20.0, 55.0]
    atr = [2.0] * 3

    assert run(bars, rsi, atr, enable_sell=False) == []
    assert len(run(bars, rsi, atr, enable_buy=False)) == 1


def test_warm_up_khong_lam_gi():
    """rsi hoac atr la None thi khong trang thai nao doi."""
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(103, 99, 100),
            Bar(102, 98, 99), Bar(105, 101, 104)]
    rsi = [None, 20.0, None, 20.0, 55.0]
    atr = [None, None, 2.0, 2.0, 2.0]

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].wait == 1          # cua so mo o nen 3, khong phai nen 1
