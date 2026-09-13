# Kill Peak + Failure Swing (`kill_peak_fs`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cặp Pine indicator + strategy ghép bối cảnh M3 của `kill_peak` (đỉnh chờ kill) với máy trạng thái failure swing M1 của `rsi_failure_swing`, TP đặt đúng ở mức chờ kill.

**Architecture:** Ba tầng chạy tuần tự trong mỗi nến — khối bối cảnh HTF chép nguyên văn từ `kill_peak`, máy trạng thái M1 chép nguyên văn từ `rsi_failure_swing` (tách làm ba mảnh), và hai khối nối viết mới nằm ở vị trí bước 3 của máy M1. Chống trôi phiên bản giữa các bản chép bằng `blockdiff.py` quét toàn thư mục. Kiểm chứng bằng oracle Python bọc ngoài `rfs_oracle.py` có sẵn, cộng mutation testing.

**Tech Stack:** Pine Script v6; Python 3 + pytest cho oracle và công cụ (chạy trong scratchpad, không commit).

**Spec:** `docs/superpowers/specs/2026-09-13-kill-peak-fs-design.md`

---

## Global Constraints

Mọi task đều chịu các ràng buộc này. Đọc hết trước khi bắt đầu bất kì task nào.

- **KHÔNG COMPILE ĐƯỢC PINE Ở MÁY NÀY.** Không bao giờ viết "đã test", "đã chạy", "verified" về code Pine. Chỉ được nói "qua checker tĩnh", "đối chiếu với oracle", "đọc tay".
- **Thụt dòng nối tiếp trong Pine phải KHÔNG chia hết cho 4.** Repo dùng 5, 9, 13. Thụt 4 hoặc 8 bị Pine đọc thành khối mới.
- **Không gọi `ta.*` bên trong `if`.** Chúng giữ state nội bộ; gọi có điều kiện làm hỏng state âm thầm. Mọi `ta.*` phải ở top level.
- **`math.round()` trả về float.** Pine không tự thu hẹp float→int. Chia int/int bị cắt cụt.
- **`line.set_x2` trên handle `na` là runtime error** giết script giữa chart. Luôn guard `not na(handle)`.
- **`strategy()` mặc định 50 label.** Phải truyền `max_labels_count=500` tường minh. `indicator()` cũng truyền `max_lines_count=500, max_labels_count=500`.
- **Windows: xoá `__pycache__` trước mỗi lần chạy pytest sau khi copy file.** Hai lệnh `cp` liên tiếp cho mtime giống hệt nhau và Python dùng lại bytecode cũ. Lệnh: `rm -rf __pycache__`.
- **Scratchpad:** `C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad`. Dưới đây viết tắt là `<SP>`. File Python kiểm chứng nằm ở đó, **không commit**.
- **Heredoc bash hay vỡ khi nội dung có nháy.** Dùng công cụ Write cho nội dung file; heredoc chỉ dùng cho khối `python - <<'PYEOF'` thuần.
- **Commit message:** tiếng Việt không dấu, ASCII, viết vào file `.txt` trong scratchpad rồi `git commit -F <file>`. Kết thúc bằng dòng:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- **Nhánh:** `feat/h4-kill-study`. Không merge, không push.
- **Nếu một bước trong kế hoạch này mâu thuẫn với thực tế code, DỪNG và báo — không tự sửa test cho khớp code.** Ở dự án `kill_peak` đã có một test sai trong kế hoạch mà người thi công báo lên đúng thay vì sửa lén; đó là hành vi mong muốn.

### Bảng tên vùng chép (dùng xuyên suốt)

| Tên vùng | Mốc mở | Mốc đóng |
|---|---|---|
| Bối cảnh HTF | `// ---- KHOI BOI CANH HTF ----` | `// ---- HET KHOI BOI CANH HTF ----` |
| M1 mảnh A | `// ---- KHOI M1-A ----` | `// ---- HET KHOI M1-A ----` |
| M1 mảnh B | `// ---- KHOI M1-B ----` | `// ---- HET KHOI M1-B ----` |
| M1 mảnh C | `// ---- KHOI M1-C ----` | `// ---- HET KHOI M1-C ----` |

Spec §3 viết tắt mốc đóng là `HET KHOI BOI CANH`. Bảng này là bản chuẩn hoá: **tên ở hai đầu phải giống hệt nhau** thì công cụ mới ghép cặp được. Dùng bảng này, không dùng bản viết tắt trong spec.

---

## Cấu trúc file

| File | Trách nhiệm | Task |
|---|---|---|
| `<SP>/blockdiff.py` | Quét `pine/`, so mọi vùng cùng tên giữa mọi file | 1 |
| `<SP>/blockdiff_test.py` | Test cho công cụ trên | 1 |
| `<SP>/blockdiff_except.txt` | Ghi đích danh những cặp dòng được phép lệch | 1 |
| `pine/rsi_failure_swing_indicator.pine` | thêm mốc M1-A/B/C (chỉ comment) | 1 |
| `pine/rsi_failure_swing_strategy.pine` | thêm mốc M1-A/B/C (chỉ comment) | 1 |
| `pine/kill_peak_indicator.pine` | thêm mốc BOI CANH HTF (chỉ comment) | 1 |
| `pine/kill_peak_strategy.pine` | thêm mốc BOI CANH HTF (chỉ comment) | 1 |
| `<SP>/kpfs_oracle.py` | Máy HTF + khối nối, bọc ngoài `rfs_oracle.step_side` | 2, 3 |
| `<SP>/kpfs_test.py` | Test cho oracle trên | 2, 3 |
| `pine/kill_peak_fs_indicator.pine` | Script soi tay | 4, 5, 6 |
| `pine/kill_peak_fs_strategy.pine` | Script backtest | 7 |

Không sửa `<SP>/rfs_oracle.py` và `<SP>/rfs_test.py` — 20 test hiện có phải giữ nguyên xanh làm chứng cứ.

---

## Task 1: Công cụ chống trôi `blockdiff.py` + chuẩn hoá mốc

Rủi ro lớn nhất của hướng thi công này là trôi phiên bản: khối bối cảnh HTF sẽ tồn tại ở 4 file, khối M1 ở 4 file. Task này dựng công cụ bắt trôi bằng máy, và phải làm **trước** mọi task khác vì các task sau dùng nó làm cổng nghiệm thu.

**Files:**
- Create: `<SP>/blockdiff.py`
- Create: `<SP>/blockdiff_test.py`
- Create: `<SP>/blockdiff_except.txt`
- Modify: `pine/rsi_failure_swing_indicator.pine` (chỉ thêm/sửa dòng comment)
- Modify: `pine/rsi_failure_swing_strategy.pine` (chỉ thêm/sửa dòng comment)
- Modify: `pine/kill_peak_indicator.pine` (chỉ thêm dòng comment)
- Modify: `pine/kill_peak_strategy.pine` (chỉ thêm dòng comment)
- Delete: `<SP>/rfs_blockdiff.py` (bị thay thế)

**Interfaces:**
- Produces: `blockdiff.py` chạy bằng `python <SP>/blockdiff.py` từ thư mục gốc repo. In một dòng cho mỗi vùng, thoát mã 0 khi sạch, 1 khi có trôi ngoài danh sách ngoại lệ.
- Produces: bốn tên vùng ở bảng Global Constraints, có mặt trong các file Pine hiện có.

### Vì sao cần cơ chế ngoại lệ

Quét toàn `pine/` sẽ bắt gặp vùng `KHOI TIN HIEU` sẵn có của cặp `kill_peak`. Hai file đó **cố ý** lệch nhau đúng hai dòng (gate `not posOpen` ↔ `strategy.position_size == 0`), đã ghi trong header cả hai file. Công cụ phải biết chuyện này, nhưng **không được** chấp nhận kiểu "cho lệch tối đa N dòng" — như thế thì bất kì trôi nào khác cũng lọt. Phải ghi đích danh từng cặp dòng.

- [ ] **Step 1: Viết test đầu tiên — tách vùng theo mốc**

Tạo `<SP>/blockdiff_test.py`:

```python
"""Test cho blockdiff — cong cu chong troi giua cac ban chep khoi Pine."""
import io
import os
import pytest
from blockdiff import find_regions, compare, load_exceptions, Diff


def w(tmp_path, name, lines):
    p = tmp_path / name
    io.open(str(p), "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    return str(p)


def test_tach_mot_vung():
    src = [
        "khong tinh",
        "// ---- KHOI ABC ----",
        "a = 1",
        "b = 2",
        "// ---- HET KHOI ABC ----",
        "cung khong tinh",
    ]
    assert find_regions(src) == {"ABC": ["a = 1", "b = 2"]}


def test_tach_nhieu_vung():
    src = [
        "// ---- KHOI A ----", "x", "// ---- HET KHOI A ----",
        "giua",
        "// ---- KHOI B ----", "y", "z", "// ---- HET KHOI B ----",
    ]
    assert find_regions(src) == {"A": ["x"], "B": ["y", "z"]}


def test_moc_dong_sai_ten_thi_bao_loi():
    src = ["// ---- KHOI A ----", "x", "// ---- HET KHOI B ----"]
    with pytest.raises(ValueError):
        find_regions(src)


def test_moc_mo_khong_dong_thi_bao_loi():
    src = ["// ---- KHOI A ----", "x"]
    with pytest.raises(ValueError):
        find_regions(src)


def test_vung_trung_ten_trong_cung_file_thi_bao_loi():
    src = [
        "// ---- KHOI A ----", "x", "// ---- HET KHOI A ----",
        "// ---- KHOI A ----", "y", "// ---- HET KHOI A ----",
    ]
    with pytest.raises(ValueError):
        find_regions(src)
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest blockdiff_test.py -q
```

Kỳ vọng: FAIL, `ModuleNotFoundError: No module named 'blockdiff'`.

- [ ] **Step 3: Viết `find_regions`**

Tạo `<SP>/blockdiff.py`:

```python
"""Chong troi phien ban giua cac ban chep khoi Pine.

Moi khoi dung chung duoc boc bang mot cap moc:
    // ---- KHOI <ten> ----
    ...
    // ---- HET KHOI <ten> ----

Cong cu quet toan bo pine/, gom cac vung theo ten, va so tung dong giua
moi file chua cung mot ten. File dau tien theo thu tu alphabet lam ban goc.

Nhung cho CO Y lech nhau ghi dich danh trong blockdiff_except.txt — ghi ca
noi dung hai dong, khong phai "cho lech N dong": nguong dem thi bat cu troi
nao khac cung lot qua.

Chay tu thu muc goc repo:
    python <SP>/blockdiff.py
Thoat 0 = sach. Thoat 1 = co troi ngoai danh sach ngoai le.
"""
import difflib
import io
import os
import re
import sys

OPEN = re.compile(r"^//\s*----\s*KHOI\s+(.+?)\s*----\s*$")
CLOSE = re.compile(r"^//\s*----\s*HET KHOI\s+(.+?)\s*----\s*$")


def find_regions(lines):
    """Tra ve {ten: [dong, ...]} — noi dung GIUA hai moc, khong ke moc."""
    out = {}
    cur = None
    buf = []
    for ln in lines:
        mo = OPEN.match(ln)
        mc = CLOSE.match(ln)
        if mo:
            if cur is not None:
                raise ValueError("moc mo '%s' long trong '%s'" % (mo.group(1), cur))
            cur = mo.group(1)
            if cur in out:
                raise ValueError("vung '%s' xuat hien hai lan trong mot file" % cur)
            buf = []
        elif mc:
            if cur is None:
                raise ValueError("moc dong '%s' khong co moc mo" % mc.group(1))
            if mc.group(1) != cur:
                raise ValueError("moc dong '%s' khong khop moc mo '%s'"
                                 % (mc.group(1), cur))
            out[cur] = buf
            cur = None
        elif cur is not None:
            buf.append(ln)
    if cur is not None:
        raise ValueError("vung '%s' khong duoc dong" % cur)
    return out
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest blockdiff_test.py -q
```

Kỳ vọng: `5 passed`.

- [ ] **Step 5: Viết test cho so sánh + ngoại lệ**

Thêm vào cuối `<SP>/blockdiff_test.py`:

```python
# ------------------------------------------------------------ so sanh
def test_hai_ban_giong_het_thi_khong_co_diff():
    assert compare(["a", "b"], ["a", "b"]) == []


def test_mot_dong_khac_thi_ra_mot_cap():
    assert compare(["a", "b"], ["a", "X"]) == [Diff("b", "X")]


def test_them_dong_la_troi_khong_ghep_cap_duoc():
    """Them/bot dong KHONG bao gio duoc coi la ngoai le hop le."""
    d = compare(["a"], ["a", "b"])
    assert d == [Diff(None, "b")]


def test_bot_dong_la_troi():
    assert compare(["a", "b"], ["a"]) == [Diff("b", None)]


# ------------------------------------------------------------ ngoai le
EXC = [
    "# ghi chu bi bo qua",
    "TIN HIEU\tmot.pine\thai.pine",
    "-if x and not posOpen",
    "+if x and strategy.position_size == 0",
    "",
    "KHAC\ta.pine\tb.pine",
    "-p",
    "+q",
]


def test_doc_file_ngoai_le(tmp_path):
    f = w(tmp_path, "exc.txt", EXC)
    e = load_exceptions(f)
    assert e[("TIN HIEU", "mot.pine", "hai.pine")] == [
        Diff("if x and not posOpen", "if x and strategy.position_size == 0")
    ]
    assert e[("KHAC", "a.pine", "b.pine")] == [Diff("p", "q")]


def test_file_ngoai_le_khong_ton_tai_thi_rong(tmp_path):
    assert load_exceptions(str(tmp_path / "khong-co.txt")) == {}


def test_dong_thieu_dau_cong_tru_thi_bao_loi(tmp_path):
    f = w(tmp_path, "exc.txt", ["A\ta.pine\tb.pine", "khong co dau"])
    with pytest.raises(ValueError):
        load_exceptions(f)
```

- [ ] **Step 6: Chạy test, xác nhận đỏ**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest blockdiff_test.py -q
```

Kỳ vọng: FAIL, `ImportError: cannot import name 'compare'`.

- [ ] **Step 7: Viết `Diff`, `compare`, `load_exceptions`**

Thêm vào `<SP>/blockdiff.py`, ngay sau phần `import`, trước `find_regions`:

```python
class Diff(object):
    """Mot cho lech. old=None nghia la dong duoc THEM; new=None la BI BOT."""

    __slots__ = ("old", "new")

    def __init__(self, old, new):
        self.old = old
        self.new = new

    def __eq__(self, o):
        return isinstance(o, Diff) and self.old == o.old and self.new == o.new

    def __hash__(self):
        return hash((self.old, self.new))

    def __repr__(self):
        return "Diff(%r, %r)" % (self.old, self.new)
```

Và sau `find_regions`:

```python
def compare(a, b):
    """Tra ve danh sach Diff giua hai ban chep cua cung mot vung."""
    out = []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        old = a[i1:i2]
        new = b[j1:j2]
        for k in range(max(len(old), len(new))):
            out.append(Diff(old[k] if k < len(old) else None,
                            new[k] if k < len(new) else None))
    return out


def load_exceptions(path):
    """Doc blockdiff_except.txt -> {(vung, file_a, file_b): [Diff, ...]}."""
    if not os.path.exists(path):
        return {}
    out = {}
    key = None
    pend = None
    for raw in io.open(path, encoding="utf-8").read().split("\n"):
        ln = raw.rstrip("\r")
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if "\t" in ln:
            if pend is not None:
                raise ValueError("cap - / + do dang truoc '%s'" % ln)
            parts = ln.split("\t")
            if len(parts) != 3:
                raise ValueError("dong tieu de phai co dung 3 cot: '%s'" % ln)
            key = (parts[0], parts[1], parts[2])
            out.setdefault(key, [])
        elif ln.startswith("-"):
            if key is None:
                raise ValueError("dong '-' truoc khi co tieu de")
            if pend is not None:
                raise ValueError("hai dong '-' lien tiep")
            pend = ln[1:]
        elif ln.startswith("+"):
            if pend is None:
                raise ValueError("dong '+' khong co dong '-' di truoc")
            out[key].append(Diff(pend, ln[1:]))
            pend = None
        else:
            raise ValueError("dong khong bat dau bang - hoac +: '%s'" % ln)
    if pend is not None:
        raise ValueError("dong '-' cuoi file khong co '+' theo sau")
    return out
```

- [ ] **Step 8: Chạy test, xác nhận xanh**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest blockdiff_test.py -q
```

Kỳ vọng: `12 passed`.

- [ ] **Step 9: Mutation — chứng minh test không rỗng**

Đổi trong `compare` dòng `out.append(Diff(...))` thành `pass` (tức không bao giờ báo lệch). Chạy lại test. Kỳ vọng: **ít nhất 3 test đỏ**. Nếu tất cả vẫn xanh thì test rỗng — dừng và báo.

Hoàn nguyên thay đổi, chạy lại, xác nhận `12 passed`.

Lặp với mutation thứ hai: trong `load_exceptions`, bỏ nhánh `raise ValueError("dong khong bat dau bang - hoac +...")` thành `continue`. Kỳ vọng: 1 test đỏ (`test_dong_thieu_dau_cong_tru_thi_bao_loi`). Hoàn nguyên.

- [ ] **Step 10: Viết `main` — quét thư mục**

Thêm vào cuối `<SP>/blockdiff.py`:

```python
def scan(pine_dir, exc_path):
    """Tra ve (danh sach dong bao cao, so cho troi ngoai ngoai le)."""
    exc = load_exceptions(exc_path)
    files = sorted(f for f in os.listdir(pine_dir) if f.endswith(".pine"))
    by_region = {}
    for f in files:
        lines = io.open(os.path.join(pine_dir, f), encoding="utf-8").read().split("\n")
        try:
            regions = find_regions(lines)
        except ValueError as e:
            return (["LOI  %s: %s" % (f, e)], 1)
        for name, body in regions.items():
            by_region.setdefault(name, []).append((f, body))

    report = []
    bad = 0
    for name in sorted(by_region):
        group = by_region[name]
        if len(group) == 1:
            report.append("MOT MINH   %-16s %s (%d dong)"
                          % (name, group[0][0], len(group[0][1])))
            continue
        base_f, base_b = group[0]
        for f, body in group[1:]:
            d = compare(base_b, body)
            allowed = exc.get((name, base_f, f), [])
            if not d:
                report.append("GIONG HET  %-16s %s = %s (%d dong)"
                              % (name, base_f, f, len(base_b)))
            elif d == allowed:
                report.append("LECH CO PHEP %-14s %s = %s (%d cho, da ghi)"
                              % (name, base_f, f, len(d)))
            else:
                bad += 1
                report.append("TROI       %-16s %s vs %s" % (name, base_f, f))
                for x in d:
                    if x not in allowed:
                        report.append("    - %s" % x.old)
                        report.append("    + %s" % x.new)
    return (report, bad)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    rep, bad = scan("pine", os.path.join(here, "blockdiff_except.txt"))
    print("\n".join(rep))
    print("---")
    print("SACH" if bad == 0 else "CO %d CHO TROI" % bad)
    sys.exit(1 if bad else 0)
```

- [ ] **Step 11: Thêm mốc `BOI CANH HTF` vào cặp `kill_peak`**

Trong `pine/kill_peak_indicator.pine`: chèn dòng `// ---- KHOI BOI CANH HTF ----` ngay **trước** dòng `var bool   measHi      = false`, và dòng `// ---- HET KHOI BOI CANH HTF ----` ngay **sau** dòng cuối của bước 6 (`        runHigh := seedHigh`).

Làm y hệt trong `pine/kill_peak_strategy.pine` — tìm cùng hai mốc neo đó.

**Chỉ thêm dòng comment. Không sửa một ký tự code nào.**

- [ ] **Step 12: Chạy blockdiff, đối chiếu vùng HTF giữa hai file kill_peak**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && python "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad/blockdiff.py"
```

Kỳ vọng: dòng `GIONG HET  BOI CANH HTF ...` cho cặp kill_peak, và dòng `TROI  TIN HIEU ...` (chưa có ngoại lệ — đúng, sẽ xử ở bước sau).

**Nếu `BOI CANH HTF` báo TROI: DỪNG và báo cáo.** Đó là trôi có thật giữa hai file đã commit, không được lấp bằng ngoại lệ.

- [ ] **Step 13: Ghi ngoại lệ cho vùng `TIN HIEU` của kill_peak**

Lấy đúng hai cặp dòng mà bước 12 in ra, viết vào `<SP>/blockdiff_except.txt`:

```
# Nhung cho CO Y lech nhau giua hai ban chep. Ghi dich danh ca hai dong.
# Dinh dang:  <ten vung> TAB <file goc> TAB <file so>
#             -<dong trong file goc>
#             +<dong trong file so>
#
# kill_peak: khoi tin hieu duoc phep lech DUNG hai dong gate vi the.
# Da ghi trong header ca hai file. Bat cu cho lech thu ba nao la troi that.
```

Rồi nối tiếp dòng tiêu đề `TIN HIEU<TAB>kill_peak_indicator.pine<TAB>kill_peak_strategy.pine` và bốn dòng `-`/`+` copy **nguyên văn** từ output bước 12 (bỏ 4 dấu cách thụt đầu và giữ dấu `-`/`+`).

- [ ] **Step 14: Chạy lại, xác nhận `TIN HIEU` thành `LECH CO PHEP`**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && python "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad/blockdiff.py"; echo "rc=$?"
```

Kỳ vọng: `LECH CO PHEP TIN HIEU ...` và `rc=0`.

- [ ] **Step 15: Chứng minh ngoại lệ không phải tấm khiên vạn năng**

Sửa tạm một dòng bất kì trong vùng `TIN HIEU` của `pine/kill_peak_strategy.pine` (ví dụ đổi một comment). Chạy lại blockdiff.

Kỳ vọng: `TROI  TIN HIEU` và `rc=1` — ngoại lệ đã ghi không che được cho cho lệch thứ ba.

Hoàn nguyên sửa đổi. Chạy lại, xác nhận `rc=0`.

- [ ] **Step 16: Tách vùng M1 của `rsi_failure_swing` thành ba mảnh**

Trong `pine/rsi_failure_swing_indicator.pine`:

**Xoá ba mốc cũ trước:** `// ---- KHOI TRANG THAI BUY ----`,
`// ---- KHOI TRANG THAI SELL (guong) ----`, `// ---- HET KHOI TRANG THAI ----`.
Phải xoá, không giữ: `HET KHOI TRANG THAI` không có mốc mở cùng tên nên
`find_regions` sẽ ném `ValueError`.

**Rồi chèn sáu mốc mới, theo đúng dòng neo sau:**

| Mốc | Vị trí |
|---|---|
| `// ---- KHOI M1-A ----` | ngay **trước** `// ---------------------------------------------------------------- series` |
| `// ---- HET KHOI M1-A ----` | ngay **sau** `        bEnd   := "VO HIEU: chan 2 pha RSI chan 1"` (cuối bước 2b BUY) |
| `// ---- KHOI M1-B ----` | ngay **trước** `// 4. gia pha chan 1` |
| `// ---- HET KHOI M1-B ----` | ngay **sau** `        sEnd   := "VO HIEU: chan 2 pha RSI chan 1"` (cuối bước 2b SELL) |
| `// ---- KHOI M1-C ----` | ngay **trước** `if sSt == 2 and high > sP1` (bước 4 SELL — tức **sau** khối bước 3 SELL) |
| `// ---- HET KHOI M1-C ----` | sau dòng cuối của bước 6 SELL, `    sR2Bar  := bar_index` |

Thứ tự cuối cùng trong file:

```
// ---- KHOI M1-A ----
// ------- series (giu nguyen tieu de cu)
...  series + khai bao state + BUY buoc 1, 2, 2b
// ---- HET KHOI M1-A ----

// 3. tin hieu — PHAI dung truoc buoc 4, xem header
...  BUY buoc 3 (rieng cua file nay)

// ---- KHOI M1-B ----
// 4. gia pha chan 1
...  BUY buoc 4, 5, 6 + SELL buoc 1, 2, 2b
// ---- HET KHOI M1-B ----

...  SELL buoc 3 (rieng cua file nay)

// ---- KHOI M1-C ----
...  SELL buoc 4, 5, 6
// ---- HET KHOI M1-C ----
```

Ba mốc cũ (`KHOI TRANG THAI BUY`, `KHOI TRANG THAI SELL (guong)`, `HET KHOI TRANG THAI`) **xoá hết**.

- [ ] **Step 17: Làm y hệt cho `pine/rsi_failure_swing_strategy.pine`**

Cùng bảy mốc, cùng vị trí neo. File strategy có nội dung khối giống hệt indicator nên các dòng neo tồn tại y nguyên.

- [ ] **Step 18: Kiểm — hai file rfs vẫn sạch và ba vùng khớp nhau**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && SP="C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && python "$SP/kp_check.py" pine/rsi_failure_swing_indicator.pine && python "$SP/kp_check.py" pine/rsi_failure_swing_strategy.pine && python "$SP/blockdiff.py"; echo "rc=$?"
```

Kỳ vọng: hai dòng `SACH`, rồi `GIONG HET` cho cả `M1-A`, `M1-B`, `M1-C`, và `rc=0`.

**Nếu một trong ba vùng M1 báo TROI: DỪNG và báo cáo** — nghĩa là hai file rfs đã lệch nhau từ trước mà `rfs_blockdiff.py` cũ không thấy.

- [ ] **Step 19: Xoá công cụ cũ**

```bash
rm "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad/rfs_blockdiff.py"
```

Sửa header của `pine/rsi_failure_swing_strategy.pine`: dòng nhắc `rfs_blockdiff.py lam viec nay` đổi thành `blockdiff.py quet toan bo pine/ lam viec nay`.

- [ ] **Step 20: Chạy lại toàn bộ test cũ, chứng minh không phá gì**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest rfs_test.py blockdiff_test.py -q
```

Kỳ vọng: `32 passed` (20 cũ + 12 mới).

- [ ] **Step 21: Commit**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && git add pine/ && git commit -F "<SP>/msg1.txt"
```

Nội dung `msg1.txt` (viết bằng công cụ Write, tiếng Việt không dấu):
tiêu đề `chore(pine): chuan hoa moc khoi chep de blockdiff quet duoc`;
thân bài nói rõ: chỉ sửa comment, không đổi một ký tự code; vùng M1 tách ba mảnh vì thân bước 3 sẽ khác nhau giữa rsi_failure_swing và kill_peak_fs; vùng TIN HIEU của kill_peak có ngoại lệ ghi đích danh hai dòng gate vị thế; đã chứng minh ngoại lệ không che được cho lệch thứ ba; kp_check SACH cả bốn file, 32 test xanh.

---

## Task 2: Oracle — máy bối cảnh HTF

**Files:**
- Create: `<SP>/kpfs_oracle.py`
- Create: `<SP>/kpfs_test.py`

**Interfaces:**
- Consumes: không gì từ task trước (độc lập với Task 1).
- Produces:
  - `Ctx` — dataclass giữ state HTF: `meas_hi, run_high, kill_high, kill_high_bar, flag_buy, flag_buy_bar, flag_buy_used` và bộ đối xứng `meas_lo, run_low, kill_low, kill_low_bar, flag_sell, flag_sell_bar, flag_sell_used`.
  - `CP` — dataclass tham số: `ctx_hi=70.0, ctx_mid=50.0, ctx_lo=30.0`.
  - `step_ctx(c, bars, i, ctx_rsi, cp, ev) -> None` — chạy đúng sáu bước §3.4 của spec cho nến `i`. `ctx_rsi` là danh sách float cùng độ dài `bars`. `ev` là list nhận `(i, tag)` với tag thuộc `{"FLAG_BUY", "FLAG_SELL", "KILL_BUY", "KILL_SELL", "RSIOUT_BUY", "RSIOUT_SELL", "NEW_BUY", "NEW_SELL"}`.
- Task 3 dùng lại `Ctx`, `CP`, `step_ctx` y nguyên.

Máy HTF nhận thẳng chuỗi `ctx_rsi` làm đầu vào — **không** mô phỏng `request.security`. Ánh xạ M3→M1 nằm ngoài phạm vi oracle (spec §13.2).

- [ ] **Step 1: Viết test đầu tiên — cờ BUY bật đúng nến, killHigh đúng giá trị**

Tạo `<SP>/kpfs_test.py`:

```python
"""Test cho kpfs_oracle — boi canh M3 ghep may failure swing M1."""
from rfs_oracle import Bar
from kpfs_oracle import Ctx, CP, step_ctx


def mk(rows):
    """(high, low, close, rsi_m1) -> Bar. atr co dinh 1.0 cho de tinh tay."""
    return [Bar(h, l, c, r, 1.0) for h, l, c, r in rows]


def run_ctx(rows, ctx_rsi, cp=None):
    cp = cp or CP()
    bars = mk(rows)
    c = Ctx()
    ev = []
    for i in range(len(bars)):
        step_ctx(c, bars, i, ctx_rsi, cp, ev)
    return c, ev


# ctx_rsi: 65 -> 75 cat len 70 (mo doan do) -> 60 -> 45 cat xuong 50 (chot)
CTX_BUY = [65, 75, 72, 60, 45]
ROWS_BUY = [
    (100,  98,  99),
    (104, 100, 103),   # 1 mo doan do, runHigh moi = seedHigh (bo qua, dung high)
    (110, 105, 108),   # 2 dinh cao nhat doan do = 110
    (107, 102, 103),   # 3
    (104,  99, 100),   # 4 cat xuong 50 -> chot killHigh = 110, bat co
]


def test_co_buy_bat_dung_nen_va_killhigh_dung():
    c, ev = run_ctx(ROWS_BUY, CTX_BUY)
    assert c.flag_buy is True
    assert c.flag_buy_bar == 4
    assert c.kill_high == 110.0
    assert c.meas_hi is False
    assert (4, "FLAG_BUY") in ev
```

Lưu ý về nến 1: Pine mồi `runHigh := seedHigh` với `seedHigh = ta.highest(high, n)`. Oracle không có khái niệm `n` (ánh xạ M3→M1 ngoài phạm vi), nên **oracle mồi bằng `high` của chính nến mở đoạn đo**. Ghi chú này phải nằm trong docstring của `step_ctx`. Hệ quả: với dữ liệu test ở trên, `seedHigh` của Pine có thể lớn hơn `high[1]`; đó là khác biệt **đã biết và chấp nhận** giữa oracle và Pine, chỉ ảnh hưởng vài nến đầu đoạn đo.

- [ ] **Step 2: Chạy test, xác nhận đỏ**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest kpfs_test.py -q
```

Kỳ vọng: FAIL, `ModuleNotFoundError: No module named 'kpfs_oracle'`.

- [ ] **Step 3: Viết `Ctx`, `CP`, `step_ctx`**

Tạo `<SP>/kpfs_oracle.py`:

```python
"""Oracle cho kill_peak_fs: boi canh M3 + may failure swing M1 + khoi noi.

May M1 KHONG viet lai — goi thang rfs_oracle.step_side, von da co 20 test
xanh. Khoi noi boc ngoai: step_side luon dat st = IDLE du co tin hieu hay
khong, nen gate truot thi chi can VUT sig di, trang thai van khop Pine.

May HTF nhan thang chuoi ctx_rsi. Khong mo phong request.security: anh xa
M3 -> M1 nam ngoai pham vi oracle.
"""
from dataclasses import dataclass, field

NAN = float("nan")


@dataclass
class CP:
    ctx_hi: float = 70.0
    ctx_mid: float = 50.0
    ctx_lo: float = 30.0


@dataclass
class Ctx:
    meas_hi: bool = False
    run_high: float = NAN
    kill_high: float = NAN
    kill_high_bar: int = -1
    flag_buy: bool = False
    flag_buy_bar: int = -1
    flag_buy_used: bool = False

    meas_lo: bool = False
    run_low: float = NAN
    kill_low: float = NAN
    kill_low_bar: int = -1
    flag_sell: bool = False
    flag_sell_bar: int = -1
    flag_sell_used: bool = False


def step_ctx(c, bars, i, ctx_rsi, cp, ev):
    """Sau buoc cua tang M3, dung thu tu spec §3.4. Thu tu LA thu chan.

    Khac Pine mot cho da biet: Pine moi run_high bang ta.highest(high, n)
    voi n = so nen chart trong mot nen HTF; oracle moi bang high cua chinh
    nen mo doan do, vi khong co khai niem n. Chi lech vai nen dau doan do.
    """
    b = bars[i]
    cur = ctx_rsi[i]
    prev = ctx_rsi[i - 1] if i > 0 else None
    ok = prev is not None and cur == cur and prev == prev

    c_up_hi = ok and prev <= cp.ctx_hi < cur
    c_dn_mid = ok and prev >= cp.ctx_mid > cur
    c_up_mid = ok and prev <= cp.ctx_mid < cur
    c_dn_lo = ok and prev >= cp.ctx_lo > cur

    # 1. noi cuc tri
    if c.meas_hi:
        c.run_high = b.high if c.run_high != c.run_high else max(c.run_high, b.high)
    if c.meas_lo:
        c.run_low = b.low if c.run_low != c.run_low else min(c.run_low, b.low)

    # 2. cham muc — PHAI truoc buoc 3: neu trong cung nen gia da cham muc
    #    thi khong con gi de giao dich, co chet truoc khi tang M1 kip dung.
    if c.flag_buy and b.high >= c.kill_high:
        c.flag_buy = False
        ev.append((i, "KILL_BUY"))
    if c.flag_sell and b.low <= c.kill_low:
        c.flag_sell = False
        ev.append((i, "KILL_SELL"))

    # 3. chot dinh cho kill
    if c_dn_mid and c.meas_hi:
        c.kill_high, c.kill_high_bar = c.run_high, i
        c.meas_hi = False
        c.flag_buy, c.flag_buy_bar, c.flag_buy_used = True, i, False
        ev.append((i, "FLAG_BUY"))

    # 4. chot day cho kill
    if c_up_mid and c.meas_lo:
        c.kill_low, c.kill_low_bar = c.run_low, i
        c.meas_lo = False
        c.flag_sell, c.flag_sell_bar, c.flag_sell_used = True, i, False
        ev.append((i, "FLAG_SELL"))

    # 5. cat xuong ctx_lo
    if c_dn_lo:
        if c.flag_buy:
            c.flag_buy = False
            ev.append((i, "RSIOUT_BUY"))
        if c.flag_sell:
            c.flag_sell = False
            ev.append((i, "NEW_SELL"))
        if not c.meas_lo:
            c.meas_lo = True
            c.run_low = b.low

    # 6. cat len ctx_hi
    if c_up_hi:
        if c.flag_sell:
            c.flag_sell = False
            ev.append((i, "RSIOUT_SELL"))
        if c.flag_buy:
            c.flag_buy = False
            ev.append((i, "NEW_BUY"))
        if not c.meas_hi:
            c.meas_hi = True
            c.run_high = b.high
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest kpfs_test.py -q
```

Kỳ vọng: `1 passed`.

- [ ] **Step 5: Viết các test còn lại của tầng HTF**

Thêm vào `<SP>/kpfs_test.py`:

```python
def test_co_chet_vi_KILL_khi_gia_cham_muc():
    rows = ROWS_BUY + [(111, 105, 110)]      # 5 high 111 >= killHigh 110
    ctx = CTX_BUY + [46]
    c, ev = run_ctx(rows, ctx)
    assert c.flag_buy is False
    assert (5, "KILL_BUY") in ev


def test_co_chet_vi_RSIOUT_khi_ctx_cat_xuong_30():
    rows = ROWS_BUY + [(103, 98, 99)]
    ctx = CTX_BUY + [25]                      # cat xuong 30
    c, ev = run_ctx(rows, ctx)
    assert c.flag_buy is False
    assert (5, "RSIOUT_BUY") in ev
    assert c.meas_lo is True                  # mo doan do day


def test_co_chet_vi_NEWLEVEL_khi_ctx_cat_len_70():
    rows = ROWS_BUY + [(112, 106, 111)]
    ctx = CTX_BUY + [75]                      # cat len 70 lan nua
    c, ev = run_ctx(rows, ctx)
    assert c.flag_buy is False
    assert (5, "NEW_BUY") in ev
    assert c.meas_hi is True


def test_cham_muc_xu_truoc_chot_muc_trong_cung_nen():
    """Neu nen chot co cung la nen gia vuot dinh cu, co CU chet truoc.

    Buoc 2 chay truoc buoc 3 nen killHigh cu bi kiem, roi killHigh moi
    duoc dat. Dao hai buoc la doi hanh vi.
    """
    rows = ROWS_BUY + [
        (120, 100, 118),   # 5 ctx cat len 70 -> co cu chet NEWLEVEL, mo do moi
        (125, 118, 124),   # 6 dinh doan do moi = 125
        (121, 115, 116),   # 7 ctx cat xuong 50 -> chot 125, bat co moi
    ]
    ctx = CTX_BUY + [75, 72, 45]
    c, ev = run_ctx(rows, ctx)
    assert (5, "NEW_BUY") in ev
    assert c.kill_high == 125.0
    assert c.flag_buy_bar == 7


def test_hai_co_khong_bao_gio_cung_bat():
    """Bat bien spec §3.5, quet tren mot chuoi ctx_rsi day du hai chieu."""
    ctx = [65, 75, 60, 45, 40, 25, 35, 55, 65, 75, 60, 45]
    rows = [(100 + i, 90 + i, 95 + i) for i in range(len(ctx))]
    bars = mk(rows)
    c = Ctx()
    ev = []
    for i in range(len(bars)):
        step_ctx(c, bars, i, ctx, CP(), ev)
        assert not (c.flag_buy and c.flag_sell), "hai co cung bat o nen %d" % i


def test_chieu_sell_guong():
    # ctx: 35 -> 25 cat xuong 30 (mo do day) -> 40 -> 55 cat len 50 (chot)
    ctx = [35, 25, 28, 40, 55]
    rows = [
        (100,  98,  99),
        (99,   92,  93),   # 1 mo doan do day
        (95,   88,  90),   # 2 day thap nhat = 88
        (97,   91,  96),   # 3
        (101,  95, 100),   # 4 cat len 50 -> chot killLow = 88, bat co SELL
    ]
    c, ev = run_ctx(rows, ctx)
    assert c.flag_sell is True
    assert c.kill_low == 88.0
    assert c.flag_sell_bar == 4
    assert (4, "FLAG_SELL") in ev
```

- [ ] **Step 6: Chạy test, xác nhận xanh**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest kpfs_test.py -q
```

Kỳ vọng: `7 passed`. Nếu có test đỏ, đọc kỹ: **có thể test sai chứ không phải code sai** — ở dự án trước đã có hai lần như vậy. Xác định bên nào đúng theo spec §3.4 rồi sửa bên sai, và ghi lý do vào comment.

- [ ] **Step 7: Mutation testing tầng HTF**

Chạy từng mutation sau trên `kpfs_oracle.py`, mỗi lần: sửa → `rm -rf __pycache__` → `python -m pytest kpfs_test.py -q` → ghi số test đỏ → hoàn nguyên.

| # | Mutation | Kỳ vọng |
|---|---|---|
| 1 | Đảo bước 2 xuống **sau** bước 3 | ≥1 đỏ (`test_cham_muc_xu_truoc_chot_muc...`) |
| 2 | Bỏ `c.flag_sell = False` ở bước 5 | ≥1 đỏ (`test_hai_co_khong_bao_gio_cung_bat`) |
| 3 | Bỏ `c.flag_buy = False` ở bước 6 | ≥1 đỏ (`test_hai_co_khong_bao_gio_cung_bat`) |
| 4 | `b.high >= c.kill_high` → `b.high > c.kill_high` | ≥1 đỏ (`test_co_chet_vi_KILL...` — dữ liệu có high 111 > 110 nên **sẽ không đỏ**; nếu vậy thêm một test biên `high == killHigh` rồi chạy lại) |
| 5 | Bước 3 đặt `c.kill_high = b.high` thay vì `c.run_high` | ≥1 đỏ |

Mutation #4 có khả năng sống sót — nếu nó sống, **phải thêm test biên** `high` đúng bằng `kill_high` rồi chạy lại cho tới khi nó chết. Đó là điểm của mutation testing.

- [ ] **Step 8: Commit**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && git commit --allow-empty -F "<SP>/msg2.txt"
```

File oracle nằm trong scratchpad nên **không có gì để `git add`**. Commit rỗng ghi lại mốc kiểm chứng: tiêu đề `test(oracle): kpfs - may boi canh HTF, 7 test xanh`; thân bài liệt kê 5 mutation và số test đỏ của mỗi cái, cộng khác biệt đã biết về cách mồi `run_high`.

Nếu người thi công thấy commit rỗng là vô nghĩa thì bỏ qua bước này và gộp ghi chú vào commit của Task 4.

---

## Task 3: Oracle — khối nối

**Files:**
- Modify: `<SP>/kpfs_oracle.py`
- Modify: `<SP>/kpfs_test.py`

**Interfaces:**
- Consumes: `Ctx`, `CP`, `step_ctx` từ Task 2; `Bar`, `P`, `Side`, `step_side` từ `rfs_oracle` (không sửa).
- Produces:
  - `JP` — dataclass tham số khối nối: `require_leg2_after_flag=True, one_trade_per_flag=True, min_rr=1.0, max_rr=0.0`.
  - `run_kpfs(bars, ctx_rsi, p=None, cp=None, jp=None) -> dict` với khoá `"signals"` (list dict có `side, bar, entry, sl, tp, rr`), `"rej_rr"` (list `(bar, side, rr)`), `"ctx"`, `"buy"`, `"sell"`, `"ev_buy"`, `"ev_sell"`, `"ev_ctx"`.

### Cách bọc, và vì sao nó tương đương Pine

`step_side` trả về `sig` hoặc `None`, và **luôn** đặt `st = IDLE` khi ở BROKEN gặp `x_mid`, bất kể có tín hiệu hay không. Nên:

- `sig is None` → không có gì làm
- có `sig` nhưng gate trượt → **vứt `sig` đi**; `st` đã về IDLE nên trạng thái khớp Pine
- gate qua → thay `sig["tp"]` bằng `kill_high`, tính `rr`, áp `min_rr`/`max_rr`, đặt `flag_used`

Ở Pine, khi `gate` sai thì `e`/`s` không được tính và `bSig` không bao giờ bật. Ở oracle chúng được tính rồi vứt. **Quan sát từ ngoài y hệt nhau**, mà `rfs_oracle.py` không phải động một dòng.

`min_sl_dist = minSlTicks * mintick` truyền qua `P` — tham số đó đã có sẵn từ commit `46aaaec`.

- [ ] **Step 1: Viết test — setup M1 đủ + cờ bật → ra lệnh, TP đúng bằng killHigh**

Thêm vào `<SP>/kpfs_test.py`:

```python
from rfs_oracle import P
from kpfs_oracle import JP, run_kpfs


# Ghep: 5 nen dung boi canh (co BUY bat o nen 4, killHigh = 110),
# roi 8 nen chay tron mot setup failure swing M1.
# ctx_rsi giu nguyen 45 tu nen 4 tro di: khong cat 30, khong cat 70,
# nen co song suot doan M1.
ROWS_FULL = ROWS_BUY + [
    (99,   95,  96),   # 5  rsi m1 25: cat xuong 30 -> SEEKING, L1 = 95
    (97,   90,  92),   # 6  rsi m1 20: L1 = 90, R1 = 20
    (99,   93,  98),   # 7  rsi m1 40
    (104, 100, 103),   # 8  rsi m1 55: cat len 50 -> ARMED
    (103,  96,  97),   # 9  rsi m1 45
    (99,   88,  90),   # 10 rsi m1 35: thung L1 = 90 -> BROKEN, L2 = 88
    (95,   89,  94),   # 11 rsi m1 48
    (99,   93,  98),   # 12 rsi m1 58: cat len 50 lan nua -> TIN HIEU
]
CTX_FULL = CTX_BUY + [45, 45, 45, 45, 45, 45, 45, 45]
RSI_M1 = [55, 55, 55, 55, 55, 25, 20, 40, 55, 45, 35, 48, 58]


def bars_full():
    return [Bar(h, l, c, r, 1.0)
            for (h, l, c), r in zip(ROWS_FULL, RSI_M1)]


def test_setup_du_va_co_bat_thi_ra_lenh_tp_bang_killhigh():
    out = run_kpfs(bars_full(), CTX_FULL)
    assert len(out["signals"]) == 1
    s = out["signals"][0]
    assert s["side"] == "BUY"
    assert s["bar"] == 12
    assert s["entry"] == 98.0
    assert s["sl"] == 87.5              # L2 88 - 0.5 * atr 1.0
    assert s["tp"] == 110.0             # = killHigh, KHONG phai boi so R
    assert abs(s["rr"] - (110.0 - 98.0) / (98.0 - 87.5)) < 1e-9
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest kpfs_test.py -q
```

Kỳ vọng: FAIL, `ImportError: cannot import name 'JP'`.

- [ ] **Step 3: Viết `JP` và `run_kpfs`**

Thêm vào `<SP>/kpfs_oracle.py`:

```python
from rfs_oracle import P, Side, step_side


@dataclass
class JP:
    """Tham so khoi noi — phan viet moi cua kill_peak_fs."""
    require_leg2_after_flag: bool = True
    one_trade_per_flag: bool = True
    min_rr: float = 1.0
    max_rr: float = 0.0          # 0 = khong chan


def _join(sig, c, jp, sgn, i):
    """Ap gate + RR len mot sig tho tu step_side.

    Tra ve (sig_da_sua, ly_do_loai). ly_do_loai la None khi qua, hoac
    "GATE" / "RR" / "LEVEL".
    """
    if sgn > 0:
        flag, lvl, used = c.flag_buy, c.kill_high, c.flag_buy_used
        flag_bar = c.flag_buy_bar
    else:
        flag, lvl, used = c.flag_sell, c.kill_low, c.flag_sell_used
        flag_bar = c.flag_sell_bar

    if not flag or lvl != lvl:
        return (None, "GATE")
    if jp.require_leg2_after_flag and sig["p2_bar"] < flag_bar:
        return (None, "GATE")
    if jp.one_trade_per_flag and used:
        return (None, "GATE")

    entry, sl = sig["entry"], sig["sl"]
    reward = (lvl - entry) if sgn > 0 else (entry - lvl)
    risk = (entry - sl) if sgn > 0 else (sl - entry)
    if reward <= 0:
        return (None, "LEVEL")

    rr = reward / risk
    if rr < jp.min_rr or (jp.max_rr > 0 and rr > jp.max_rr):
        sig["rr"] = rr
        return (None, "RR")

    sig["tp"] = lvl
    sig["rr"] = rr
    if sgn > 0:
        c.flag_buy_used = True
    else:
        c.flag_sell_used = True
    return (sig, None)


def run_kpfs(bars, ctx_rsi, p=None, cp=None, jp=None):
    p = p or P()
    cp = cp or CP()
    jp = jp or JP()
    c = Ctx()
    buy, sell = Side(), Side()
    ev_b, ev_s, ev_c = [], [], []
    sigs, rej = [], []

    for i in range(len(bars)):
        # Tang M3 PHAI chay truoc tang M1: khoi noi doc flag/kill cua NEN NAY.
        step_ctx(c, bars, i, ctx_rsi, cp, ev_c)

        for sgn, side, ev in ((+1, buy, ev_b), (-1, sell, ev_s)):
            if sgn > 0 and not p.enable_buy:
                continue
            if sgn < 0 and not p.enable_sell:
                continue
            g = step_side(side, bars, i, p, sgn, ev)
            if g is None:
                continue
            g["p2_bar"] = side.p2_bar if side.p2_bar >= 0 else g.get("p2_bar", -1)
            out, why = _join(g, c, jp, sgn, i)
            if out is not None:
                sigs.append(out)
            elif why == "RR":
                rej.append((i, g["side"], g["rr"]))

    return {"signals": sigs, "rej_rr": rej, "ctx": c,
            "buy": buy, "sell": sell,
            "ev_buy": ev_b, "ev_sell": ev_s, "ev_ctx": ev_c}
```

**Cảnh báo cho người thi công:** `step_side` đặt `st = IDLE` **trước khi** trả về, và nó reset `p2_bar` chưa? Kiểm tra `rfs_oracle.py` bằng mắt trước khi viết dòng `g["p2_bar"] = ...`. Nếu `sig` trả về đã chứa `p2` nhưng **không** chứa `p2_bar`, thì phải đọc `side.p2_bar` **trước** khi gọi `step_side` — vì bước 5/6 trong cùng lần gọi đó có thể ghi đè. Nếu thấy như vậy: **DỪNG và báo**, đừng đoán. Cách sửa đúng là chụp `p2_bar` trước lệnh gọi:

```python
        p2_bar_truoc = side.p2_bar
        g = step_side(side, bars, i, p, sgn, ev)
        if g is not None:
            g["p2_bar"] = p2_bar_truoc
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest kpfs_test.py -q
```

Kỳ vọng: `8 passed`.

- [ ] **Step 5: Viết phần test còn lại của khối nối**

Thêm vào `<SP>/kpfs_test.py`. Đây là các mục 6–14 của spec §13.2:

```python
def test_setup_du_nhung_khong_co_co_thi_khong_lenh_ma_van_tieu_setup():
    """Spec §13.2 muc 6. ctx_rsi phang: khong bao gio bat co."""
    ctx = [55] * len(ROWS_FULL)
    out = run_kpfs(bars_full(), ctx)
    assert out["signals"] == []
    assert out["buy"].st == "IDLE"          # setup van bi tieu


def test_chan_2_truoc_co_thi_bi_chan():
    """Spec §13.2 muc 7, nua dau.

    Day co bat o nen 12 — sau khi chan 2 (nen 10) da hinh thanh — nen
    requireLeg2AfterFlag phai chan.
    """
    ctx = [65, 75, 72, 60, 55, 55, 55, 55, 55, 55, 55, 55, 45]
    out = run_kpfs(bars_full(), ctx)
    assert out["signals"] == []


def test_chan_2_sau_co_thi_qua():
    """Spec §13.2 muc 7, nua sau — chinh la kich ban ROWS_FULL."""
    out = run_kpfs(bars_full(), CTX_FULL)
    assert len(out["signals"]) == 1


def test_tat_require_leg2_thi_chan_2_truoc_co_van_qua():
    ctx = [65, 75, 72, 60, 55, 55, 55, 55, 55, 55, 55, 55, 45]
    out = run_kpfs(bars_full(), ctx, jp=JP(require_leg2_after_flag=False))
    assert len(out["signals"]) == 1


def test_co_bat_cung_nen_xac_nhan_thi_bi_chan():
    """Spec §13.2 muc 8 va §5.5: flagBuyBar == bar_index, bP2Bar < do."""
    ctx = [65, 75, 72, 60, 55, 55, 55, 55, 55, 55, 55, 55, 45]
    out = run_kpfs(bars_full(), ctx)
    assert out["ctx"].flag_buy_bar == 12
    assert out["signals"] == []


def test_loai_vi_min_rr():
    """Spec §13.2 muc 10. RR that = 12 / 10.5 = 1.14; dat nguong 2.0."""
    out = run_kpfs(bars_full(), CTX_FULL, jp=JP(min_rr=2.0))
    assert out["signals"] == []
    assert len(out["rej_rr"]) == 1
    assert out["rej_rr"][0][0] == 12


def test_loai_vi_max_rr():
    out = run_kpfs(bars_full(), CTX_FULL, jp=JP(max_rr=1.0))
    assert out["signals"] == []
    assert len(out["rej_rr"]) == 1


def test_loai_vi_sl_qua_ngan():
    """min_sl_dist = minSlTicks * mintick. Risk that = 10.5."""
    out = run_kpfs(bars_full(), CTX_FULL, p=P(min_sl_dist=11.0))
    assert out["signals"] == []


def test_moi_kieu_loai_deu_van_tieu_setup():
    """Spec §13.2 muc 10, ve sau: bSt := 0 nam NGOAI moi if con."""
    for kw in ({"jp": JP(min_rr=2.0)},
               {"jp": JP(max_rr=1.0)},
               {"p": P(min_sl_dist=11.0)}):
        out = run_kpfs(bars_full(), CTX_FULL, **kw)
        assert out["buy"].st == "IDLE", kw


def test_loai_vi_rr_khong_tieu_co():
    """Spec §13.2 muc 11 — bai hoc tu vong soat cuoi cua kill_peak."""
    out = run_kpfs(bars_full(), CTX_FULL, jp=JP(min_rr=2.0))
    assert out["ctx"].flag_buy_used is False


def test_vao_lenh_thi_tieu_co():
    out = run_kpfs(bars_full(), CTX_FULL)
    assert out["ctx"].flag_buy_used is True


def test_co_chet_giua_luc_M1_dang_BROKEN():
    """Spec §13.2 muc 12: M1 chay tiep, khong lenh, khong reset."""
    # ctx cat len 70 o nen 11, khi M1 dang o BROKEN -> co chet NEWLEVEL
    ctx = CTX_BUY + [45, 45, 45, 45, 45, 45, 75, 45]
    out = run_kpfs(bars_full(), ctx)
    assert out["signals"] == []
    assert (11, "NEW_BUY") in out["ev_ctx"]
    assert out["buy"].st == "IDLE"          # M1 van chay het vong cua no


def test_hai_chieu_doc_lap():
    """Spec §13.2 muc 14."""
    out = run_kpfs(bars_full(), CTX_FULL)
    assert [s["side"] for s in out["signals"]] == ["BUY"]
    assert out["ev_sell"] == []
```

- [ ] **Step 6: Chạy test**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest kpfs_test.py -q
```

Kỳ vọng: `21 passed`.

Nếu có đỏ: kiểm bằng tay xem **test hay oracle** sai theo spec §5.3. Ở dự án trước hai lần test sai chứ không phải code. Sửa bên sai và ghi lý do vào comment ngay tại chỗ.

- [ ] **Step 7: Thêm test cho chiều SELL**

Spec §13.2 mục 13 đòi soi gương cho các mục 1, 5, 7, 10. Dựng một kịch bản SELL đầy đủ theo mẫu `SCEN_SELL` trong `rfs_test.py` (ctx: `35 → 25` mở đo đáy → `55` chốt `killLow`, rồi 8 nến setup SELL M1), rồi viết bốn test:

```python
CTX_SELL_FULL = [35, 25, 28, 40, 55] + [55] * 8
ROWS_SELL_FULL = [
    (100,  98,  99),
    (99,   92,  93),
    (95,   88,  90),   # 2 day doan do = 88 -> killLow
    (97,   91,  96),
    (101,  95, 100),   # 4 chot killLow = 88, bat co SELL
    (105,  99, 104),   # 5 rsi m1 75: cat len 70 -> SEEKING, H1 = 105
    (110, 103, 108),   # 6 rsi m1 80: H1 = 110, R1 = 80
    (107, 101, 102),   # 7 rsi m1 60
    (100,  96,  97),   # 8 rsi m1 45: cat xuong 50 -> ARMED
    (104,  97, 103),   # 9 rsi m1 55
    (112, 103, 110),   # 10 rsi m1 65: vuot H1 = 110 -> BROKEN, H2 = 112
    (111, 105, 106),   # 11 rsi m1 52
    (107, 101, 102),   # 12 rsi m1 42: cat xuong 50 lan nua -> TIN HIEU
]
RSI_M1_SELL = [45, 45, 45, 45, 45, 75, 80, 60, 45, 55, 65, 52, 42]


def bars_sell():
    return [Bar(h, l, c, r, 1.0)
            for (h, l, c), r in zip(ROWS_SELL_FULL, RSI_M1_SELL)]


def test_sell_ra_lenh_tp_bang_killlow():
    out = run_kpfs(bars_sell(), CTX_SELL_FULL)
    assert len(out["signals"]) == 1
    s = out["signals"][0]
    assert s["side"] == "SELL"
    assert s["bar"] == 12
    assert s["entry"] == 102.0
    assert s["sl"] == 112.5             # H2 112 + 0.5 * atr
    assert s["tp"] == 88.0              # = killLow


def test_sell_chan_2_truoc_co_thi_bi_chan():
    ctx = [35, 25, 28, 40, 45, 45, 45, 45, 45, 45, 45, 45, 55]
    out = run_kpfs(bars_sell(), ctx)
    assert out["signals"] == []


def test_sell_loai_vi_min_rr():
    out = run_kpfs(bars_sell(), CTX_SELL_FULL, jp=JP(min_rr=5.0))
    assert out["signals"] == []
    assert len(out["rej_rr"]) == 1


def test_sell_loai_vi_rr_khong_tieu_co():
    out = run_kpfs(bars_sell(), CTX_SELL_FULL, jp=JP(min_rr=5.0))
    assert out["ctx"].flag_sell_used is False
```

- [ ] **Step 8: Chạy test**

Kỳ vọng: `25 passed`.

Nếu giá trị `entry`/`sl`/`tp` của chiều SELL không khớp, **tính lại bằng tay** từ dữ liệu rồi sửa **test**, không sửa oracle — trừ khi đọc kỹ thấy oracle thật sự sai spec §5.4.

- [ ] **Step 9: Mutation testing khối nối — sáu mutation của spec §13.3**

Mỗi lần: sửa `kpfs_oracle.py` → `rm -rf __pycache__` → chạy test → ghi số đỏ → hoàn nguyên.

| # | Mutation | Kỳ vọng |
|---|---|---|
| 1 | `sig["p2_bar"] < flag_bar` → `<=` | ≥1 đỏ |
| 2 | Bỏ `if not flag` khỏi `_join` | ≥2 đỏ |
| 3 | `c.flag_buy_used = True` chuyển lên **trước** kiểm `rr` | ≥1 đỏ (`test_loai_vi_rr_khong_tieu_co`) |
| 4 | `sig["tp"] = lvl` → `sig["tp"] = entry + 3 * risk` | ≥2 đỏ |
| 5 | `rr < jp.min_rr` → `rr <= jp.min_rr` | có thể **sống** — nếu sống, thêm test biên `min_rr` đúng bằng RR thật rồi chạy lại cho tới khi chết |
| 6 | Trong `run_kpfs`, gọi `step_ctx` **sau** vòng lặp `step_side` | ≥1 đỏ |

Ghi lại số test đỏ của từng mutation — con số này vào commit message.

- [ ] **Step 10: Chạy lại toàn bộ, chứng minh không phá test cũ**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest rfs_test.py blockdiff_test.py kpfs_test.py -q
```

Kỳ vọng: `57 passed` (20 + 12 + 25). **`rfs_test.py` phải vẫn đúng 20 xanh** — đó là chứng cứ `rfs_oracle.py` không bị động tới.

---

## Task 4: Indicator — khung, inputs, khối bối cảnh HTF

**Files:**
- Create: `pine/kill_peak_fs_indicator.pine`

**Interfaces:**
- Consumes: `blockdiff.py` (Task 1) làm cổng nghiệm thu; vùng `BOI CANH HTF` trong `pine/kill_peak_indicator.pine` làm bản gốc để chép.
- Produces: file Pine có `indicator(...)`, đủ bộ input của spec §10, và vùng `KHOI BOI CANH HTF` chép nguyên văn. Task 5 nối tiếp vào cuối file này.

- [ ] **Step 1: Viết header + khai báo `indicator`**

Tạo `pine/kill_peak_fs_indicator.pine`. Mở đầu `//@version=6`, rồi khối comment header nêu: ý tưởng (M3 chốt mức chờ kill, M1 chờ failure swing, TP = mức đó); ba tầng và nguồn chép của từng tầng; **bất biến chép nguyên văn** và tên công cụ `blockdiff.py`; cảnh báo chưa compile; và rủi ro §11.1 (điểm vào muộn → RR kém hệ thống, đọc dòng "Loại vì RR" ở bảng đếm trước tiên).

```pine
indicator("Kill Peak FS", overlay=true, max_lines_count=500, max_labels_count=500)
```

- [ ] **Step 2: Viết toàn bộ input theo spec §10**

Chép đúng tên, đúng mặc định, đúng nhóm từ bảng trong spec §10. Bảy nhóm: `Boi canh (HTF)`, `RSI (khung chart)`, `Huy setup M1`, `Cua so cho kill`, `Rui ro`, `Chieu`, `Hien thi`.

Không có `tpR`. Không có `fastLen`/`fHi`/`fLo`. Không có `hlMarginAtr`.

`htfTf = input.timeframe("3", "Khung boi canh", group=grpCtx)` — mặc định **"3"**, không phải "5".

Nhóm `Hien thi` gồm **bảy**: `showCtx`, `showState`, `showDiv`, `showSig`, `showRejected`, `showTable`, `showCounters`.

Tooltip dài thì đặt trên dòng nối tiếp thụt **5 dấu cách**.

- [ ] **Step 3: Viết khối series HTF + guard khung**

```pine
float ctxRsi = request.security(syminfo.tickerid, htfTf, ta.rsi(close, ctxLen)[1],
     barmerge.gaps_off, barmerge.lookahead_on)

float tfRatio = timeframe.in_seconds(htfTf) * 1.0 / timeframe.in_seconds()
int   n       = math.max(1, int(math.ceil(tfRatio)))

// ta.* phai goi o top level, khong duoc nam trong if — chung giu state noi bo
float seedHigh = ta.highest(high, n)
float seedLow  = ta.lowest(low, n)

if barstate.isfirst and timeframe.in_seconds(htfTf) <= timeframe.in_seconds()
    runtime.error("Khung boi canh phai lon hon khung chart")
```

`int(math.ceil(...))` — `math.ceil` trả float, Pine không tự thu hẹp.

- [ ] **Step 4: Chép vùng `BOI CANH HTF` nguyên văn**

Chép **bằng máy**, không gõ tay. Chạy:

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && python - <<'PYEOF'
import io, sys
sys.path.insert(0, "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad")
from blockdiff import find_regions
src = io.open("pine/kill_peak_indicator.pine", encoding="utf-8").read().split("\n")
body = find_regions(src)["BOI CANH HTF"]
out = ["// ---- KHOI BOI CANH HTF ----"] + body + ["// ---- HET KHOI BOI CANH HTF ----"]
io.open("C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad/htf_block.txt",
        "w", encoding="utf-8", newline="\n").write("\n".join(out))
print(len(out), "dong")
PYEOF
```

Rồi nối nội dung file đó vào cuối `pine/kill_peak_fs_indicator.pine`.

- [ ] **Step 5: Chạy checker tĩnh**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && python "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad/kp_check.py" pine/kill_peak_fs_indicator.pine
```

Kỳ vọng: `SACH`.

- [ ] **Step 6: Chạy blockdiff**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && python "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad/blockdiff.py"; echo "rc=$?"
```

Kỳ vọng: `GIONG HET  BOI CANH HTF` cho cả ba file (kill_peak_indicator, kill_peak_strategy, kill_peak_fs_indicator) và `rc=0`.

- [ ] **Step 7: Đọc tay — đối chiếu tên biến input với khối chép**

Khối `BOI CANH HTF` dùng `ctxHi`, `ctxMid`, `ctxLo`, `seedHigh`, `seedLow`. Xác nhận cả năm tên đó đã được khai báo ở trên trong file mới, đúng chính tả. Đây là lỗi mà `kp_check.py` **không** bắt được — nó không phân giải tên.

- [ ] **Step 8: Commit**

Tiêu đề: `feat(pine): kill_peak_fs indicator - khung, inputs, khoi boi canh M3`.
Thân bài: nêu file mới; khối HTF chép bằng máy chứ không gõ tay; blockdiff GIONG HET ba file; `htfTf` mặc định "3"; danh sách input bị bỏ so với hai file nguồn (`tpR`, `fastLen`/`fHi`/`fLo`, `hlMarginAtr`); và câu **chưa compile**.

---

## Task 5: Indicator — máy M1 ba mảnh + hai khối nối

Đây là trái tim của dự án.

**Files:**
- Modify: `pine/kill_peak_fs_indicator.pine`

**Interfaces:**
- Consumes: `flagBuy`, `flagBuyBar`, `flagBuyUsed`, `killHigh` (và bộ SELL) từ khối HTF của Task 4; các input `requireLeg2AfterFlag`, `oneTradePerFlag`, `minRR`, `maxRR`, `minSlTicks`, `slAtrMult` từ Task 4.
- Produces: `bSig`, `bEntry`, `bSl`, `bTp`, `bRr`, `bRejRr` và bộ SELL — Task 6 (vẽ) và Task 7 (strategy) đọc chúng.

- [ ] **Step 1: Khai báo bốn biến mới, NGOÀI vùng chép**

Thêm vào `pine/kill_peak_fs_indicator.pine`, ngay sau khối HTF và **trước** mốc `KHOI M1-A`:

```pine
// Bon bien nay KHONG co trong rsi_failure_swing (da kiem: 0 lan xuat hien).
// Chung phuc vu bo loc RR, von la thu moi cua script nay. Dat chung trong
// vung chep la pha bat bien chep nguyen van ngay tu dong dau.
float bRr    = na
bool  bRejRr = false
float sRr    = na
bool  sRejRr = false
```

- [ ] **Step 2: Chép ba mảnh M1 bằng máy**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && python - <<'PYEOF'
import io, sys
SP = "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad/"
sys.path.insert(0, SP)
from blockdiff import find_regions
src = io.open("pine/rsi_failure_swing_indicator.pine", encoding="utf-8").read().split("\n")
r = find_regions(src)
for name in ("M1-A", "M1-B", "M1-C"):
    out = ["// ---- KHOI %s ----" % name] + r[name] + ["// ---- HET KHOI %s ----" % name]
    io.open(SP + "m1_%s.txt" % name, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print(name, len(out), "dong")
PYEOF
```

- [ ] **Step 3: Ghép ba mảnh + hai chỗ trống cho khối nối**

Nối vào cuối file theo đúng thứ tự: `m1_M1-A.txt`, rồi để trống một dòng, rồi `m1_M1-B.txt`, rồi trống, rồi `m1_M1-C.txt`.

Hai chỗ trống là nơi J-BUY (giữa M1-A và M1-B) và J-SELL (giữa M1-B và M1-C) sẽ nằm.

- [ ] **Step 4: Viết J-BUY**

Chèn vào chỗ trống giữa `HET KHOI M1-A` và `KHOI M1-B`:

```pine
// 3. tin hieu — PHAI dung truoc buoc 4, xem header.
//    Day la KHOI NOI: thay cho than buoc 3 cua rsi_failure_swing. TP khong
//    con la boi so R ma la killHigh, va co them gate co + cua so + loc RR.
//    Vi tri cua no truoc buoc 4 la load-bearing: mot nen vua thung bP1 vua
//    dong cua tren 50 chi dat BROKEN, khong ra tin hieu.
if bSt == 3 and xUpMid
    bool gate = enableBuy and flagBuy and not na(killHigh)
         and (not requireLeg2AfterFlag or bP2Bar >= flagBuyBar)
         and not (oneTradePerFlag and flagBuyUsed)
    if gate
        float e = close
        float s = bP2 - slAtrMult * atr
        bool  slOk = not (minSlTicks > 0 and e - s < minSlTicks * syminfo.mintick)
        if e - s > 0 and slOk and killHigh - e > 0
            float r = (killHigh - e) / (e - s)
            if r >= minRR and (maxRR <= 0 or r <= maxRR)
                bSig        := true
                bEntry      := e
                bSl         := s
                bTp         := killHigh
                bRr         := r
                flagBuyUsed := true
            else
                bRejRr := true
                bRr    := r
    bSt := 0
```

Hai điểm sinh tử, đã có test oracle phủ:

- `bSt := 0` nằm **ngoài** mọi `if` con — setup bị loại vì bất cứ lý do gì vẫn bị tiêu.
- `flagBuyUsed := true` nằm **trong** nhánh ra tín hiệu, sau khi mọi bộ lọc đã qua. Một lệnh bị loại mà vẫn tiêu cờ sẽ làm bảng đếm đọc sai, và bảng đếm là phép đo của dự án.

Dòng nối tiếp của `bool gate` thụt **9 dấu cách**.

- [ ] **Step 5: Viết J-SELL**

Chèn vào chỗ trống giữa `HET KHOI M1-B` và `KHOI M1-C`:

```pine
// 3. tin hieu chieu SELL — guong hoan toan cua J-BUY o tren.
if sSt == 3 and xDnMid
    bool gate = enableSell and flagSell and not na(killLow)
         and (not requireLeg2AfterFlag or sP2Bar >= flagSellBar)
         and not (oneTradePerFlag and flagSellUsed)
    if gate
        float e = close
        float s = sP2 + slAtrMult * atr
        bool  slOk = not (minSlTicks > 0 and s - e < minSlTicks * syminfo.mintick)
        if s - e > 0 and slOk and e - killLow > 0
            float r = (e - killLow) / (s - e)
            if r >= minRR and (maxRR <= 0 or r <= maxRR)
                sSig         := true
                sEntry       := e
                sSl          := s
                sTp          := killLow
                sRr          := r
                flagSellUsed := true
            else
                sRejRr := true
                sRr    := r
    sSt := 0
```

- [ ] **Step 6: Chạy checker tĩnh**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && python "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad/kp_check.py" pine/kill_peak_fs_indicator.pine
```

Kỳ vọng: `SACH`. Nếu báo lỗi thụt dòng, kiểm hai dòng nối tiếp của `bool gate` — phải là 9 dấu cách.

- [ ] **Step 7: Chạy blockdiff**

Kỳ vọng: `GIONG HET` cho `M1-A`, `M1-B`, `M1-C` giữa `kill_peak_fs_indicator.pine` và cặp `rsi_failure_swing_*`, cộng `GIONG HET BOI CANH HTF`, `rc=0`.

- [ ] **Step 8: Đọc tay — đối chiếu J-BUY với `_join` của oracle, từng dòng**

Mở `<SP>/kpfs_oracle.py` hàm `_join` cạnh J-BUY. Xác nhận từng điều kiện khớp một-một:

| Oracle | Pine |
|---|---|
| `if not flag or lvl != lvl` | `flagBuy and not na(killHigh)` |
| `sig["p2_bar"] < flag_bar` | `bP2Bar >= flagBuyBar` (đảo dấu) |
| `jp.one_trade_per_flag and used` | `not (oneTradePerFlag and flagBuyUsed)` |
| `reward <= 0` | `killHigh - e > 0` |
| `rr < min_rr or (max_rr > 0 and rr > max_rr)` | `r >= minRR and (maxRR <= 0 or r <= maxRR)` |
| `p.min_sl_dist` | `minSlTicks * syminfo.mintick` |

Mọi chỗ lệch: **DỪNG và báo**, ghi rõ bên nào đúng theo spec §5.3.

- [ ] **Step 9: Đọc tay — xác nhận mọi tên biến khối nối dùng đều tồn tại**

J-BUY dùng: `bSt, xUpMid, enableBuy, flagBuy, killHigh, requireLeg2AfterFlag, bP2Bar, flagBuyBar, oneTradePerFlag, flagBuyUsed, close, bP2, slAtrMult, atr, minSlTicks, minRR, maxRR, bSig, bEntry, bSl, bTp, bRr, bRejRr`.

Kiểm từng cái có mặt: `bSt`/`xUpMid`/`bP2Bar`/`bP2`/`atr`/`bSig`/`bEntry`/`bSl`/`bTp` đến từ M1-A; `flagBuy`/`killHigh`/`flagBuyBar`/`flagBuyUsed` từ khối HTF; còn lại là input hoặc bốn biến ở Step 1.

`kp_check.py` **không** phân giải tên nên bước này không thay thế được bằng máy.

- [ ] **Step 10: Commit**

Tiêu đề: `feat(pine): kill_peak_fs indicator - may M1 ba manh + hai khoi noi`.
Thân bài: nêu tách ba mảnh và lý do (thân bước 3 khác nhau, mà vị trí bước 3 trước bước 4 là load-bearing); bốn biến RR khai báo ngoài vùng chép; hai điểm sinh tử `bSt := 0` ngoài mọi if và `flagBuyUsed` trong nhánh ra tín hiệu; blockdiff GIONG HET bốn vùng; kp_check SACH; **chưa compile**.

---

## Task 6: Indicator — vẽ và hai bảng

**Files:**
- Modify: `pine/kill_peak_fs_indicator.pine`

**Interfaces:**
- Consumes: mọi biến state và tín hiệu từ Task 4 và Task 5.
- Produces: không gì cho task sau (Task 7 bỏ hết phần này trừ hai `plotshape`).

**Bất biến của task này:** mọi predicate dùng để **vẽ** phải giống hệt predicate dùng để **ra tín hiệu**. Ở `kill_peak` Task 6 đã mắc đúng lỗi này — phần vẽ dùng `lastLowP > prevLowP`, phần tín hiệu dùng `+ hlMarginAtr * atr`, nên chart vẽ nhãn xanh mà strategy không đồng ý. Một công cụ soi tay vẽ sai là một công cụ nói dối.

- [ ] **Step 1: Đường mức chờ kill, có guard `na`**

```pine
var line bLvlLn = na
var line sLvlLn = na

if showCtx and flagBuy and not flagBuy[1]
    bLvlLn := line.new(bar_index, killHigh, bar_index + 1, killHigh,
         color=color.new(color.teal, 20), width=1, style=line.style_dashed)
if showCtx and not na(bLvlLn) and flagBuy
    line.set_x2(bLvlLn, bar_index)

if showCtx and flagSell and not flagSell[1]
    sLvlLn := line.new(bar_index, killLow, bar_index + 1, killLow,
         color=color.new(color.red, 20), width=1, style=line.style_dashed)
if showCtx and not na(sLvlLn) and flagSell
    line.set_x2(sLvlLn, bar_index)
```

`not na(bLvlLn)` là bắt buộc: với `showCtx` tắt rồi bật giữa chart, `set_x2(na, ...)` là runtime error giết script.

- [ ] **Step 2: Tô nền theo trạng thái M1**

```pine
color stateCol = bSt == 1 or sSt == 1 ? color.new(color.gray, 92) :
     bSt == 2 ? color.new(color.teal, 90) :
     bSt == 3 ? color.new(color.teal, 80) :
     sSt == 2 ? color.new(color.red, 90) :
     sSt == 3 ? color.new(color.red, 80) :
     na
bgcolor(showState ? stateCol : na, title="Trang thai M1")
```

Dòng nối tiếp thụt 5 dấu cách.

- [ ] **Step 3: Đường phân kì chân 1 → chân 2**

```pine
if showDiv and bSig and not na(bP1Bar) and not na(bP2Bar)
    line.new(bP1Bar, bP1, bP2Bar, bP2, color=color.new(color.teal, 0), width=2)
if showDiv and sSig and not na(sP1Bar) and not na(sP2Bar)
    line.new(sP1Bar, sP1, sP2Bar, sP2, color=color.new(color.red, 0), width=2)
```

- [ ] **Step 4: Mũi tên, nhãn entry, đường SL/TP**

```pine
plotshape(showSig and bSig, title="BUY", style=shape.triangleup, location=location.belowbar,
     color=color.new(color.teal, 0), size=size.small)
plotshape(showSig and sSig, title="SELL", style=shape.triangledown, location=location.abovebar,
     color=color.new(color.red, 0), size=size.small)

if showSig and bSig
    label.new(bar_index, bEntry, "BUY " + str.tostring(bEntry, format.mintick) +
         "  R " + str.tostring(bRr, "#.##"), style=label.style_label_up,
         color=color.new(color.teal, 20), textcolor=color.white, size=size.small)
    line.new(bar_index, bSl, bar_index + 20, bSl,
         color=color.new(color.red, 0), width=1, style=line.style_dashed)
    line.new(bar_index, bTp, bar_index + 20, bTp,
         color=color.new(color.teal, 0), width=1, style=line.style_dashed)
```

Viết khối SELL soi gương y hệt (`sSig`, `sEntry`, `sRr`, `sSl`, `sTp`, `label.style_label_down`). **Chép ra đầy đủ, không viết "tương tự trên".**

- [ ] **Step 5: Nhãn setup bị loại vì RR, và nhãn lý do cờ chết**

```pine
if showRejected and bRejRr
    label.new(bar_index, low, "LOAI RR " + str.tostring(bRr, "#.##"),
         style=label.style_label_up, color=color.new(color.gray, 70),
         textcolor=color.gray, size=size.tiny)
if showRejected and sRejRr
    label.new(bar_index, high, "LOAI RR " + str.tostring(sRr, "#.##"),
         style=label.style_label_down, color=color.new(color.gray, 70),
         textcolor=color.gray, size=size.tiny)

if showCtx and not na(buyEnd)
    label.new(bar_index, high, buyEnd, style=label.style_label_down,
         color=color.new(color.gray, 75), textcolor=color.gray, size=size.tiny)
if showCtx and not na(sellEnd)
    label.new(bar_index, low, sellEnd, style=label.style_label_up,
         color=color.new(color.gray, 75), textcolor=color.gray, size=size.tiny)
```

- [ ] **Step 6: Bảng trạng thái theo spec §8.1**

Tám hàng, hai cột, `table.new(position.top_right, 2, 8, border_width=1)`, dựng trong `if showTable and barstate.islast`, có guard `if na(tbl)` trước khi `table.new`.

Hàm tên trạng thái:

```pine
f_stName(s) =>
    s == 1 ? "CHO HOI" : s == 2 ? "SAN SANG" : s == 3 ? "DA PHA CHAN 1" : "—"
```

Hàng cuối — hàng quan trọng nhất khi soi tay, cho thấy RR teo dần theo từng nến giá hồi lên:

```pine
    float liveRr = flagBuy and not na(bP2) and not na(atr) ?
         (killHigh - close) / (close - (bP2 - slAtrMult * atr)) :
         flagSell and not na(sP2) and not na(atr) ?
         (close - killLow) / ((sP2 + slAtrMult * atr) - close) :
         na
    table.cell(tbl, 0, 7, "RR neu vao bay gio", text_size=size.small)
    table.cell(tbl, 1, 7, na(liveRr) or liveRr <= 0 ? "—" : str.tostring(liveRr, "#.##"), text_size=size.small)
```

Mẫu số có thể âm hoặc bằng 0 khi `close` nằm dưới SL — điều kiện `liveRr <= 0` xử chỗ đó.

- [ ] **Step 7: Bảng đếm theo spec §8.2**

Bảy bộ đếm `var int`, tăng ở đúng chỗ:

```pine
var int cntFlag   = 0
var int cntKill   = 0
var int cntCtxOut = 0
var int cntSetup  = 0
var int cntRejRr  = 0
var int cntRejSl  = 0
var int cntEntry  = 0
```

`cntFlag` tăng khi `flagBuy and not flagBuy[1]` hoặc `flagSell and not flagSell[1]`. `cntKill` tăng khi `buyEnd == "KILL"` hoặc `sellEnd == "KILL"`. `cntCtxOut` tăng khi `buyEnd`/`sellEnd` khác `na` và khác `"KILL"`. `cntRejRr` tăng theo `bRejRr`/`sRejRr`. `cntEntry` tăng theo `bSig`/`sSig`.

`cntSetup` và `cntRejSl` cần biến phụ đặt **trong khối nối** — mà khối nối là code riêng của file này nên được phép. Thêm vào J-BUY, ngay sau `if gate`: một `bool bGateOk = true` để đếm; và trong nhánh `slOk` sai: `bRejSl := true`. **Nếu làm vậy thì J-BUY của indicator và của strategy phải giống hệt nhau** — nhớ chép sang ở Task 7.

Cách đơn giản hơn, khuyến nghị: bỏ `cntSetup` và `cntRejSl` khỏi bảng, giữ năm dòng còn lại. Năm dòng đó đã trả lời được câu hỏi trung tâm (`cntKill` so với `cntEntry`) và không phải đụng vào khối nối. **Chọn cách này trừ khi có lý do rõ ràng để làm khác.**

Đặt bảng ở `position.bottom_right` để không đè bảng trạng thái.

- [ ] **Step 8: Chạy checker tĩnh + blockdiff**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && SP="C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && python "$SP/kp_check.py" pine/kill_peak_fs_indicator.pine && python "$SP/blockdiff.py"; echo "rc=$?"
```

Kỳ vọng: `SACH`, mọi vùng `GIONG HET`, `rc=0`.

- [ ] **Step 9: Đọc tay — soát bất biến vẽ**

Duyệt từng lệnh vẽ, đối chiếu predicate của nó với predicate trong khối nối. Cụ thể: nhãn entry vẽ khi `bSig`, mà `bSig` chỉ bật sau khi qua hết gate + `slOk` + RR — nên nhãn không bao giờ xuất hiện cho một setup strategy sẽ bỏ. Xác nhận điều đó đúng cho cả sáu lệnh vẽ.

Đồng thời soát: mọi `line.set_x2` đều có `not na(...)` đi kèm.

- [ ] **Step 10: Commit**

Tiêu đề: `feat(pine): kill_peak_fs indicator - ve va hai bang`.
Thân bài: nêu bất biến "predicate vẽ = predicate tín hiệu" và lý do (bài học `kill_peak` Task 6); guard `na` cho `set_x2`; hàng "RR nếu vào bây giờ" là hàng để soi tay; bảng đếm năm dòng với `cntRejRr` là phép đo chính của dự án; **chưa compile**.

---

## Task 7: File strategy

**Files:**
- Create: `pine/kill_peak_fs_strategy.pine`

**Interfaces:**
- Consumes: toàn bộ `pine/kill_peak_fs_indicator.pine`.
- Produces: file backtest.

- [ ] **Step 1: Viết header + khai báo `strategy`**

```pine
strategy("Kill Peak FS Strategy", overlay=true, initial_capital=10000,
     default_qty_type=strategy.fixed, currency=currency.NONE,
     commission_type=strategy.commission.percent, commission_value=0.0,
     process_orders_on_close=false, max_labels_count=500)
```

Header nêu: bất biến chép nguyên văn và tên `blockdiff.py`; **bộ lọc vị thế nằm ngoài mọi khối** (khác `kill_peak_strategy.pine` vốn còn đúng một dòng được phép lệch); hệ quả đã biết là tín hiệu rơi trúng lúc đang có vị thế sẽ biến mất khỏi bảng lệnh trong khi cột trạng thái vẫn khớp indicator; lệch rủi ro do entry ở close mà khớp ở open nến sau; và **chưa compile**.

- [ ] **Step 2: Chép inputs, thêm `grpExec`, bỏ nhóm hiển thị thừa**

Chép nguyên bộ input của indicator, bỏ `showCtx`/`showDiv`/`showRejected`/`showTable`/`showCounters`, giữ `showSig`. Thêm:

```pine
grpExec = "Thuc thi lenh"
riskPct = input.float(1.0, "Rui ro % equity moi lenh", minval=0.01, step=0.25, group=grpExec)
```

- [ ] **Step 3: Chép khối series HTF + guard khung + bốn biến RR**

Y hệt Task 4 Step 3 và Task 5 Step 1.

- [ ] **Step 4: Chép năm khối bằng máy**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && python - <<'PYEOF'
import io, sys
SP = "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad/"
sys.path.insert(0, SP)
from blockdiff import find_regions
src = io.open("pine/kill_peak_fs_indicator.pine", encoding="utf-8").read().split("\n")
r = find_regions(src)
parts = []
for name in ("BOI CANH HTF", "M1-A", "M1-B", "M1-C"):
    parts.append("// ---- KHOI %s ----" % name)
    parts.extend(r[name])
    parts.append("// ---- HET KHOI %s ----" % name)
    parts.append("")
io.open(SP + "kpfs_blocks.txt", "w", encoding="utf-8", newline="\n").write("\n".join(parts))
print(len(parts), "dong")
PYEOF
```

Hai khối nối J-BUY và J-SELL **không** nằm trong vùng có mốc, nên phải chép tay từ indicator — chép **nguyên văn**, không sửa một ký tự. Ghép đúng thứ tự: HTF, M1-A, J-BUY, M1-B, J-SELL, M1-C.

- [ ] **Step 5: Viết khối sizing và đặt lệnh**

```pine
// =============================================================================
//  Sizing + dat lenh
//
//  bSl/bTp va sSl/sTp da la MUC GIA tuyet doi, tinh xong trong khoi noi o
//  tren, nen strategy.exit dat MOT LAN la du — khong can cho lenh khop roi
//  tinh lai TP nhu cac file dung TP = boi so R tren gia khop that.
//
//  Bo loc vi the nam O DAY chu khong trong khoi noi: khoi noi phai giong
//  het indicator tung ky tu. Nghia la may trang thai van chay va van tieu
//  setup ngay ca khi dang co lenh — dung nhu indicator — chi rieng lenh la
//  khong duoc dat. Khong dao lenh, khong xep hang.
// =============================================================================
string alertJson = na

if bSig and strategy.position_size == 0
    float slDist = bEntry - bSl
    if slDist > 0
        float riskUsd = strategy.equity * riskPct / 100.0
        float qty     = riskUsd / (slDist * syminfo.pointvalue)
        strategy.entry("L", strategy.long, qty=qty, comment="BUY kill peak fs")
        strategy.exit("LX", from_entry="L", stop=bSl, limit=bTp)
        alertJson := '{"symbol":"' + syminfo.ticker + '","tf":"' + timeframe.period + '","direction":"BUY","setup":"KILLPEAKFS"' + ',"entry":' + str.tostring(bEntry, "#.#####") + ',"sl":' + str.tostring(bSl, "#.#####") + ',"tp":' + str.tostring(bTp, "#.#####") + '}'

if sSig and strategy.position_size == 0
    float slDist = sSl - sEntry
    if slDist > 0
        float riskUsd = strategy.equity * riskPct / 100.0
        float qty     = riskUsd / (slDist * syminfo.pointvalue)
        strategy.entry("S", strategy.short, qty=qty, comment="SELL kill peak fs")
        strategy.exit("SX", from_entry="S", stop=sSl, limit=sTp)
        alertJson := '{"symbol":"' + syminfo.ticker + '","tf":"' + timeframe.period + '","direction":"SELL","setup":"KILLPEAKFS"' + ',"entry":' + str.tostring(sEntry, "#.#####") + ',"sl":' + str.tostring(sSl, "#.#####") + ',"tp":' + str.tostring(sTp, "#.#####") + '}'

if not na(alertJson)
    alert(alertJson, alert.freq_once_per_bar_close)
```

- [ ] **Step 6: Hai `plotshape`**

```pine
plotshape(showSig and bSig, title="BUY", style=shape.triangleup, location=location.belowbar,
     color=color.new(color.teal, 0), size=size.small)
plotshape(showSig and sSig, title="SELL", style=shape.triangledown, location=location.abovebar,
     color=color.new(color.red, 0), size=size.small)
```

Kèm comment nói rõ: mũi tên vẽ theo **tín hiệu**, không phải lệnh khớp; tín hiệu bị bỏ vì đang có vị thế vẫn có mũi tên mà không có lệnh — có chủ ý, để đối chiếu được với indicator bằng mắt.

- [ ] **Step 7: Chạy checker tĩnh + blockdiff**

Kỳ vọng: `SACH`, mọi vùng `GIONG HET` trên cả 11 file pine, `rc=0`.

- [ ] **Step 8: Đối chiếu hai khối nối bằng máy**

`blockdiff` không phủ J-BUY/J-SELL vì chúng nằm ngoài mốc. Đối chiếu riêng:

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && python - <<'PYEOF'
import io, difflib, sys
def between(p, a, b):
    s = io.open(p, encoding="utf-8").read().split("\n")
    return s[s.index(a) + 1: s.index(b)]
pairs = [("// ---- HET KHOI M1-A ----", "// ---- KHOI M1-B ----"),
         ("// ---- HET KHOI M1-B ----", "// ---- KHOI M1-C ----")]
bad = 0
for a, b in pairs:
    x = between("pine/kill_peak_fs_indicator.pine", a, b)
    y = between("pine/kill_peak_fs_strategy.pine", a, b)
    if x == y:
        print("GIONG HET  khoi noi sau %s (%d dong)" % (a, len(x)))
    else:
        bad = 1
        sys.stdout.writelines(difflib.unified_diff(x, y, "indicator", "strategy", lineterm="\n"))
sys.exit(bad)
PYEOF
echo "rc=$?"
```

Kỳ vọng: hai dòng `GIONG HET khoi noi ...` và `rc=0`.

**Nếu lệch: DỪNG và báo.** Hai khối nối phải giống hệt nhau giữa hai file — chúng là phần code mới duy nhất của dự án, và không có công cụ tự động nào canh chúng ngoài bước này.

- [ ] **Step 9: Đọc tay — soát ba điểm của file strategy**

1. `max_labels_count=500` có mặt trong `strategy(...)` — Pine mặc định 50.
2. Không có `strategy.position_size` ở bất kì đâu **bên trong** năm vùng có mốc hoặc hai khối nối. Grep để chắc:

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && grep -n "strategy.position_size" pine/kill_peak_fs_strategy.pine
```

Kỳ vọng: đúng **hai** dòng, cả hai nằm trong khối sizing ở Step 5.

3. `syminfo.pointvalue` dùng đúng chỗ trong công thức `qty`.

- [ ] **Step 10: Commit**

Tiêu đề: `feat(pine): kill_peak_fs strategy - sizing, exit muc co dinh, alert`.
Thân bài: nêu năm vùng chép bằng máy + hai khối nối chép tay có bước đối chiếu riêng; bộ lọc vị thế nằm ngoài mọi khối, **không ngoại lệ nào** — khác `kill_peak_strategy.pine`; hệ quả đã biết về tín hiệu bị bỏ khi đang có vị thế; `strategy.exit` đặt một lần vì SL/TP là mức giá tuyệt đối; **chưa compile**.

---

## Task 8: Soát cuối và đối chiếu toàn bộ

Vòng soát cuối của `kill_peak` đã bắt được một lỗi Critical mà tám task trước đó bỏ lọt (`minSlTicks` kiểm sau khi cờ đã bị tiêu). Task này tồn tại vì lý do đó.

**Files:**
- Modify: `pine/kill_peak_fs_indicator.pine`, `pine/kill_peak_fs_strategy.pine` (chỉ nếu tìm ra lỗi)

**Interfaces:**
- Consumes: tất cả.
- Produces: báo cáo kiểm chứng để đưa cho người dùng.

- [ ] **Step 1: Chạy toàn bộ cổng nghiệm thu, một lệnh**

```bash
cd "C:/Users/MeoMeo/Desktop/AI BOT TRADING NEW FLOW" && SP="C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && for f in pine/*.pine; do python "$SP/kp_check.py" "$f" > /dev/null || echo "BAN: $f"; done; echo "kp_check xong" && python "$SP/blockdiff.py"; echo "blockdiff rc=$?"
```

Kỳ vọng: không dòng `BAN:` nào, mọi vùng `GIONG HET` (trừ `TIN HIEU` là `LECH CO PHEP`), `rc=0`.

- [ ] **Step 2: Chạy toàn bộ test**

```bash
cd "C:/Users/MeoMeo/AppData/Local/Temp/claude/C--Users-MeoMeo-Desktop-AI-BOT-TRADING-NEW-FLOW/c9bdd694-7f50-4f2c-88cd-a337fa819acb/scratchpad" && rm -rf __pycache__ && python -m pytest rfs_test.py blockdiff_test.py kpfs_test.py -q
```

Kỳ vọng: `57 passed`, trong đó `rfs_test.py` đúng 20 — chứng cứ `rfs_oracle.py` không bị động tới.

- [ ] **Step 3: Soát thứ tự toàn cục theo spec §6**

Đọc `pine/kill_peak_fs_indicator.pine` từ trên xuống, xác nhận đúng thứ tự này và không có gì chen ngang:

```
1. inputs
2. ctxRsi, tfRatio, n, seedHigh, seedLow, guard khung
3. bon bien RR
4. KHOI BOI CANH HTF
5. KHOI M1-A
6. J-BUY
7. KHOI M1-B
8. J-SELL
9. KHOI M1-C
10. ve
11. bang
```

Điểm sinh tử: **khối HTF phải nằm trước khối M1**. Khối nối đọc `flagBuy`/`killHigh` của nến hiện tại; đảo thứ tự là đọc giá trị nến trước mà không báo lỗi gì.

- [ ] **Step 4: Soát năm lỗi đã mắc ở hai dự án trước**

Duyệt từng cái trên cả hai file mới:

| # | Lỗi | Cách soát |
|---|---|---|
| 1 | Bộ lọc đặt **sau** chỗ tiêu cờ | `flagBuyUsed := true` / `flagSellUsed := true` phải nằm trong nhánh trong cùng, sau mọi `if` lọc |
| 2 | `line.set_x2` trên handle `na` | `grep -n "set_x2" pine/kill_peak_fs_*.pine` — mỗi chỗ phải có `not na(...)` ở dòng `if` ngay trên |
| 3 | Predicate vẽ khác predicate tín hiệu | mọi lệnh vẽ tín hiệu phải gác bằng `bSig`/`sSig`, không tự tính lại điều kiện |
| 4 | `ta.*` nằm trong `if` | `kp_check.py` bắt; xác nhận nó đã chạy |
| 5 | `math.round`/chia int trả float vào chỗ cần int | `grep -n "math.ceil\|math.round\|math.max(1," pine/kill_peak_fs_*.pine` — phải có `int(...)` bọc ngoài |

- [ ] **Step 5: Đối chiếu một kịch bản đầu-cuối bằng tay**

Lấy `ROWS_FULL`/`CTX_FULL`/`RSI_M1` từ `kpfs_test.py`. Đi bộ qua 13 nến, với mỗi nến ghi ra bằng tay: `flagBuy`, `killHigh`, `bSt`, `bP1`, `bP2`, `bR1`, `bR2` — theo đúng code Pine chứ không theo oracle. So kết quả cuối với `test_setup_du_va_co_bat_thi_ra_lenh_tp_bang_killhigh`.

Đây là lớp kiểm chứng duy nhất **không** đi qua oracle, nên nó bắt được lỗi mà oracle và Pine cùng sai.

Nếu lệch: **DỪNG và báo**, kèm bảng đi bộ từng nến.

- [ ] **Step 6: Viết báo cáo kiểm chứng**

Ghi vào commit message cuối, nêu đúng những gì đã làm và đúng những gì chưa:

Đã làm — `kp_check.py` SACH trên toàn bộ `pine/`; `blockdiff.py` sạch trên 5 vùng × 11 file; 57 test xanh trong đó 20 test cũ không đổi; N mutation giết được test (liệt kê số đỏ từng cái); đi bộ tay một kịch bản đầu-cuối.

Chưa làm — **chưa compile trên TradingView**; chưa chạy backtest nên chưa có số liệu cho rủi ro §11.1 và §11.2; ánh xạ M3→M1 không nằm trong oracle nên cách mồi `run_high` lệch giữa oracle và Pine ở vài nến đầu mỗi đoạn đo.

- [ ] **Step 7: Commit**

Tiêu đề: `chore(pine): kill_peak_fs - soat cuoi, bao cao kiem chung`.

Nếu Step 1–5 không tìm ra lỗi nào thì commit rỗng (`--allow-empty`) chỉ để ghi báo cáo; nếu có sửa thì commit kèm sửa.

- [ ] **Step 8: Báo cáo cho người dùng**

Nói rõ ba điều, không hedge:

1. Hai file mới đã xong, qua checker tĩnh và đối chiếu khối, **chưa compile**.
2. Việc tiếp theo là nạp lên TradingView khung M1 XAUUSD. Chỗ dễ vỡ nhất: `int(math.ceil(...))` và `request.security` với `lookahead_on`.
3. Sau khi compile được, chạy backtest rồi **đọc dòng `LOAI RR` ở bảng đếm trước tiên** — spec §11.1 dự đoán con số đó sẽ lớn, và đó là thứ quyết định setup này có dùng được không.

Không merge, không push. Đợi người dùng xác nhận đã compile.

---

## Tự soát kế hoạch

**1. Phủ spec.** Duyệt từng mục spec, tìm task tương ứng:

| Spec | Task |
|---|---|
| §2 kiến trúc ba tầng | 4, 5 |
| §2.1 bỏ zigzag | 4 (không chép sang) |
| §2.2 hai file | 4–6, 7 |
| §3 tầng M3 | 4 Step 3–4; oracle ở 2 |
| §4 tầng M1 | 5 Step 2–3; oracle mượn `rfs_oracle` |
| §5.1 vì sao tách ba mảnh | 1 Step 16, 5 Step 2 |
| §5.2 bốn biến mới ngoài vùng chép | 5 Step 1 |
| §5.3 J-BUY | 5 Step 4; oracle 3 |
| §5.4 J-SELL | 5 Step 5; oracle 3 Step 7 |
| §5.5 cửa sổ tự động | 3 Step 5 (`test_co_bat_cung_nen_xac_nhan_thi_bi_chan`) |
| §5.6 cờ chết giữa chừng | 3 Step 5 (`test_co_chet_giua_luc_M1_dang_BROKEN`) |
| §6 thứ tự toàn cục | 8 Step 3 |
| §7 vẽ | 6 Step 1–5 |
| §8.1 bảng trạng thái | 6 Step 6 |
| §8.2 bảng đếm | 6 Step 7 |
| §9 file strategy | 7 |
| §10 inputs | 4 Step 2 |
| §11 rủi ro | 4 Step 1 (header), 8 Step 6 (báo cáo) |
| §12 bất biến chép + `blockdiff.py` | 1 |
| §13.1 checker tĩnh | mọi task, tổng ở 8 Step 1 |
| §13.2 oracle | 2, 3 |
| §13.3 mutation | 2 Step 7, 3 Step 9 |
| §13.4 đối chiếu khối | 8 Step 1 |
| §14 ngoài phạm vi | không task nào — đúng |

Không có mục spec nào thiếu task.

**2. Chỗ kế hoạch tự nhận là chưa chắc.** Ba chỗ được đánh dấu "DỪNG và báo" thay vì đoán:

- Task 3 Step 3 — `step_side` có trả `p2_bar` trong `sig` hay không. Chưa đọc kỹ `rfs_oracle.py` đủ để khẳng định; kế hoạch đưa sẵn cách sửa nếu không có.
- Task 1 Step 12 và 18 — nếu vùng `BOI CANH HTF` hoặc ba vùng M1 đã trôi sẵn giữa các file đã commit.
- Task 2 Step 7 mutation #4 và Task 3 Step 9 mutation #5 — có khả năng sống sót; kế hoạch yêu cầu thêm test biên cho tới khi chúng chết, chứ không cho phép ghi "sống sót, chấp nhận".

**3. Nhất quán tên.** `find_regions`, `compare`, `load_exceptions`, `Diff`, `scan` (Task 1) — dùng lại đúng tên ở Task 4 Step 4, Task 5 Step 2, Task 7 Step 4. `Ctx`, `CP`, `step_ctx` (Task 2) — dùng lại ở Task 3. `JP`, `run_kpfs` (Task 3) — dùng ở Task 3 và tham chiếu ở Task 8 Step 5. Tên vùng bốn cái ở bảng Global Constraints — dùng nhất quán từ Task 1 đến Task 8.

Một chỗ đã sửa khi soát: Task 6 Step 7 ban đầu đòi thêm biến đếm **vào trong khối nối**, việc đó buộc phải chép sang strategy và làm khối nối phình ra. Đã đổi thành khuyến nghị bỏ hai bộ đếm đó, giữ năm bộ còn lại.

**4. Placeholder.** Quét kế hoạch tìm "TBD", "TODO", "tương tự Task N", "thêm xử lý lỗi phù hợp", bước mô tả việc mà không có code. Hai chỗ đã sửa khi soát: Task 4 Step 2 đếm nhầm "sáu" cho bảy input hiển thị (đã sửa thành bảy); Task 1 Step 16 viết theo lối tự sửa giữa chừng, khó đọc (đã viết lại thành bảng dòng neo). Task 6 Step 4 có câu "viết khối SELL soi gương y hệt" — kèm ngay danh sách đầy đủ sáu tên biến phải đổi, nên không phải placeholder.
