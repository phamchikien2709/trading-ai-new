"""End-to-end smoke test for scripts/run_rsi2_swing.py on a tiny synthetic cache."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rsi_fvg.data.mt5_loader import cache_paths
from rsi_fvg.params import SymbolSpec

ROOT = Path(__file__).resolve().parents[1]
SYMBOL = "XAUUSDc"  # matches config/default.yaml's default symbol, so CLI runs that omit --symbol find the cache


def _write_cache(data_dir: Path, symbol: str = SYMBOL, n: int = 3000, seed: int = 7) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2.0, n))
    open_ = np.r_[close[0], close[:-1]]
    df = pd.DataFrame({
        "time": (1_700_000_000 + np.arange(n, dtype="int64") * 300),
        "open": open_,
        "high": np.maximum(open_, close) + rng.uniform(0.1, 2.0, n),
        "low": np.minimum(open_, close) - rng.uniform(0.1, 2.0, n),
        "close": close,
        "tick_volume": rng.integers(10, 500, n),
        "spread": np.full(n, 260, dtype="int64"),
    })
    pq, sj = cache_paths(data_dir, symbol, "M5")
    df.to_parquet(pq, index=False)
    sj.write_text(json.dumps(SymbolSpec(name=symbol, point=0.001, digits=3, contract_size=1.0).to_dict()),
                  encoding="utf-8")


def test_cli_writes_grid_and_reports(tmp_path):
    data_dir, out_dir = tmp_path / "data", tmp_path / "results"
    _write_cache(data_dir)
    cmd = [sys.executable, str(ROOT / "scripts" / "run_rsi2_swing.py"),
           "--symbol", SYMBOL, "--tf", "M5", "--tp", "2", "--atr-mult", "1",
           "--rsi14", "75/25", "--rsi2", "90/10", "--rsi-fast", "2", "5", "--min-sl-mult", "1.5", "--htf", "3600",
           "--data-dir", str(data_dir), "--out", str(out_dir)]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=600)
    assert p.returncode == 0, f"stdout:\n{p.stdout}\nstderr:\n{p.stderr}"
    assert "usable" in p.stdout and "=== Recommendation ===" in p.stdout
    runs = [d for d in out_dir.iterdir() if d.is_dir()]
    assert len(runs) == 1
    run = runs[0]
    assert (run / "grid.csv").exists()
    assert (run / f"report_{SYMBOL}.xlsx").exists()
    assert (run / f"report_{SYMBOL}.html").exists()
    grid = pd.read_csv(run / "grid.csv")
    assert len(grid) == 2                                   # one combo per fast-RSI length
    assert sorted(grid["rsi_fast"]) == [2, 5]
    assert (grid["min_sl_mult"] == 1.5).all()               # --min-sl-mult reaches the engine
    assert (grid["htf_seconds"] == 3600).all()              # --htf reaches the strategy


def test_pairs_rejects_malformed_values():
    sys.path.insert(0, str(ROOT / "scripts"))
    import argparse
    import importlib

    mod = importlib.import_module("run_rsi2_swing")
    assert mod._pairs(["75/25", "80/20"]) == ((75.0, 25.0), (80.0, 20.0))
    for bad in ("7525", "75/25/5", ""):
        with pytest.raises(argparse.ArgumentTypeError, match="expected A/B"):
            mod._pairs([bad])
    with pytest.raises(argparse.ArgumentTypeError, match="expected A/B with numbers"):
        mod._pairs(["hi/there"])


def test_data_dir_help_mentions_the_live_fetch():
    text = (ROOT / "scripts" / "run_rsi2_swing.py").read_text(encoding="utf-8")
    assert "a missing cache triggers a live MT5 fetch of full history" in text


def test_optimize_cli_runs_rsi2_ema_swing(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_cache(data_dir)
    out = tmp_path / "results"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "optimize.py"),
                        "--strategy", "rsi2_ema_swing", "--tf", "M5",
                        "--axis", "ema=20/100", "--axis", "atr_mult=1.5",
                        "--axis", "rsi_fast=2", "--axis", "rsi2=90/10",
                        "--tp", "4", "--risk", "1",
                        "--data-dir", str(data_dir), "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    # A crash AFTER the files are written still exits 0-ish in spirit: the printed block is the
    # only proof the run reached its end (this is how KeyError: 'ob' shipped).
    assert "=== Recommendation ===" in r.stdout
    folders = list((out).glob("*"))
    assert len(folders) == 1
    produced = {p.name for p in folders[0].iterdir()}
    assert "grid.csv" in produced
    assert any(n.startswith("report_") and n.endswith(".xlsx") for n in produced)
    assert any(n.startswith("report_") and n.endswith(".html") for n in produced)
    head = (folders[0] / "grid.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert head[:8] == ["tf", "rsi_fast", "f_hi", "f_lo", "ema_fast", "ema_slow", "atr_mult", "tp_r"]


def test_optimize_cli_runs_rsi2_swing_too(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_cache(data_dir)
    out = tmp_path / "results2"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "optimize.py"),
                        "--strategy", "rsi2_swing", "--tf", "M5",
                        "--axis", "rsi14=80/20", "--axis", "rsi2=90/10",
                        "--axis", "rsi_fast=2", "--axis", "atr_mult=1.5",
                        "--tp", "4", "--risk", "1",
                        "--data-dir", str(data_dir), "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "=== Recommendation ===" in r.stdout
    head = (next((out).glob("*")) / "grid.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert head[:8] == ["tf", "rsi_fast", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r"]


def test_optimize_cli_rejects_bad_axis(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_cache(data_dir)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "optimize.py"),
                        "--strategy", "rsi2_ema_swing", "--tf", "M5", "--axis", "nope=1",
                        "--data-dir", str(data_dir), "--out", str(tmp_path / "r3")],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode != 0
    assert "nope" in (r.stdout + r.stderr)


def test_optimize_cli_honours_an_explicit_non_default_symbol(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_cache(data_dir, symbol="XOVERRIDE")
    out = tmp_path / "results"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "optimize.py"),
                        "--strategy", "rsi2_ema_swing", "--tf", "M5", "--symbol", "XOVERRIDE",
                        "--axis", "ema=20/100", "--axis", "atr_mult=1.5",
                        "--axis", "rsi_fast=2", "--axis", "rsi2=90/10",
                        "--tp", "4", "--risk", "1",
                        "--data-dir", str(data_dir), "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "=== Recommendation ===" in r.stdout
    produced = {p.name for p in next(out.glob("*")).iterdir()}
    assert "report_XOVERRIDE.xlsx" in produced and "report_XOVERRIDE.html" in produced


def test_optimize_cli_rejects_an_empty_grid(tmp_path):
    """E: a bare `--tp` yields [] -> tp_r=() -> a zero-row grid, which used to load all the
    data first and then die with KeyError: 'ruin_time' on the empty frame."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_cache(data_dir)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "optimize.py"),
                        "--strategy", "rsi2_ema_swing", "--tf", "M5", "--tp",
                        "--data-dir", str(data_dir), "--out", str(tmp_path / "r")],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode != 0
    combined = r.stdout + r.stderr
    assert "empty grid" in combined and "Traceback" not in combined


def test_optimize_cli_rejects_a_repeated_axis(tmp_path):
    """F: `dict(...)` kept only the last value, so --axis ema=20/100 --axis ema=50/200 ran one
    pair instead of two — a silently smaller grid, never an error."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_cache(data_dir)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "optimize.py"),
                        "--strategy", "rsi2_ema_swing", "--tf", "M5",
                        "--axis", "ema=20/100", "--axis", "ema=50/200",
                        "--data-dir", str(data_dir), "--out", str(tmp_path / "r")],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode != 0
    combined = r.stdout + r.stderr
    assert "ema" in combined and "Traceback" not in combined


def test_optimize_cli_rejects_malformed_axis_value(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_cache(data_dir)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "optimize.py"),
                        "--strategy", "rsi2_ema_swing", "--tf", "M5", "--axis", "ema=abc",
                        "--data-dir", str(data_dir), "--out", str(tmp_path / "r")],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode != 0
    combined = r.stdout + r.stderr
    assert "ema" in combined and "Traceback" not in combined
