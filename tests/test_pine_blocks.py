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
    xanh vi ly do sai. Ghim rang cac vung that su duoc gom.

    Ghim ca RSITP: neu mot moc cua vung nay hong (doi ten, doi hoa/thuong,
    hoac bi xoa) thi khoi do chi con gom duoc TU MOT file, va drift() bo qua
    (len(names) < 2) roi coi nhu sach — vung troi tu do ma toan suite van
    xanh. Day chinh la co che kill_peak da mac."""
    blocks = collect_blocks(PINE)
    assert "TIN HIEU" in blocks
    assert len(blocks["TIN HIEU"]) >= 2
    assert "RSITP" in blocks
    assert len(blocks["RSITP"]) == 2


def test_ngoai_le_ghi_dich_danh_ca_hai_dong():
    """Ngoai le phai la cap dong cu the, KHONG phai nguong "cho lech N dong" —
    nguong thi bat cu cho troi nao khac cung lot qua."""
    for key, pairs in ALLOWED.items():
        assert len(key) == 3
        for old, new in pairs:
            assert isinstance(old, str) and isinstance(new, str)
            assert old != new


def test_drift_phat_hien_duoc_lech_that(tmp_path):
    """Guard phai phat hien lech that, khong chi khang dinh sach tren du lieu
    repo hien co."""
    # Tao hai file gia voi cung vung nhung noi dung lech
    aaa = tmp_path / "aaa_indicator.pine"
    bbb = tmp_path / "bbb_strategy.pine"

    aaa.write_text(
        "// ---- KHOI THU ----\n"
        "var int x = 10\n"
        "var int y = 20\n"
        "// ---- HET KHOI THU ----\n",
        encoding="utf-8"
    )
    bbb.write_text(
        "// ---- KHOI THU ----\n"
        "var int x = 10\n"
        "var int y = 30\n"
        "// ---- HET KHOI THU ----\n",
        encoding="utf-8"
    )

    # drift() voi ALLOWED rong phai tra non-empty, co ten vung, ten file, va cap dong
    result = drift(tmp_path, {})
    assert result, "drift() phai phat hien lech"
    assert len(result) == 1
    assert "THU" in result[0]
    assert "aaa_indicator.pine" in result[0]
    assert "bbb_strategy.pine" in result[0]
    assert "var int y = 20" in result[0]
    assert "var int y = 30" in result[0]

    # Cung bo file, nhung ALLOWED co cap lech ay => drift() phai tra []
    allowed_with_pair = {
        ("THU", "aaa_indicator.pine", "bbb_strategy.pine"): [
            ("var int y = 20", "var int y = 30"),
        ]
    }
    result_allowed = drift(tmp_path, allowed_with_pair)
    assert result_allowed == [], "drift() phai bo qua lech trong ALLOWED"


def test_drift_phat_hien_lech_so_dong(tmp_path):
    """Phat hien lech kieu them hang mot dong (khong phai 1-doi-1)."""
    aaa = tmp_path / "aaa_indicator.pine"
    bbb = tmp_path / "bbb_strategy.pine"

    aaa.write_text(
        "// ---- KHOI THU2 ----\n"
        "line1\n"
        "line2\n"
        "// ---- HET KHOI THU2 ----\n",
        encoding="utf-8"
    )
    bbb.write_text(
        "// ---- KHOI THU2 ----\n"
        "line1\n"
        "line1b\n"
        "line2\n"
        "// ---- HET KHOI THU2 ----\n",
        encoding="utf-8"
    )

    result = drift(tmp_path, {})
    assert result, "drift() phai phat hien lech so dong"
    assert len(result) >= 1
    assert "THU2" in result[0]
