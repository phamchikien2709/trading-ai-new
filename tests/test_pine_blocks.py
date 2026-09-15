"""Guard chong troi giua cac ban chep khoi Pine.

Pine khong co module system, nen ban strategy CHEP NGUYEN VAN khoi tin hieu
tu ban indicator. Khong co gi canh thi hai ban troi khoi nhau am tham va
chart ve mot dang con lenh chay mot dang khac.

Truoc day guard nay la mot script trong scratchpad cua phien lam viec. Phien
ket thuc thi guard bien mat trong khi header cua bon file Pine van tro vao no.
Gio no la test, nen no tu chay.
"""
from pathlib import Path

from pine_blocks import ALLOWED, collect_blocks, drift

PINE = Path(__file__).resolve().parent.parent / "pine"


def test_khong_co_cho_nao_troi_ngoai_danh_sach_ngoai_le():
    assert drift(PINE, ALLOWED) == []


def test_guard_that_su_thay_cac_vung_dang_co():
    """Neu bo loc hong thi drift() tra ve rong VI KHONG THAY GI, va test tren
    xanh vi ly do sai. Ghim rang cac vung that su duoc gom."""
    blocks = collect_blocks(PINE)
    assert "TIN HIEU" in blocks
    assert len(blocks["TIN HIEU"]) >= 2


def test_ngoai_le_ghi_dich_danh_ca_hai_dong():
    """Ngoai le phai la cap dong cu the, KHONG phai nguong "cho lech N dong" —
    nguong thi bat cu cho troi nao khac cung lot qua."""
    for key, pairs in ALLOWED.items():
        assert len(key) == 3
        for old, new in pairs:
            assert isinstance(old, str) and isinstance(new, str)
            assert old != new
