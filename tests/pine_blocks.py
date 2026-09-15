"""Gom cac vung duoc boc bang moc va so tung dong giua cac ban chep.

Moi khoi dung chung duoc boc bang mot cap moc:
    // ---- KHOI <ten> ----
    ...
    // ---- HET KHOI <ten> ----

File dau tien theo thu tu alphabet lam ban goc.

Nhung cho CO Y lech nhau ghi dich danh trong ALLOWED — ghi CA NOI DUNG hai
dong, khong phai "cho lech N dong": mot nguong dem thi bat cu cho troi nao
khac cung lot qua.
"""
import difflib
import re

OPEN = re.compile(r"^//\s*----\s*KHOI\s+(.+?)\s*----\s*$")
CLOSE = re.compile(r"^//\s*----\s*HET KHOI\s+(.+?)\s*----\s*$")

# (ten_vung, file_goc, file_so) -> [(dong_trong_file_goc, dong_trong_file_so)]
#
# kill_peak: khoi tin hieu duoc phep lech DUNG hai dong gate vi the. Da ghi
# trong header ca hai file. Bat cu cho lech thu ba nao la troi that.
ALLOWED = {
    ("TIN HIEU", "kill_peak_indicator.pine", "kill_peak_strategy.pine"): [
        ("if lowConf and enableBuy and flagBuy and not posOpen and not na(prevLowP) and not na(atr)",
         "if lowConf and enableBuy and flagBuy and strategy.position_size == 0 and not na(prevLowP) and not na(atr)"),
        ("if highConf and enableSell and flagSell and not posOpen and not na(prevHighP) and not na(atr)",
         "if highConf and enableSell and flagSell and strategy.position_size == 0 and not na(prevHighP) and not na(atr)"),
    ],
}


def collect_blocks(pine_dir):
    """{ten_vung: {ten_file: [cac dong ben trong, khong ke hai moc]}}"""
    out = {}
    for path in sorted(pine_dir.glob("*.pine")):
        name = None
        buf = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if name is None:
                m = OPEN.match(line)
                if m:
                    name, buf = m.group(1), []
                continue
            m = CLOSE.match(line)
            if m:
                out.setdefault(name, {})[path.name] = buf
                name = None
                continue
            buf.append(line)
    return out


def _diff_pairs(a, b):
    """Cac cap (dong_cu, dong_moi). Dong chi co o mot ben ghep voi chuoi rong."""
    pairs = []
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        old = a[i1:i2]
        new = b[j1:j2]
        for k in range(max(len(old), len(new))):
            pairs.append((old[k] if k < len(old) else "",
                          new[k] if k < len(new) else ""))
    return pairs


def drift(pine_dir, allowed):
    """Mo ta tung cho lech KHONG nam trong `allowed`. Rong = sach."""
    problems = []
    for region, by_file in sorted(collect_blocks(pine_dir).items()):
        names = sorted(by_file)
        if len(names) < 2:
            continue
        base = names[0]
        for other in names[1:]:
            ok = list(allowed.get((region, base, other), []))
            for old, new in _diff_pairs(by_file[base], by_file[other]):
                if (old, new) in ok:
                    continue
                problems.append(
                    "%s: %s vs %s\n  -%s\n  +%s" % (region, base, other, old, new)
                )
    return problems
