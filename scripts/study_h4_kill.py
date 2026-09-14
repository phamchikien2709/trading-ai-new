"""Nến H4 (lưới neo 17:00 New York) có bị quét cả hai đầu nhiều hơn mức mà hình
học đã giải thích được?

Spec: docs/superpowers/specs/2026-09-09-h4-kill-both-ends-study-design.md

Usage:
  python scripts/study_h4_kill.py
  python scripts/study_h4_kill.py --tf M5 --shifts 200
  python scripts/study_h4_kill.py --source csv --csv data/XAUUSD_m1.csv

Mã thoát: 0 nghiên cứu chạy xong; 1 cổng chặn timezone fail; 2 không đủ dữ liệu.

`verdict` và bốn hằng số của nó KHÔNG nằm ở đây mà ở `rsi_fvg/h4_kill.py`: đó là
cổng kết luận của cả nghiên cứu nên phải có test gọi hàm trực tiếp, mà mọi test
script của repo chạy bằng `subprocess`.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from rsi_fvg.bars import Bars  # noqa: E402
from rsi_fvg.data.csv_loader import load_csv  # noqa: E402
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.data.tz_detect import detect_source_tz  # noqa: E402
from rsi_fvg.h4_grid import DAY_SECONDS  # noqa: E402
# `h4_kill.run_grid`/`run_null` TRÙNG TÊN với `quarter_stats.run_grid`/`run_null`
# nhưng khác chữ ký và khác kiểu trả về. Script này chỉ dùng bản H4; bản kia
# tuyệt đối không được import vào cùng namespace.
from rsi_fvg.h4_kill import (MIN_CELL_N, STD_HORIZON_MIN,  # noqa: E402
                             decile_cell_table, excursion_usd_by_year,
                             killed_range_usd_by_year, run_grid, run_null,
                             verdict)
from rsi_fvg.quarter_stats import make_offsets, percentile_of  # noqa: E402

TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600}

# argparse in `description` ra STDOUT, va console Windows mac dinh o day la
# cp1252 — no khong ma hoa duoc dau tieng Viet, nen dung `__doc__` lam
# description se lam `--help` NEM UnicodeEncodeError thay vi in tro giup. Ban
# ASCII nay ton tai vi ly do do; `__doc__` phia tren van la ban day du cho nguoi
# doc code. (`scripts/study_quarters.py` con dinh dung loi nay.)
CLI_DOC = """Nen H4 (luoi neo 17:00 New York) co bi quet ca hai dau nhieu hon
muc ma hinh hoc da giai thich duoc?

Spec: docs/superpowers/specs/2026-09-09-h4-kill-both-ends-study-design.md

Vi du:
  python scripts/study_h4_kill.py
  python scripts/study_h4_kill.py --tf M5 --shifts 200
  python scripts/study_h4_kill.py --source csv --csv data/XAUUSD_m1.csv

Ma thoat: 0 chay xong; 1 cong chan timezone fail; 2 khong du du lieu.
"""


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=CLI_DOC,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbol", default="XAUUSDc")
    p.add_argument("--tf", default="M1", choices=sorted(TF_SECONDS))
    p.add_argument("--source", default="mt5", choices=("mt5", "csv"))
    p.add_argument("--csv", type=Path, default=None,
                   help="duong dan CSV khi --source csv")
    p.add_argument("--broker", default="Exness",
                   help="ten broker cua cache MT5, CHI de dan nhan bao cao. "
                        "Terminal tren may nay la Exness; doi nguon thi doi co nay.")
    p.add_argument("--shifts", type=int, default=200,
                   help="so luoi null xin; M1 co gan 1440 moc, H1 chi co 23")
    p.add_argument("--seed", type=int, default=20260909)
    p.add_argument("--data-dir", type=Path, default=ROOT / "data")
    p.add_argument("--out-dir", type=Path, default=None)
    return p.parse_args(argv)


def load_bars(args) -> Bars:
    """Nghiên cứu này không dùng SymbolSpec — không sizing, không cost — nên bỏ
    nửa sau của load_or_fetch."""
    if args.source == "csv":
        if args.csv is None:
            raise SystemExit("--source csv can --csv <duong dan>")
        return Bars.from_dataframe(load_csv(args.csv))
    df, _spec = load_or_fetch(args.symbol, args.tf, args.data_dir)
    return Bars.from_dataframe(df)


def source_label(args) -> str:
    """Spec §6.3: mọi kết quả phải ghi rõ nguồn nào đã sinh ra nó. Trộn hai nguồn
    mà không ghi nhãn là cách chắc chắn nhất để sau này không ai biết con số nào
    tin được."""
    if args.source == "csv":
        return f"CSV {args.csv}"
    return f"{args.broker} {args.symbol} {args.tf} (cache MT5)"


def gate_timezone(bars: Bars, bar_seconds: int, source: str) -> tuple[str, list[str]]:
    """Cổng chặn §6.1. Fail thì thoát 1 và KHÔNG chạy nghiên cứu.

    Mọi biên slot là một mốc giờ treo tường New York, nên nếu cách đọc `time`
    sai thì nghiên cứu đo một lưới khác mà vẫn in ra số trông hợp lý. In cả bảng
    điểm chứ không chỉ người thắng — người đọc phải thấy được khoảng cách.

    Trả về nhãn thắng cộng chính khối chữ đã in, để `summary.md` mang y nguyên
    cái mà người chạy đã thấy trên màn hình (spec §6.1: "in thật to trong báo
    cáo"), không phải một bản tóm tắt khác được dựng lại.
    """
    chk = detect_source_tz(bars.time, bar_seconds)
    block = [
        f"  khe trong ngay tim duoc : {chk.n_gaps}",
        f"  ung vien tot nhat       : {chk.best!r}  score={chk.score:.4f}",
        f"  ung vien nhi            : {chk.runner_up!r}  score={chk.runner_up_score:.4f}",
        "  bang diem (top 5)       : "
        + ", ".join(f"{lab}={sc:.4f}" for lab, sc in chk.table[:5]),
    ]
    block += [f"  ghi chu: {note}" for note in chk.notes]

    print("--- cong chan timezone (spec 6.1) ---")
    for line in block:
        print(line)
    if not chk.ok:
        print("\nFAIL: khong xac dinh duoc timezone cua nguon.")
        print("Moi bien slot la mot moc gio New York, nen doc sai mot gio la do")
        print("mot luoi khac. Khong chay tiep. Xem spec 6.1.")
        sys.exit(1)
    if source == "mt5" and chk.best != "UTC":
        print(f"\nFAIL: nguon mt5 phai doc duoc la UTC, do ra {chk.best!r}.")
        print("Bars.time la instant UTC that (rsi_fvg/quarters.py). Neu no doi")
        print("thi moi ket qua cu cung phai doc lai. Khong chay tiep.")
        sys.exit(1)
    print(f"  PASS ({chk.best})\n")
    block.append(f"  PASS ({chk.best})")
    return chk.best, block


def compare_to_null(real: dict, nulls: pd.DataFrame) -> pd.DataFrame:
    recs = []
    for key, value in real.items():
        col = (nulls[key].to_numpy(dtype="float64")
               if key in nulls.columns else np.array([]))
        finite = col[np.isfinite(col)]
        recs.append({
            "quantity": key, "real": value,
            "null_mean": float(finite.mean()) if finite.size else float("nan"),
            "null_p05": float(np.percentile(finite, 5)) if finite.size else float("nan"),
            "null_p50": float(np.percentile(finite, 50)) if finite.size else float("nan"),
            "null_p95": float(np.percentile(finite, 95)) if finite.size else float("nan"),
            "real_percentile": percentile_of(value, col),
            "n_nulls": int(finite.size),
        })
    return pd.DataFrame(recs)


def report_head(args, bars, rows, nulls, stats, cells, src, tz_block) -> list[str]:
    """Phần báo cáo trước phán quyết. Ba cảnh báo bắt buộc đều nằm TRƯỚC bảng số,
    không nhét xuống cuối: ai đọc bảng trước khi đọc cảnh báo sẽ đọc sai bảng."""
    spread_line = ""
    if bars.spread is not None and np.any(bars.spread > 0):
        spread_line = (f"- spread trung vi: {float(np.median(bars.spread)):.0f} points. "
                       f"Gia la BID nen ti le kill dau TREN thuc te cao hon con so bao "
                       f"(stop mua khop o Ask) — thien lech mot phia, khong sua so.")

    out = [
        "# Nen H4 bi kill hai dau", "",
        f"- nguon: **{src}**",
        f"- bar: {len(bars)}   dong (ngay x slot): {len(rows)}   "
        f"ngay song sot ca ba luat loai: {rows['day_num'].nunique()}",
        f"- luoi null: {len(nulls)}   seed: {args.seed}   "
        f"horizon chuan hoa: {STD_HORIZON_MIN} phut",
        spread_line,
        "- **Day KHONG phai du lieu FXCM.** Dialect FXCM cho `csv_loader` (spec 6.2) "
        "chua duoc lam, nen nghien cuu chay tren nguon o tren lam proxy, dung nhu "
        "spec 6.3 cho phep. Khe nghi cua nguon nay do duoc trung khit 17:00-18:00 NY.",
        "- spec: docs/superpowers/specs/2026-09-09-h4-kill-both-ends-study-design.md",
        "",
        "## Cong chan timezone (spec 6.1)", "",
        "Mot nghien cuu phu thuoc gio treo tuong ma khong noi no da doc gio the nao "
        "la mot nghien cuu khong kiem chung duoc. Bang diem day du:", "",
        "```",
    ]
    out += tz_block
    out += [
        "```", "",
        "## Ba canh bao phai doc TRUOC bang so", "",
        "1. Hai cay duoc hoi (slot 0 va slot 5) la hai cay HEP NHAT trong sau, VA",
        "   theo dinh nghia cua so chung nhan hai cua so DAI NHAT (20h va 24h so",
        "   voi 4-16h). So sanh tho thien vi hai lan cung chieu. Dung dai luong",
        "   `standardized` de so giua cac slot, dung dung `window`.",
        "2. Moi con so ten `*_max` la DUNG MOT diem du lieu (spec 4.4). Max tren",
        "   mau 9 nam noi ve ngay tin tuc te nhat tung xay ra, khong noi ve tuan",
        "   sau. `*_p90` moi la con so dat SL duoc; `*_p95` tach theo nam dua tren",
        "   ~250 quan sat nen da lung lay.",
        "3. Phan vi USD GOP ca mau bi 2025-2026 chi phoi: range median cua vang gap",
        "   13 lan tu 2017 toi 2026 (spec 2.3b). Spec 11 muc 9 CAM dung dang gop do",
        "   de quyet dinh bat cu dieu gi. Dung dang chia `day_atr` (trong bang duoi,",
        "   ten `*_atr_*`), hoac `excursion_usd_by_year.csv` tach theo nam.",
        "",
        "## Bang (slot x decile) — n tung o", "",
        "Spec 4.3 muc 3 buoc 2: de o thua lo ra. `deciles_used_s{k} == 10` doc nhu",
        "\"chuan hoa day du\", nhung mot o trong muoi co the chi co mot quan sat ma",
        f"van mang trong so gop day du. Cong (a) cua section 10 chan o < {MIN_CELL_N}.",
        "Chia decile o day la CUNG mot phep chia voi khoa `min_cell_n_s{k}`.", "",
        "```",
        cells.to_string() if not cells.empty else "(khong co o nao)",
        "```", "",
        "## Bang thong ke (that vs Null A)", "",
        "```", stats.to_string(index=False), "```", "",
        "## File khac trong thu muc nay", "",
        "- `rows.csv` — mot dong moi (ngay, slot), du bon nguyen thuy.",
        "- `stats.csv` — dung bang tren, dang may doc.",
        "- `excursion_usd_by_year.csv`, `killed_range_usd_by_year.csv` — dang USD",
        "  TACH THEO NAM (spec 4.4 dang 2), dang duy nhat dung de dat SL. Dang 3",
        "  (USD gop ca mau) khong duoc tinh o dau va khong duoc them: no bi",
        "  2025-2026 chi phoi. Trong hai file nay moi cot `*_max` cung la DUNG MOT",
        "  diem du lieu.",
        "",
    ]
    return out


def main(argv=None) -> int:
    args = parse_args(argv)
    bar_seconds = TF_SECONDS[args.tf]
    bars = load_bars(args)
    src = source_label(args)
    print(f"nguon: {src} - {len(bars)} bar")
    if len(bars) < 5000:
        print("FAIL: qua it bar de do bat cu thu gi.")
        return 2

    _tz_label, tz_block = gate_timezone(bars, bar_seconds, args.source)

    real, rows = run_grid(bars, bar_seconds)
    if rows.empty:
        print("FAIL: khong con dong nao sau luat loai.")
        return 2
    print(f"bang dong: {len(rows)} dong, {rows['day_num'].nunique()} ngay giao dich")

    offsets = make_offsets("", bar_seconds, args.shifts, args.seed,
                           cycle_seconds=DAY_SECONDS)
    if len(offsets) < args.shifts:
        print(f"chi co {len(offsets)} moc neo kha dung (xin {args.shifts}). "
              f"Chu ky {DAY_SECONDS} s / bar {bar_seconds} s gioi han so luoi null.")
    nulls = run_null(bars, bar_seconds, offsets)
    stats = compare_to_null(real, nulls)
    cells = decile_cell_table(rows, bar_seconds)

    out_dir = args.out_dir or (ROOT / "results" / "h4_kill" / date.today().isoformat())
    out_dir.mkdir(parents=True, exist_ok=True)
    rows.to_csv(out_dir / "rows.csv", index=False)
    stats.to_csv(out_dir / "stats.csv", index=False)
    cells.to_csv(out_dir / "decile_cells.csv")
    excursion_usd_by_year(rows).to_csv(out_dir / "excursion_usd_by_year.csv", index=False)
    killed_range_usd_by_year(rows).to_csv(out_dir / "killed_range_usd_by_year.csv",
                                          index=False)

    passed, verdict_md = verdict(real, stats)
    # KHONG dung to_markdown: no doi `tabulate`, khong co trong requirements.txt.
    head = report_head(args, bars, rows, nulls, stats, cells, src, tz_block)
    (out_dir / "summary.md").write_text("\n".join(head) + verdict_md + "\n",
                                        encoding="utf-8")
    print(verdict_md)
    print(f"\nket qua: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
