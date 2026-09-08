import numpy as np
import openpyxl
import pandas as pd
import pytest

from rsi_fvg.backtest.engine import run_backtest
from rsi_fvg.backtest.export import _equity_frame, write_csvs, write_html, write_xlsx
from rsi_fvg.backtest.optimize import GridSpec, recommend, run_optimization, run_single
from rsi_fvg.bars import Bars
from rsi_fvg.params import CostParams, SizingParams, SymbolSpec
from rsi_fvg.strategies.registry import StrategyAdapter, get_adapter
from rsi_fvg.strategies.rsi2_ema_swing import Rsi2EmaParams
from rsi_fvg.strategies.rsi2_swing import Rsi2SwingParams

ADAPTER = get_adapter("rsi2_swing")                    # default adapter for single-strategy tests
EMA_ADAPTER = get_adapter("rsi2_ema_swing")
STRATEGIES = ["rsi2_swing", "rsi2_ema_swing"]
SPEC = SymbolSpec(name="T", point=0.01, digits=2, contract_size=1.0)
COSTS = CostParams(spread_points=20, commission_per_lot_rt=0.0, slippage_points=0)
SIZING = SizingParams(risk_pct=5.0, initial_equity=10_000.0)

# Small, fast grids per adapter — kept tiny so the 6000-bar synthetic series stays quick to
# optimise over. rsi2_swing's non-varying axes match Rsi2SwingParams()' defaults so only
# atr_mult needs overriding when a picked row is re-run; same idea for rsi2_ema_swing.
_SMALL_GRIDS: dict[str, GridSpec] = {
    "rsi2_swing": GridSpec.for_strategy(ADAPTER, axes={"rsi14": ((75.0, 25.0),), "rsi2": ((90.0, 10.0),),
                                                        "atr_mult": (0.5, 1.0)}, tp_r=(1.0, 2.0)),
    "rsi2_ema_swing": GridSpec.for_strategy(EMA_ADAPTER, axes={"rsi_fast": (2,), "rsi2": ((90.0, 10.0),),
                                                                "ema": ((20, 100), (50, 200)),
                                                                "atr_mult": (1.5,)}, tp_r=(4.0,)),
}
_BASE_PARAMS = {"rsi2_swing": Rsi2SwingParams, "rsi2_ema_swing": Rsi2EmaParams}
SMALL = _SMALL_GRIDS["rsi2_swing"]                      # kept for any external references


def _bars(n=6000, seed=5):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, n)
    return Bars(time=1_700_000_000 + np.arange(n, dtype=np.int64) * 300, open=open_, high=high, low=low, close=close)


def _row_params(adapter: StrategyAdapter, base, row) -> object:
    """Rebuild a params object for one grid row, generically, from the adapter's own axes."""
    axis_values = {a.name: (tuple(row[c] for c in a.columns) if len(a.columns) > 1 else row[a.columns[0]])
                  for a in adapter.axes}
    return adapter.make_params(base, axis_values)


def _fixture(strategy: str = "rsi2_swing"):
    adapter = get_adapter(strategy)
    grid = _SMALL_GRIDS[strategy]
    base = _BASE_PARAMS[strategy]()
    b = _bars()
    df = run_optimization(adapter, {"M5": b}, {"M5": SPEC}, base, grid, COSTS, SIZING)
    rec = recommend(df, adapter)
    row = df.iloc[0]
    params = _row_params(adapter, base, row)
    _, res = run_single(adapter, b, SPEC, params, row.tp_r, COSTS, SIZING, "hedge")
    info = {"symbol": "T", "timeframes": ["M5"], "data_range": {"M5": ("2023-11-14", "2023-12-05")},
            "initial_equity": 10_000, "risk_pct": 5.0, "concurrency": "hedge", "spread_points": 20,
            "commission_per_lot_rt": 0.0, "slippage_points": 0, "is_frac": 0.7,
            "grid": {"tp_r": list(grid.tp_r), **grid.axes}, "strategy": strategy,
            "git_hash": "test", "generated_at": "2026-09-08 00:00"}
    return df, rec, {"M5": res}, info


def test_write_csvs(tmp_path):
    df, rec, res, info = _fixture()
    write_csvs(tmp_path, df, res, info)
    assert (tmp_path / "grid.csv").exists() and (tmp_path / "trades_M5.csv").exists()
    assert len(pd.read_csv(tmp_path / "grid.csv")) == 4
    grid = pd.read_csv(tmp_path / "grid.csv")
    for c in ("ruined", "capped_share", "grid_edge", "is_max_dd_pct", "oos_max_dd_pct"):
        assert c in grid.columns


def test_write_csvs_emits_skipped_only_when_non_empty(tmp_path):
    df, _, res, info = _fixture()
    r = res["M5"]
    assert r.skipped.empty
    write_csvs(tmp_path, df, res, info)
    assert not (tmp_path / "skipped_M5.csv").exists()          # nothing to say, no file
    r.skipped = pd.DataFrame([{"time": pd.Timestamp("2024-01-01", tz="UTC"),
                               "signal_time": pd.Timestamp("2024-01-01", tz="UTC"),
                               "direction": "BUY", "variant": "SWING", "reason": "blocked"}])
    write_csvs(tmp_path, df, res, info)
    assert (tmp_path / "skipped_M5.csv").exists()
    assert len(pd.read_csv(tmp_path / "skipped_M5.csv")) == 1


def test_equity_frame_drawdown_uses_the_full_curve():
    # M3: the peak lands on bar 201, which a 1-in-20 downsample drops. Taking the drawdown
    # after thinning would never see it and would report no drawdown at all.
    b = _bars(400)
    res = run_backtest(b, [], 1.0, SPEC, COSTS, SIZING)
    vals = np.full(400, 10_000.0)
    vals[201] = 20_000.0
    res.equity = pd.Series(vals, index=res.equity.index)
    frame = _equity_frame(res, max_rows=20)
    assert len(frame) <= 21
    assert frame["drawdown_usd"].max() == pytest.approx(10_000.0)
    assert frame["drawdown_pct"].max() == pytest.approx(50.0)


def test_write_xlsx_sheets_and_rows(tmp_path):
    df, rec, res, info = _fixture()
    p = tmp_path / "r.xlsx"
    write_xlsx(p, df, rec, res, info)
    wb = openpyxl.load_workbook(p, read_only=True)
    assert {"Summary", "Grid", "Trades_M5", "Monthly_M5", "Equity_M5", "Params"} <= set(wb.sheetnames)
    assert wb["Grid"].max_row == 5            # header + 4 combos
    head = [c.value for c in next(wb["Grid"].iter_rows(min_row=1, max_row=1))]
    assert head[:8] == ["tf", "rsi_fast", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r"]
    assert wb["Equity_M5"].max_row <= 20_001   # downsampled


def _rec_for(df, adapter: StrategyAdapter = ADAPTER):
    """A recommendation dict for row 0, as recommend() would return it (random-walk bars
    never clear the profit gates, so the 'recommended' branch needs a hand-built pick)."""
    from rsi_fvg.backtest.optimize import _param_value, _reason
    best = df.iloc[0]
    return {"M5": {"params": {k: _param_value(best, k, adapter.int_cols) for k in adapter.full_key_cols()},
                   "score": 1.23, "row": best.to_dict(), "reason": _reason(best)}}


def test_reports_show_cash_metrics_for_a_recommended_combo(tmp_path):
    df, _, res, info = _fixture()
    rec = _rec_for(df)
    write_xlsx(tmp_path / "r.xlsx", df, rec, res, info)
    wb = openpyxl.load_workbook(tmp_path / "r.xlsx", read_only=True)
    head = [c.value for row in wb["Summary"].iter_rows() for c in row if isinstance(c.value, str)]
    for col in ("net_pnl", "profit_factor", "max_dd_pct", "capped_share", "ruined"):
        assert col in head, f"{col} missing from the Summary recommendation table"
    write_html(tmp_path / "r.html", df, rec, res, info)
    html = (tmp_path / "r.html").read_text(encoding="utf-8")
    for token in ("net P&amp;L", "profit factor", "max drawdown", "capped lots"):
        assert token in html


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_write_reports_for_each_strategy(tmp_path, strategy):
    """End-to-end write_csvs/write_xlsx/write_html for both registered adapters — this is what
    would have raised KeyError: 'ob' building the HTML recommendation for rsi2_ema_swing before
    the recommendation line was made generic (grep for the fixed line: rsi_fvg/backtest/export.py).

    Checks the Grid header (csv + xlsx) starts with the adapter's own full_key_cols(), and that
    write_html's Recommendation block either names every one of the adapter's key columns (via a
    forced 'recommended' entry, since random-walk bars rarely clear the real profit gates) or
    takes the 'no reliable parameter set' branch for the real recommend() output.
    """
    adapter = get_adapter(strategy)
    df, rec, res, info = _fixture(strategy)

    write_csvs(tmp_path, df, res, info)
    grid_csv = pd.read_csv(tmp_path / "grid.csv")
    assert list(grid_csv.columns[:len(adapter.full_key_cols())]) == adapter.full_key_cols()

    write_xlsx(tmp_path / "r.xlsx", df, rec, res, info)
    wb = openpyxl.load_workbook(tmp_path / "r.xlsx", read_only=True)
    head = [c.value for c in next(wb["Grid"].iter_rows(min_row=1, max_row=1))]
    assert head[:len(adapter.full_key_cols())] == adapter.full_key_cols()

    # Real recommend() output: either branch is valid on a small synthetic grid.
    write_html(tmp_path / "r.html", df, rec, res, info)
    html = (tmp_path / "r.html").read_text(encoding="utf-8")
    assert "Recommendation" in html
    r = rec["M5"]
    if r is None:
        assert "no reliable parameter set" in html
    else:
        assert adapter.title(r["params"]) in html
        assert adapter.axis(adapter.robust_axis).columns[0] in html

    # Forced 'recommended' entry (regression case for the KeyError: 'ob' bug): the line must
    # name every one of the adapter's own key columns, not a hardcoded set from one strategy.
    forced_rec = _rec_for(df, adapter)
    write_html(tmp_path / "forced.html", df, forced_rec, res, info)
    forced_html = (tmp_path / "forced.html").read_text(encoding="utf-8")
    row = df.iloc[0]
    assert adapter.title({k: row[k] for k in adapter.panel_cols}) in forced_html
    robust_col = adapter.axis(adapter.robust_axis).columns[0]
    assert robust_col in forced_html
    write_xlsx(tmp_path / "forced.xlsx", df, forced_rec, res, info)
    wb2 = openpyxl.load_workbook(tmp_path / "forced.xlsx", read_only=True)
    cells = [c.value for wrow in wb2["Summary"].iter_rows() for c in wrow if isinstance(c.value, str)]
    for col in adapter.key_cols:
        assert col in cells


def test_reports_name_the_fast_rsi_length(tmp_path):
    df, _, res, info = _fixture()
    rec = _rec_for(df)
    write_html(tmp_path / "r.html", df, rec, res, info)
    html = (tmp_path / "r.html").read_text(encoding="utf-8")
    assert "RSI(2)" in html                     # recommendation line names the fast RSI length
    assert "RSI(2) 90" in html                  # heatmap panel title (plotly escapes the "/")
    write_xlsx(tmp_path / "r.xlsx", df, rec, res, info)
    wb = openpyxl.load_workbook(tmp_path / "r.xlsx", read_only=True)
    cells = [c.value for row in wb["Summary"].iter_rows() for c in row if isinstance(c.value, str)]
    assert "rsi_fast" in cells


def test_write_xlsx_handles_no_recommendation(tmp_path):
    df, _, res, info = _fixture()
    write_xlsx(tmp_path / "r.xlsx", df, {"M5": None}, res, info)
    wb = openpyxl.load_workbook(tmp_path / "r.xlsx", read_only=True)
    cells = [c.value for row in wb["Summary"].iter_rows() for c in row if isinstance(c.value, str)]
    assert any("no reliable" in v for v in cells)


def test_write_html_contents(tmp_path):
    df, rec, res, info = _fixture()
    p = tmp_path / "r.html"
    write_html(p, df, rec, res, info)
    html = p.read_text(encoding="utf-8")
    assert "Recommendation" in html and "plotly" in html.lower()
    assert "Heatmap" in html or "heatmap" in html
    assert "cdn.plot.ly" in html                   # cdn mode by default
    write_html(tmp_path / "off.html", df, rec, res, info, offline=True)
    assert (tmp_path / "off.html").stat().st_size > 1_000_000   # plotly.js embedded


def test_write_html_handles_incomplete_grid(tmp_path):
    df, rec, res, info = _fixture()
    incomplete_df = df.iloc[:-1]  # Drop one row to create incomplete (3-of-4) grid
    p = tmp_path / "r.html"
    write_html(p, incomplete_df, rec, res, info)
    html = p.read_text(encoding="utf-8")
    assert p.exists()
    assert "Recommendation" in html
    # Also test write_xlsx does not crash on incomplete grid
    xlsx_p = tmp_path / "r.xlsx"
    write_xlsx(xlsx_p, incomplete_df, rec, res, info)
    assert xlsx_p.exists()


def test_grid_first_cols_follow_the_adapter():
    from rsi_fvg.backtest.export import grid_first_cols
    cols = grid_first_cols(ADAPTER)
    assert cols[:8] == ["tf", "rsi_fast", "ob", "os", "f_hi", "f_lo", "atr_mult", "tp_r"]
    assert "flags" in cols and "robust_r" in cols


def test_heatmap_has_one_panel_per_panel_col_combo():
    from rsi_fvg.backtest.export import _fig_heatmaps
    df, rec, res, info = _fixture()
    g = df[df["tf"] == "M5"]
    n_panels = g.groupby(ADAPTER.panel_cols).ngroups
    fig = _fig_heatmaps("M5", g, ADAPTER)
    assert len(fig.data) == n_panels
    assert "RSI(" in fig.layout.annotations[0].text          # adapter title used as the subplot title


def test_is_oos_labels_name_the_robust_axis_value():
    from rsi_fvg.backtest.export import _fig_is_oos
    df, rec, res, info = _fixture()
    g = df[df["tf"] == "M5"]
    fig = _fig_is_oos("M5", g, ADAPTER)
    labels = list(fig.data[0].text)
    assert len(labels) == len(g)
    robust_col = ADAPTER.axis(ADAPTER.robust_axis).columns[0]
    for label, (_, row) in zip(labels, g.iterrows()):
        assert f"TP {row['tp_r']:g}R" in label
        assert f"{robust_col}×{row[robust_col]:g}" in label
        assert ADAPTER.title(row.to_dict()) in label
    assert len(set(labels)) == len(labels)      # every combo is now distinguishable


def test_unknown_strategy_in_run_info_is_an_error(tmp_path):
    from rsi_fvg.backtest.export import write_xlsx
    df, rec, res, info = _fixture()
    with pytest.raises(KeyError):
        write_xlsx(tmp_path / "r.xlsx", df, rec, res, info | {"strategy": "nope"})
