"""End-to-end cho `scripts/study_h4_kill.py` trên dữ liệu tổng hợp nhỏ.

Chạy bằng `subprocess` như mọi test script khác của repo (`test_cli.py`,
`test_rerender.py`): script là một tiến trình, và test nó bằng cách import hàm
bên trong nó sẽ bỏ sót đúng những thứ chỉ tồn tại khi nó chạy thật — mã thoát,
cổng chặn, file đã ghi. `verdict` không nằm ở đây mà ở `rsi_fvg/h4_kill.py`
chính vì lý do ngược lại: nó là cổng kết luận của cả nghiên cứu nên phải có test
gọi hàm trực tiếp (xem `tests/test_h4_kill.py`).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from conftest import epoch_for_ny
from rsi_fvg.data.mt5_loader import cache_paths
from rsi_fvg.params import SymbolSpec

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "study_h4_kill.py"

# 23 giờ giao dịch của một ngày H4: 18:00 NY tới 16:00 NY hôm sau. 17:00 NY là
# khe nghỉ và bị bỏ — chính khe đó là thứ cổng §6.1 đo.
NY_HOURS = (18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4,
            5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)

# 2026-03-15 tới 2026-10-31 nằm TRỌN trong một mùa DST (EDT). Cố ý: chuỗi tổng
# hợp bắc qua biên DST sẽ có giờ 02:00 NY không tồn tại và `pd.Timestamp` ném.
# Biên DST được test riêng ở `tests/test_h4_grid.py`, không phải ở đây.
START_DAY = "2026-03-15"
N_DAYS = 230                       # 230 * 23 = 5290 bar, qua nguong 5000 cua main


def _frame(days: int = N_DAYS, seed: int = 11, shift_seconds: int = 0,
           spread: int | None = None) -> pd.DataFrame:
    """Bar H1 với mốc treo tường New York đúng, cộng `shift_seconds` nếu muốn
    một nguồn đọc SAI timezone."""
    rng = np.random.default_rng(seed)
    times = []
    d0 = pd.Timestamp(START_DAY)
    for k in range(days):
        day0 = d0 + pd.Timedelta(days=k)
        for hh in NY_HOURS:
            day = day0 + pd.Timedelta(days=0 if hh >= 17 else 1)
            times.append(epoch_for_ny(day.year, day.month, day.day, hh))
    n = len(times)
    close = 2000 + np.cumsum(rng.normal(0, 1.5, n))
    open_ = np.r_[close[0], close[:-1]]
    out = pd.DataFrame({
        "time": np.asarray(times, dtype="int64") + int(shift_seconds),
        "open": open_,
        "high": np.maximum(open_, close) + rng.uniform(0.05, 3.0, n),
        "low": np.minimum(open_, close) - rng.uniform(0.05, 3.0, n),
        "close": close,
        "tick_volume": rng.integers(10, 500, n),
    })
    if spread is not None:
        out["spread"] = np.full(n, spread, dtype="int64")
    return out


def _run(*args, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=ROOT, timeout=timeout)


def test_help_runs():
    p = _run("--help")
    assert p.returncode == 0
    assert "--shifts" in p.stdout and "--source" in p.stdout


def test_end_to_end_csv_writes_every_artifact(tmp_path):
    csv = tmp_path / "synth_h1.csv"
    _frame(spread=260).to_csv(csv, index=False)
    out = tmp_path / "out"
    p = _run("--source", "csv", "--csv", str(csv), "--tf", "H1",
             "--shifts", "5", "--out-dir", str(out))
    assert p.returncode == 0, f"stdout:\n{p.stdout}\nstderr:\n{p.stderr}"

    # cổng chặn phải chạy TRƯỚC nghiên cứu và in cả bảng điểm, không chỉ người thắng
    assert "cong chan timezone" in p.stdout
    assert "PASS (UTC)" in p.stdout
    assert "bang diem" in p.stdout

    for name in ("rows.csv", "stats.csv", "summary.md",
                 "excursion_usd_by_year.csv", "killed_range_usd_by_year.csv"):
        assert (out / name).exists(), name

    rows = pd.read_csv(out / "rows.csv")
    assert len(rows) > 0 and set(rows["slot"]) == set(range(6))
    stats = pd.read_csv(out / "stats.csv")
    assert (stats["n_nulls"] > 0).any()
    assert "standardized.std_s0" in set(stats["quantity"])

    text = (out / "summary.md").read_text(encoding="utf-8")
    assert csv.name in text                       # nguon sinh ra so phai nam trong bao cao
    assert "FXCM" in text                         # va phai noi ro no KHONG phai FXCM
    assert "## Cong chan timezone" in text
    assert "## Bang (slot x decile)" in text
    assert "## Phan quyet section 10" in text
    assert "Null B" in text                       # cong thu ba khong ton tai
    # Spec 4.4: MOI LAN in `max` phai kem ghi chu rang do la dung mot diem du
    # lieu. Bao cao in `max` o hai cho (bang thong ke, va hai file theo nam),
    # nen ghi chu phai xuat hien hai lan — mot lan la da bo quen mot cho.
    assert text.count("diem du lieu") >= 2
    assert "2025" in text                         # canh bao USD gop ca mau
    assert "spread trung vi" in text              # gia la BID, thien lech mot phia


def test_timezone_gate_blocks_and_writes_nothing(tmp_path):
    """Chuỗi liên tục không có khe nghỉ nào: cổng không dò được gì -> thoát 1,
    và nghiên cứu KHÔNG được chạy. Mọi biên slot là một mốc giờ New York, nên
    một nghiên cứu chạy sau khi cổng fail chỉ đang in số trông hợp lý cho một
    lưới khác."""
    n = 6000
    t = 1_700_000_000 + np.arange(n, dtype="int64") * 3600
    close = 2000 + np.cumsum(np.random.default_rng(3).normal(0, 1.5, n))
    csv = tmp_path / "no_gaps.csv"
    pd.DataFrame({"time": t, "open": close, "high": close + 1.0,
                  "low": close - 1.0, "close": close}).to_csv(csv, index=False)
    out = tmp_path / "out"
    p = _run("--source", "csv", "--csv", str(csv), "--tf", "H1",
             "--shifts", "3", "--out-dir", str(out))
    assert p.returncode == 1, f"stdout:\n{p.stdout}"
    assert "FAIL" in p.stdout
    assert not out.exists()


def test_mt5_source_must_read_as_utc(tmp_path):
    """`Bars.time` là instant UTC thật (rsi_fvg/quarters.py). Nếu cổng dò ra
    thứ khác trên nguồn mt5 thì ngữ nghĩa của `time` đã đổi, và mọi kết quả CŨ
    cũng phải đọc lại — nên script dừng thay vì chạy tiếp."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pq, sj = cache_paths(data_dir, "XAUUSDc", "H1")
    # Lệch +5h chứ không phải +3h: ở +3h thì `Europe/Athens` (EEST = +3 vào mùa
    # hè) đạt 0,917 và cổng chết ở nhánh "biên quá hẹp" TRƯỚC khi tới được nhánh
    # mt5-phải-là-UTC. Đó là hành vi đúng của cổng, nhưng nó che mất nhánh đang
    # được test ở đây.
    _frame(shift_seconds=5 * 3600).to_parquet(pq, index=False)
    sj.write_text(json.dumps(SymbolSpec(name="XAUUSDc", point=0.001, digits=3,
                                        contract_size=1.0).to_dict()),
                  encoding="utf-8")
    out = tmp_path / "out"
    p = _run("--source", "mt5", "--symbol", "XAUUSDc", "--tf", "H1",
             "--data-dir", str(data_dir), "--shifts", "3", "--out-dir", str(out))
    assert p.returncode == 1, f"stdout:\n{p.stdout}"
    assert "phai doc duoc la UTC" in p.stdout
    assert not out.exists()


def test_too_few_bars_exits_two(tmp_path):
    csv = tmp_path / "tiny.csv"
    _frame(days=20).to_csv(csv, index=False)
    out = tmp_path / "out"
    p = _run("--source", "csv", "--csv", str(csv), "--tf", "H1",
             "--shifts", "3", "--out-dir", str(out))
    assert p.returncode == 2, f"stdout:\n{p.stdout}"
    assert not out.exists()


def test_csv_source_without_path_fails_loudly(tmp_path):
    p = _run("--source", "csv", "--tf", "H1", "--out-dir", str(tmp_path / "out"))
    assert p.returncode != 0
    assert "--csv" in (p.stdout + p.stderr)
