"""Test cho momexp_oracle — pattern ba nen tang tien dong luong.

Moi nen la Candle(o, h, l, c). Thu tu tham so cua detect la (n3, n2, n1),
tuc CU NHAT TRUOC — nguoc voi chi so Pine [2],[1],[0]. Co y nhu vay: cho
dich giua hai cach danh so nam o dung mot noi.
"""
import random

from momexp_oracle import BEAR, BULL, Candle, detect


# Bang so cua spec section 2.5
N3_BULL = Candle(100.0, 103.0, 99.0, 102.0)
N2_BULL = Candle(102.0, 105.0, 101.0, 104.0)
N1_BULL = Candle(104.0, 107.0, 103.5, 106.0)


def test_bull_day_du():
    assert detect(N3_BULL, N2_BULL, N1_BULL) == BULL


# ------------------------------------------------------------------ BEAR
N3_BEAR = Candle(100.0, 101.0, 97.0, 98.0)
N2_BEAR = Candle(98.0, 99.0, 95.0, 96.0)
N1_BEAR = Candle(96.0, 96.5, 93.0, 94.0)


def test_bear_day_du():
    assert detect(N3_BEAR, N2_BEAR, N1_BEAR) == BEAR


# ------------------------------------- bat doi xung co y: n1 chong lan n2
def test_n1_chong_n2_van_hop_le():
    """Spec section 2.5. Day la ly do dieu kien 4 dung n3 chu khong phai n2."""
    assert N1_BULL.l < N2_BULL.h          # co chong lan that
    assert detect(N3_BULL, N2_BULL, N1_BULL) == BULL


# ------------------------------------------------------------------ doji
def test_doji_o_n3_thi_khong_tinh():
    n3 = Candle(102.0, 103.0, 99.0, 102.0)      # c == o
    assert detect(n3, N2_BULL, N1_BULL) is None


def test_doji_o_n2_thi_khong_tinh():
    n2 = Candle(104.0, 105.0, 101.0, 104.0)     # c == o
    assert detect(N3_BULL, n2, N1_BULL) is None


def test_doji_o_n1_thi_khong_tinh():
    n1 = Candle(106.0, 107.0, 103.5, 106.0)     # c == o
    assert detect(N3_BULL, N2_BULL, n1) is None


# ----------------------------------------------------------------- bien
def test_bien_n2_close_bang_dung_dinh_n3():
    """Luat la `>` chat: dong cua dung bang dinh nen truoc KHONG tinh."""
    n2 = Candle(102.0, 105.0, 101.0, 103.0)     # c == n3.h == 103
    assert detect(N3_BULL, n2, N1_BULL) is None


def test_bien_n1_low_bang_dung_dinh_n3():
    n1 = Candle(104.0, 107.0, 103.0, 106.0)     # l == n3.h == 103
    assert detect(N3_BULL, N2_BULL, n1) is None


def test_bien_n1_close_bang_dung_dinh_n2():
    n1 = Candle(104.0, 107.0, 103.5, 105.0)     # c == n2.h == 105
    assert detect(N3_BULL, N2_BULL, n1) is None


# ---------------------------------------------- bo tung dieu kien mot
def test_bo_dieu_kien_1_mot_nen_khong_xanh():
    n2 = Candle(105.0, 105.0, 101.0, 104.0)     # do: c 104 < o 105
    assert detect(N3_BULL, n2, N1_BULL) is None


def test_bo_dieu_kien_2_n2_dong_duoi_dinh_n3():
    n2 = Candle(100.0, 105.0, 99.0, 102.5)      # xanh, nhung c 102.5 < 103
    assert detect(N3_BULL, n2, N1_BULL) is None


def test_bo_dieu_kien_3_n1_dong_duoi_dinh_n2():
    n1 = Candle(104.0, 107.0, 103.5, 104.5)     # xanh, nhung c 104.5 < 105
    assert detect(N3_BULL, N2_BULL, n1) is None


def test_bo_dieu_kien_4_n1_khong_thoat_range_n3():
    n1 = Candle(104.0, 107.0, 102.0, 106.0)     # xanh, nhung l 102 < 103
    assert detect(N3_BULL, N2_BULL, n1) is None


# -------------------------------------------------------------- di ngang
def test_ba_nen_xanh_nhung_di_ngang():
    n3 = Candle(100.0, 101.0, 99.0, 100.5)
    n2 = Candle(100.5, 101.5, 99.5, 100.8)      # c 100.8 < n3.h 101
    n1 = Candle(100.8, 101.2, 100.0, 101.0)
    assert detect(n3, n2, n1) is None


# --------------------------------------------- tinh chat tren du lieu ngau nhien
def _rand_candle(rng):
    a, b = rng.uniform(90, 110), rng.uniform(90, 110)
    o, c = rng.uniform(min(a, b), max(a, b)), rng.uniform(min(a, b), max(a, b))
    return Candle(o, max(a, b), min(a, b), c)


def test_ket_qua_luon_thuoc_ba_gia_tri():
    rng = random.Random(20260913)
    for _ in range(5000):
        r = detect(_rand_candle(rng), _rand_candle(rng), _rand_candle(rng))
        assert r in (BULL, BEAR, None)


def test_BULL_keo_theo_du_bon_dieu_kien():
    """Neu detect noi BULL thi ca bon dieu kien phai that su dung.

    _rand_candle sinh doc lap, khong dinh huong. Da kiem tra bang tay
    truoc khi dua vao test: voi seed 20260914, 20000 vong sinh duoc 115
    ca BULL (~0.6%) — du de assert seen > 0 khong bi flaky, nen khong
    can dung du lieu dinh huong (n2/n1 dich len co chu dich) nhu brief
    cho phep o Step 7.
    """
    rng = random.Random(20260914)
    seen = 0
    for _ in range(20000):
        n3, n2, n1 = (_rand_candle(rng) for _ in range(3))
        if detect(n3, n2, n1) == BULL:
            seen += 1
            assert n3.c > n3.o and n2.c > n2.o and n1.c > n1.o
            assert n2.c > n3.h
            assert n1.c > n2.h
            assert n1.l > n3.h
    assert seen > 0, "fuzz khong sinh duoc ca BULL nao — doi seed"


def test_BEAR_keo_theo_du_bon_dieu_kien():
    """Cung cach sinh nhu test BULL o tren; seed 20260915 cho 126 ca BEAR
    tren 20000 vong (~0.6%), da kiem tra bang tay truoc khi dua vao test.
    """
    rng = random.Random(20260915)
    seen = 0
    for _ in range(20000):
        n3, n2, n1 = (_rand_candle(rng) for _ in range(3))
        if detect(n3, n2, n1) == BEAR:
            seen += 1
            assert n3.c < n3.o and n2.c < n2.o and n1.c < n1.o
            assert n2.c < n3.l
            assert n1.c < n2.l
            assert n1.h < n3.l
    assert seen > 0, "fuzz khong sinh duoc ca BEAR nao — doi seed"
