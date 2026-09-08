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
SYMBOL = "XCLITEST"


def _write_cache(data_dir: Path, n: int = 3000, seed: int = 7) -> None:
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
    pq, sj = cache_paths(data_dir, SYMBOL, "M5")
    df.to_parquet(pq, index=False)
    sj.write_text(json.dumps(SymbolSpec(name=SYMBOL, point=0.001, digits=3, contract_size=1.0).to_dict()),
                  encoding="utf-8")


def test_cli_writes_grid_and_reports(tmp_path):
    data_dir, out_dir = tmp_path / "data", tmp_path / "results"
    _write_cache(data_dir)
    cmd = [sys.executable, str(ROOT / "scripts" / "run_rsi2_swing.py"),
           "--symbol", SYMBOL, "--tf", "M5", "--tp", "2", "--atr-mult", "1",
           "--rsi14", "75/25", "--rsi2", "90/10",
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
    assert len(pd.read_csv(run / "grid.csv")) == 1          # one combo in the grid


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
