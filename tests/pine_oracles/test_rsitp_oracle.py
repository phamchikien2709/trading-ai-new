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


def test_rsi_dung_bang_muc_giua_khong_mua():
    """Doi xung voi test_rsi_dung_bang_muc_giua_khong_ban, o chieu MUA.

    Luat la `<` chat. 50.0 chan; 49.5 moi mua.
    """
    bars = [Bar(110, 105, 108), Bar(115, 110, 112), Bar(114, 109, 111),
            Bar(113, 108, 110)]
    rsi = [50.0, 80.0, 50.0, 49.5]
    atr = [2.0] * 4

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].direction == BUY and got[0].bar == 3


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


def test_atr_bang_0_khong_mua_nhung_van_tieu_thu_setup():
    """Doi xung voi test_atr_bang_0_khong_ban_nhung_van_tieu_thu_setup, o
    chieu MUA: atr=0 -> khong do duoc rui ro -> khong ban, nhung setup van
    bi tieu thu nen cu vuot 75 o nen 3 mo mot cua so MOI.

    `cho == 1` la bang chung: neu cua so cu (mo o nen 1) con song thi cho se
    la 4 - 1 = 3.
    """
    bars = [Bar(150, 145, 148), Bar(200, 195, 199), Bar(198, 193, 196),
            Bar(204, 199, 200), Bar(202, 199, 201)]
    rsi = [50.0, 80.0, 45.0, 80.0, 45.0]
    atr = [0.0, 0.0, 0.0, 2.0, 2.0]

    got = run(bars, rsi, atr)

    assert len(got) == 1
    s = got[0]
    assert s.direction == BUY and s.bar == 4
    assert s.entry == 201.0
    assert s.sl == 195.0
    assert s.tp == 206.0
    assert s.rr == 5 / 6
    assert s.wait == 1


def test_tat_mot_chieu_khong_anh_huong_chieu_kia():
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(105, 100, 104)]
    rsi = [60.0, 20.0, 55.0]
    atr = [2.0] * 3

    assert run(bars, rsi, atr, enable_sell=False) == []
    assert len(run(bars, rsi, atr, enable_buy=False)) == 1


def test_setup_bi_tieu_thu_ke_ca_khi_tat_chieu_do():
    """Spec 2.7: `sSt := 0` nam NGOAI moi if con cua buoc 2, nen setup van bi
    tieu thu KE CA KHI chieu do bi tat -- cung tinh than voi
    test_atr_bang_0_khong_ban_nhung_van_tieu_thu_setup, nhung o day "khong do
    duoc rui ro" duoc thay bang "chieu bi tat".

    `enable_sell`/`enable_buy` la tham so cua CA LAN GOI, khong doi giua
    chung nen khong the tat nua dau, bat nua sau trong MOT lan goi run(). Vi
    the phep thu chia hai buoc tren CUNG mot chuoi hai pha lien tiep:

      1. goi voi chieu do TAT ca chuoi -- khong tin hieu nao ban o CA HAI
         pha (khong chi pha dau).
      2. goi LAI dung chuoi do voi chieu do BAT -- vi run() la mot lan mo
         phong doc lap moi lan goi (khong giu trang thai giua hai lan goi),
         day chinh la phep do "neu tat roi bat lai thi co bat dau sach hay
         khong": ca hai pha phai ban duoc, va `wait` cua pha thu hai phai
         tinh tu XBAR RIENG cua no (nho), khong dinh vao pha dau tien.
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(105, 100, 104),
            Bar(103, 98, 99), Bar(104, 99, 103)]
    rsi = [60.0, 20.0, 55.0, 20.0, 55.0]
    atr = [2.0] * 5

    assert run(bars, rsi, atr, enable_sell=False) == []

    got = run(bars, rsi, atr, enable_sell=True)
    assert len(got) == 2
    assert got[0].direction == SELL and got[0].bar == 2 and got[0].wait == 1
    assert got[1].direction == SELL and got[1].bar == 4 and got[1].wait == 1

    bars_buy = [Bar(150, 145, 148), Bar(200, 195, 199), Bar(198, 193, 196),
                Bar(203, 198, 200), Bar(198, 193, 197)]
    rsi_buy = [50.0, 80.0, 45.0, 80.0, 45.0]

    assert run(bars_buy, rsi_buy, atr, enable_buy=False) == []

    got_buy = run(bars_buy, rsi_buy, atr, enable_buy=True)
    assert len(got_buy) == 2
    assert (got_buy[0].direction == BUY and got_buy[0].bar == 2
            and got_buy[0].wait == 1)
    assert (got_buy[1].direction == BUY and got_buy[1].bar == 4
            and got_buy[1].wait == 1)


def test_rsi_dung_bang_25_khong_mo_pha_ban():
    """Khong test nao truoc day dung RSI DUNG BANG 25. Luat la `r < lo`
    (chat), nen 25.0 khong duoc mo pha -- phai la 24.9 tro xuong."""
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(105, 100, 104)]
    rsi = [60.0, 25.0, 55.0]
    atr = [2.0] * 3

    assert run(bars, rsi, atr) == []


def test_rsi_24_9_moi_mo_pha_ban():
    """Doi xung voi test tren: 24.9 moi thuc su mo pha."""
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(105, 100, 104)]
    rsi = [60.0, 24.9, 55.0]
    atr = [2.0] * 3

    got = run(bars, rsi, atr)
    assert len(got) == 1
    assert got[0].bar == 2


def test_rsi_dung_bang_75_khong_mo_pha_mua():
    """Guong voi test_rsi_dung_bang_25_khong_mo_pha_ban. Luat la `r > hi`
    (chat), nen 75.0 khong duoc mo pha -- phai la 75.1 tro len."""
    bars = [Bar(150, 145, 148), Bar(200, 195, 199), Bar(198, 193, 196)]
    rsi = [50.0, 75.0, 45.0]
    atr = [2.0] * 3

    assert run(bars, rsi, atr) == []


def test_rsi_75_1_moi_mo_pha_mua():
    """Doi xung voi test tren: 75.1 moi thuc su mo pha."""
    bars = [Bar(150, 145, 148), Bar(200, 195, 199), Bar(198, 193, 196)]
    rsi = [50.0, 75.1, 45.0]
    atr = [2.0] * 3

    got = run(bars, rsi, atr)
    assert len(got) == 1
    assert got[0].bar == 2


def test_tp_dung_atr_cua_nen_entry_khong_phai_nen_mo_pha():
    """Ca 13 vector truoc F7 deu dung ATR HANG trong moi test, nen khong gi
    ghim duoc ATR lay o nen nao: neu code lay ATR cua nen MO PHA (luc thung
    25) thay vi nen ENTRY (luc bat tin hieu) thi khong test nao trong so do
    phat hien duoc, vi hai gia tri giong het nhau.

    O day ATR nen mo pha (nen 1) = 5.0, ATR nen entry (nen 2) = 3.0 -- khac
    han nhau. TP va rr dung tren PHAI dung ATR nen entry (3.0).
    """
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(105, 100, 104)]
    rsi = [60.0, 20.0, 55.0]
    atr = [2.0, 5.0, 3.0]

    got = run(bars, rsi, atr)

    assert len(got) == 1
    s = got[0]
    assert s.entry == 104.0
    assert s.sl == 113.0          # 104 + 3*3.0 (atr nen entry)
    assert s.tp == 97.0           # 100 - 1*3.0 (atr nen entry, KHONG phai 95.0 = 100 - 1*5.0)
    assert s.rr == 7 / 9


def test_tp_mua_dung_atr_cua_nen_entry_khong_phai_nen_mo_pha():
    """Doi xung voi test tren, o chieu MUA."""
    bars = [Bar(150, 145, 148), Bar(200, 195, 199), Bar(198, 193, 196)]
    rsi = [50.0, 80.0, 45.0]
    atr = [2.0, 5.0, 3.0]

    got = run(bars, rsi, atr)

    assert len(got) == 1
    s = got[0]
    assert s.entry == 196.0
    assert s.sl == 187.0          # 196 - 3*3.0 (atr nen entry)
    assert s.tp == 203.0          # 200 + 1*3.0 (atr nen entry, KHONG phai 205.0 = 200 + 1*5.0)
    assert s.rr == 7 / 9


def test_warm_up_khong_lam_gi():
    """rsi hoac atr la None thi khong trang thai nao doi."""
    bars = [Bar(110, 105, 108), Bar(104, 100, 101), Bar(103, 99, 100),
            Bar(102, 98, 99), Bar(105, 101, 104)]
    rsi = [None, 20.0, None, 20.0, 55.0]
    atr = [None, None, 2.0, 2.0, 2.0]

    got = run(bars, rsi, atr)

    assert len(got) == 1
    assert got[0].wait == 1          # cua so mo o nen 3, khong phai nen 1
