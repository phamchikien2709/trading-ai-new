"""Test cho pine_indent.py -- hien vat cho bien phap 8.4 cua spec.

Truoc day day la mot script chay tay trong scratchpad cua phien lam viec,
roi bien mat khi phien ket thuc trong khi khong ai con nho de chay lai.
Gio no la test nen no tu chay moi lan pytest.
"""
from pathlib import Path

from pine_indent import find_continuation_lines

PINE = Path(__file__).resolve().parent.parent / "pine"


def test_thut_dong_noi_tiep_khong_chia_het_cho_4():
    """Repo dung thut 5/9/13 cho dong noi tiep, KHONG bao gio dung boi so
    cua 4 (Pine doc thut 4/8 thanh khoi moi, sai am tham, khong bao loi)."""
    problems = []
    for path in sorted(PINE.glob("*.pine")):
        text = path.read_text(encoding="utf-8")
        for lineno, indent, raw in find_continuation_lines(text):
            if indent % 4 == 0:
                problems.append(
                    "%s:%d: thut %d (chia het cho 4) - %r"
                    % (path.name, lineno, indent, raw)
                )
    assert not problems, "\n".join(problems)


def test_tim_duoc_dong_noi_tiep_that(tmp_path):
    """Guard cho chinh checker: no phai THAT SU tim duoc dong noi tiep,
    khong chi tra ve rong vi ly do sai."""
    f = tmp_path / "aaa.pine"
    f.write_text(
        "foo(a,\n"
        "    b,\n"
        "    c)\n",
        encoding="utf-8",
    )
    got = find_continuation_lines(f.read_text(encoding="utf-8"))
    assert len(got) == 2
    assert got[0][0] == 2 and got[0][1] == 4
    assert got[1][0] == 3 and got[1][1] == 4


def test_bo_qua_ngoac_trong_comment_va_chuoi():
    """Ngoac ben trong comment hoac chuoi khong duoc tinh vao bo dem --
    neu tinh nham thi moi dong sau se bi bao sai la dong noi tiep."""
    text = (
        'label.new(bar_index, high, "canh bao (test)"\n'
        "     // ham nay co ngoac (gia) trong comment, khong duoc dem\n"
        "     , color=color.red)\n"
        "plain = 1\n"
    )
    got = find_continuation_lines(text)
    # dong 2 va 3 la noi tiep that (tu ngoac mo o dong 1, dong 3 dong lai)
    linenos = [g[0] for g in got]
    assert linenos == [2, 3]
    # dong 4 (sau khi ngoac da dong) KHONG duoc coi la noi tiep
    assert 4 not in linenos
