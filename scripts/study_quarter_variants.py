"""Phase 1b: do nam bien the cua phep do ⑥ sau khi cach thu nhat that bai.

Spec: docs/superpowers/specs/2026-09-09-quarterly-theory-variants-study-design.md

Usage:
  python scripts/study_quarter_variants.py
  python scripts/study_quarter_variants.py --tf M5 --shifts 200 --seed 20260909

Ma thoat: 0 chay xong; 1 cong chan timezone fail; 2 khong du du lieu.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from rsi_fvg.bars import Bars  # noqa: E402
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.quarter_stats import make_offsets  # noqa: E402
from rsi_fvg.quarter_variants import (DIRECT_VARIANT, PRIMARY_TIER,  # noqa: E402
                                      confirm, pick_winner, screen,
                                      split_halves, verdict)
from rsi_fvg.quarters import TIERS, verify_server_tz  # noqa: E402

TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbol", default="XAUUSDc")
    p.add_argument("--tf", default="M5", choices=sorted(TF_SECONDS))
    p.add_argument("--tier", default=PRIMARY_TIER, choices=sorted(TIERS),
                   help="tang chinh cua ca hai duong; spec 1b section 5 chot q90")
    p.add_argument("--shifts", type=int, default=200,
                   help="so luoi null xin; tang q90 chi co 69 moc kha dung")
    p.add_argument("--seed", type=int, default=20260909)
    p.add_argument("--data-dir", type=Path, default=ROOT / "data")
    p.add_argument("--out-dir", type=Path, default=None)
    return p.parse_args(argv)


def load_bars(symbol: str, tf: str, data_dir: Path) -> Bars:
    """load_or_fetch tra ve (DataFrame, SymbolSpec); nghien cuu nay khong dung spec."""
    df, _spec = load_or_fetch(symbol, tf, data_dir)
    return Bars.from_dataframe(df)


def gate_timezone(bars: Bars, bar_seconds: int) -> None:
    """Cong chan Phase 1 section 3.2. Fail thi thoat 1 va KHONG chay tiep."""
    chk = verify_server_tz(bars.time, bar_seconds)
    print("--- cong chan timezone ---")
    print(f"  mo dau tuan  : {chk.weekly_open_mode!r}  ok={chk.weekly_ok}")
    print(f"  ket khe ngay : {chk.daily_gap_end_mode!r}  ok={chk.daily_ok}")
    for note in chk.notes:
        print(f"  ghi chu: {note}")
    if not chk.ok:
        print("\nFAIL: cach doc Bars.time khong khop du lieu nay. Khong chay tiep.")
        sys.exit(1)
    print("  PASS\n")


def main(argv=None) -> int:
    args = parse_args(argv)
    bar_seconds = TF_SECONDS[args.tf]
    bars = load_bars(args.symbol, args.tf, args.data_dir)
    print(f"{args.symbol} {args.tf}: {len(bars)} bar")
    if len(bars) < 2000:
        print("FAIL: qua it bar de chia hai nua roi do.")
        return 2

    gate_timezone(bars, bar_seconds)

    first, second = split_halves(bars)
    print(f"chia 50/50: nua dau {len(first)} bar, nua sau {len(second)} bar")
    offsets = make_offsets(args.tier, bar_seconds, args.shifts, args.seed)
    if len(offsets) < args.shifts:
        print(f"  [{args.tier}] chi co {len(offsets)} moc neo kha dung "
              f"(xin {args.shifts}). Chu ky {4 * TIERS[args.tier]} s / bar "
              f"{bar_seconds} s gioi han so luoi null.")
    print()

    # Duong B: sang V2-V5 tren nua dau. KHONG tuyen bo gi tai day.
    screened = screen(first, args.tier, offsets)
    print("--- vong sang tren NUA DAU (chi de xep hang, KHONG phai bang chung) ---")
    print(screened.to_string(index=False))
    winner_b = pick_winner(screened)
    print(f"  -> bien the mang sang nua sau: {winner_b}\n")

    # Hai kiem dinh cuoi tren nua sau.
    track_a = confirm(second, args.tier, offsets, DIRECT_VARIANT)
    track_b = confirm(second, args.tier, offsets, winner_b)
    conf = pd.DataFrame([{"track": "A", **track_a}, {"track": "B", **track_b}])
    print("--- kiem dinh cuoi tren NUA SAU ---")
    print(conf.to_string(index=False))
    print()

    # Spec 1b section 5 chot luat quyet dinh section 6 CHI cho tang chinh
    # PRIMARY_TIER (q90). Tang session la mo ta, khong tuyen bo gi. In phan
    # quyet section 6 cho mot tang khac se tao ra mot ket luan co tham quyen
    # gia tren mot tang spec khong cho phep -> be mat p-hacking con song duy
    # nhat cua thiet ke nay. Vi vay chi tinh/in/ghi verdict khi tier chinh xac
    # bang PRIMARY_TIER; nguoc lai chi in bang mo ta va mot dong noi ro day
    # KHONG phai kiem dinh da dang ky.
    if args.tier == PRIMARY_TIER:
        tail = verdict(track_a, track_b)[1]
    else:
        tail = ("\n## KHONG phai kiem dinh da dang ky\n\n"
                f"Tang `{args.tier}` khac tang chinh `{PRIMARY_TIER}`. Luat "
                "chot section 6 CHI ap dung cho tang chinh (spec 1b section "
                "5). Ket qua o day CHI la mo ta, khong tuyen bo pass/fail, "
                "khong duoc doc thanh phan quyet.")
    print(tail)

    out_dir = args.out_dir or (ROOT / "results" / "quarter_variants"
                               / date.today().isoformat())
    out_dir.mkdir(parents=True, exist_ok=True)
    screened.to_csv(out_dir / "screen.csv", index=False)
    conf.to_csv(out_dir / "confirm.csv", index=False)
    head = ["# Quarterly Theory - nghien cuu bien the (phase 1b)", "",
            f"- symbol: {args.symbol}  timeframe: {args.tf}  bars: {len(bars)}",
            f"- tang chinh: {args.tier}  shifts xin: {args.shifts}  "
            f"thuc te: {len(offsets)}  seed: {args.seed}",
            f"- chia 50/50: nua dau {len(first)} bar, nua sau {len(second)} bar",
            "- spec: docs/superpowers/specs/"
            "2026-09-09-quarterly-theory-variants-study-design.md", "",
            "## Vong sang tren nua dau (chi de xep hang, KHONG phai bang chung)",
            "", "```", screened.to_string(index=False), "```", "",
            "## Kiem dinh cuoi tren nua sau", "",
            "```", conf.to_string(index=False), "```", ""]
    (out_dir / "summary.md").write_text("\n".join(head) + tail + "\n",
                                        encoding="utf-8")
    print(f"\nket qua: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
