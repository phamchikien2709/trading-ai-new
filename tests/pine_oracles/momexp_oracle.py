"""Pattern ba nen tang tien dong luong.

Spec: docs/superpowers/specs/2026-09-13-momentum-expansion-indicator-design.md

Ban goc de doi chieu voi pine/momentum_expansion.pine. Rui ro so mot cua
file Pine la LECH CHI SO: nguoi dung dat ten n1 moi nhat / n3 cu nhat,
con Pine danh so [0],[1],[2] cung lui ve qua khu. Lech mot chi so thi
pattern van chay, van ve, va sai am tham.

Vi vay detect() nhan tham so theo TEN CUA NGUOI DUNG — (n3, n2, n1), cu
nhat truoc — chu khong theo thu tu chi so Pine. Cho dich giua hai cach
danh so vi the nam o dung mot noi va bi test soi thang vao.
"""
from collections import namedtuple

Candle = namedtuple("Candle", "o h l c")

BULL = "BULL"
BEAR = "BEAR"


def _green(x):
    """Doji khong tinh la xanh: luat la `>` chat. Spec section 2.6."""
    return x.c > x.o


def _red(x):
    return x.c < x.o


def detect(n3, n2, n1):
    """n3 cu nhat, n1 moi nhat. Tra ve BULL, BEAR hoac None.

    Bon dieu kien chieu tang, moi cai doc lap (spec section 2.4):
      1. ca ba nen xanh
      2. n2 dong tren dinh n3
      3. n1 dong tren dinh n2
      4. n1 thoat han range n3

    Dieu kien 4 dung dinh cua N3 chu khong phai n2: n1 duoc phep chong lan
    n2. Bat doi xung nay la co y, xem spec section 2.5.
    """
    if (_green(n3) and _green(n2) and _green(n1)
            and n2.c > n3.h
            and n1.c > n2.h
            and n1.l > n3.h):
        return BULL

    if (_red(n3) and _red(n2) and _red(n1)
            and n2.c < n3.l
            and n1.c < n2.l
            and n1.h < n3.l):
        return BEAR

    return None
