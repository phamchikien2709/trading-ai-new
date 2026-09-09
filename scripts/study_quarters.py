"""Đo tiền đề Quarterly Theory: lưới thời gian có cấu trúc thật, hay chỉ là hình
học của việc chia bốn?

Spec: docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md

Usage:
  python scripts/study_quarters.py
  python scripts/study_quarters.py --tf M5 --shifts 200 --seed 20260909
  python scripts/study_quarters.py --tiers session          # chỉ một tầng

Mã thoát: 0 nghiên cứu chạy xong; 1 cổng chặn timezone fail; 2 không đủ dữ liệu.
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
from rsi_fvg.data.mt5_loader import load_or_fetch  # noqa: E402
from rsi_fvg.quarter_stats import (make_offsets, percentile_of,  # noqa: E402
                                   run_grid, run_null)
from rsi_fvg.quarters import TIERS, verify_server_tz  # noqa: E402

TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600}

# Con số duy nhất mà luật kết luận §7 dùng, và ngưỡng của nó.
VERDICT_KEY = "reclaim_q3.reclaim_pooled_against"
VERDICT_THRESHOLD = 95.0


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbol", default="XAUUSDc")
    p.add_argument("--tf", default="M5", choices=sorted(TF_SECONDS))
    p.add_argument("--tiers", nargs="+", default=["session", "q90"],
                   choices=sorted(TIERS))
    p.add_argument("--shifts", type=int, default=200,
                   help="số lưới null xin; tầng q90 chỉ có 69 mốc khả dụng")
    p.add_argument("--seed", type=int, default=20260909)
    p.add_argument("--data-dir", type=Path, default=ROOT / "data")
    p.add_argument("--out-dir", type=Path, default=None)
    return p.parse_args(argv)


def load_bars(symbol: str, tf: str, data_dir: Path) -> Bars:
    """load_or_fetch tra ve (DataFrame, SymbolSpec). Nghien cuu nay khong dung
    spec — khong co sizing, khong co cost — nen bo qua nua sau."""
    df, _spec = load_or_fetch(symbol, tf, data_dir)
    return Bars.from_dataframe(df)


def gate_timezone(bars: Bars, bar_seconds: int) -> None:
    """Cổng chặn §3.2. Fail thì thoát 1 và KHÔNG chạy nghiên cứu."""
    chk = verify_server_tz(bars.time, bar_seconds)
    print("--- cong chan timezone (spec 3.2) ---")
    print(f"  mo dau tuan  : {chk.weekly_open_mode!r}  ok={chk.weekly_ok}")
    print(f"    phan phoi  : {chk.weekly_open_counts}")
    print(f"  ket khe ngay : {chk.daily_gap_end_mode!r}  ok={chk.daily_ok}")
    print(f"    phan phoi  : {chk.daily_gap_end_counts}")
    for note in chk.notes:
        print(f"  ghi chu: {note}")
    if not chk.ok:
        print("\nFAIL: cach doc Bars.time khong khop du lieu nay.")
        print("Moi bien quarter la mot moc gio New York, nen neu ngu nghia cua")
        print("time da doi thi nghien cuu se do sai hoan toan. Khong chay tiep.")
        print("Xem spec section 2 va 3.2, va docstring rsi_fvg/quarters.py.")
        sys.exit(1)
    print("  PASS\n")


def study_tier(bars: Bars, tier: str, bar_seconds: int,
               shifts: int, seed: int) -> pd.DataFrame:
    real = run_grid(bars, tier)
    offsets = make_offsets(tier, bar_seconds, shifts, seed)
    if len(offsets) < shifts:
        print(f"  [{tier}] chi co {len(offsets)} moc neo kha dung (xin {shifts}). "
              f"Chu ky {4 * TIERS[tier]} s / bar {bar_seconds} s gioi han so luoi null.")
    nulls = run_null(bars, tier, offsets)

    rows = []
    for key, real_value in real.items():
        col = nulls[key].to_numpy(dtype="float64") if key in nulls else np.array([])
        finite = col[np.isfinite(col)]
        rows.append({
            "tier": tier, "quantity": key, "real": real_value,
            "null_mean": float(finite.mean()) if finite.size else float("nan"),
            "null_p05": float(np.percentile(finite, 5)) if finite.size else float("nan"),
            "null_p50": float(np.percentile(finite, 50)) if finite.size else float("nan"),
            "null_p95": float(np.percentile(finite, 95)) if finite.size else float("nan"),
            "real_percentile": percentile_of(real_value, col),
            "n_nulls": int(finite.size),
        })
    return pd.DataFrame(rows)


def verdict(stats: pd.DataFrame) -> tuple[bool, str]:
    """Luật §7, tính bằng máy — không để người đọc tự kết luận."""
    rows = stats[stats["quantity"] == VERDICT_KEY]
    lines = ["## Phan quyet section 7", ""]
    passed = False
    for _, r in rows.iterrows():
        hit = bool(np.isfinite(r["real_percentile"])
                   and r["real_percentile"] > VERDICT_THRESHOLD)
        passed = passed or hit
        lines.append(f"- tang **{r['tier']}**: real={r['real']:.4f}, "
                     f"percentile={r['real_percentile']:.1f}, "
                     f"nulls={r['n_nulls']} -> {'VUOT' if hit else 'khong vuot'} "
                     f"nguong {VERDICT_THRESHOLD}")
    lines += ["", (
        "**Phase 2 duoc phep viet spec.** Thong ke 6 pooled vuot percentile 95 "
        "cua null o it nhat mot tang." if passed else
        "**Phase 2 KHONG duoc phep viet spec.** Thong ke 6 pooled khong vuot "
        "percentile 95 o tang nao. Cac phep do 1-5 du dep cung khong mo cong "
        "nay (spec section 7)."
    ), "", (
        "Luu y da ghi trong spec section 7: luat nay chay 2 kiem dinh o muc 95% "
        "nen sai so toan ho khoang 10%, khong phai 5%. Nguong de nay duoc chon "
        "co y thuc va khong duoc siet hay noi sau khi thay so."
    )]
    return passed, "\n".join(lines)


def main(argv=None) -> int:
    args = parse_args(argv)
    bar_seconds = TF_SECONDS[args.tf]
    bars = load_bars(args.symbol, args.tf, args.data_dir)
    print(f"{args.symbol} {args.tf}: {len(bars)} bar")
    if len(bars) < 1000:
        print("FAIL: qua it bar de do bat cu thu gi.")
        return 2

    gate_timezone(bars, bar_seconds)

    parts = [study_tier(bars, t, bar_seconds, args.shifts, args.seed)
             for t in args.tiers]
    stats = pd.concat(parts, ignore_index=True)

    out_dir = args.out_dir or (ROOT / "results" / "quarters_study" / date.today().isoformat())
    out_dir.mkdir(parents=True, exist_ok=True)
    stats.to_csv(out_dir / "stats.csv", index=False)

    passed, verdict_md = verdict(stats)
    # KHONG dung stats.to_markdown: no doi `tabulate`, khong co trong
    # requirements.txt (da kiem). to_string trong khoi ``` cho ket qua doc duoc
    # ma khong them dependency.
    head = ["# Quarterly Theory - nghien cuu tien de", "",
            f"- symbol: {args.symbol}  timeframe: {args.tf}  bars: {len(bars)}",
            f"- tiers: {', '.join(args.tiers)}  shifts xin: {args.shifts}  seed: {args.seed}",
            "- spec: docs/superpowers/specs/2026-09-09-quarterly-theory-premise-study-design.md",
            "", "## Bang thong ke", "",
            "```", stats.to_string(index=False), "```", ""]
    (out_dir / "summary.md").write_text("\n".join(head) + verdict_md + "\n",
                                        encoding="utf-8")
    print(verdict_md)
    print(f"\nket qua: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
