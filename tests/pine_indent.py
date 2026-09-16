"""Checker heuristic cho thut dong noi tiep trong file Pine.

Spec 8.4: thut dong noi tiep (dong nam trong mot loi goi ham/tuple con dang
mo ngoac tu (cac) dong truoc) PHAI KHONG chia het cho 4 -- Pine doc thut 4
hoac 8 thanh mot KHOI MOI, khong bao loi gi ca, chi doi hanh vi am tham.
Truoc day muc nay chi duoc kiem tay roi bien mat cung phien lam viec, dung
bai hoc da ghi trong docstring cua tests/pine_blocks.py -- gio no la mot
checker song trong version control.

GIOI HAN CUA HEURISTIC NAY -- DOC KY TRUOC KHI TIN:

- **KHONG PHAI PARSER PINE DAY DU.** Day la mot bo dem ngoac o muc ky tu,
  khong hieu ngu phap Pine.
- Chi theo doi ngoac TRON `()`. KHONG xu ly `[]` hay `{}` (Pine it dung
  nhung khong phai khong co), va KHONG xu ly cac kieu noi tiep khac khong
  dung ngoac (vi du dinh nghia ham nhieu dong ky la bang thut don thuan).
- Bo comment `//` va noi dung ben trong chuoi `"..."` bang mot bo quet
  TUYEN TINH qua tung ky tu (theo doi dang o trong chuoi hay khong). No
  hieu escape `\\"` don gian nhung KHONG phai lexer Pine that: mot chuoi
  bi mo ma khong dong tren cung dong (loi cu phap that su) co the lam bo
  dem lech cho toi het file.
- Do thut bang SO KY TU TRANG DAU DONG (dem tung dau cach). Neu file dung
  tab thay vi space thi con so nay mat y nghia truc tiep.
- Neu bo dem ngoac tuot am (thua dong dong) thi CLAMP VE 0 thay vi de am
  lan sang cac dong/file khac -- tranh bao dong nhieu that khi thuc ra chi
  la mot ngoac thua o dau do.

Noi cach khac: day la MOT BO LOC RE VA NHANH de bat mot lop loi cu the (thut
4/8 tren dong noi tiep that), khong phai bang chung Pine se compile dung.
Dung cung viec doc tay khi nghi ngo.
"""
import re

_QUOTE = '"'
_ESCAPE = "\\"


def _strip_comment_and_strings(line):
    """Tra ve `line` sau khi cat comment `//` (ngoai chuoi) va thay noi dung
    ben trong chuoi bang khoang trang (giu nguyen do dai va vi tri ngoac
    ben ngoai chuoi, neu co, de debug de hon)."""
    out = []
    in_str = False
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if in_str:
            if ch == _ESCAPE and i + 1 < n:
                out.append("  ")  # giu do dai, khong doi trang thai chuoi
                i += 2
                continue
            if ch == _QUOTE:
                in_str = False
                out.append(ch)
                i += 1
                continue
            out.append(" ")
            i += 1
            continue
        if ch == _QUOTE:
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and line[i + 1] == "/":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def find_continuation_lines(text):
    """Tra ve `[(so_dong_1_based, thut, noi_dung_goc), ...]` cho moi dong
    ma, TRUOC KHI xu ly ky tu nao cua chinh no, dang nam trong mot cap
    ngoac tron chua dong tu (cac) dong phia truoc.

    Thuat toan: quet tung dong theo thu tu, bo comment/chuoi, cong don so
    `(` tru so `)`. Dong nao bat dau voi bo dem tich luy > 0 la dong noi
    tiep that (dang o giua mot loi goi/tuple chua dong)."""
    depth = 0
    out = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if depth > 0:
            stripped = raw.lstrip(" ")
            indent = len(raw) - len(stripped)
            out.append((lineno, indent, raw))
        code = _strip_comment_and_strings(raw)
        depth += code.count("(") - code.count(")")
        if depth < 0:
            depth = 0
    return out
