# RSI Pullback Strategies — Python backtest & optimisation

Two XAUUSD strategies share one backtest core:

- **RSI2 Swing Pullback** — `rsi_fvg/strategies/rsi2_swing.py` (port of `pine/rsi2_swing_strategy.pine`). Optimisation + Excel/HTML report: see below.
- **RSI-FVG Pullback** — `rsi_fvg/strategies/rsi_fvg.py` (port of `pine/rsi_fvg_strategy.pine`). Engine-ready; its grid report is not wired yet.

Specs: `docs/superpowers/specs/`. Plans: `docs/superpowers/plans/`.

## Setup (Windows, Python 3.13)

    pip install -r requirements.txt

An MT5 terminal must be open and logged in for data fetching. **Use a demo account for anything that trades** — this repo only reads history and never sends orders.

## Data

    python scripts/fetch_data.py                 # XAUUSDc M5/M15/H1 -> data/*.parquet + *.spec.json
    python scripts/fetch_data.py --refresh       # re-download
    python scripts/fetch_data.py --start 2023-01-01

The `.spec.json` sidecar stores the broker's symbol spec (point, contract size, lot step) so backtests use real values. If a "Max bars in chart" warning appears: MT5 → Tools → Options → Charts → Max bars in chart → Unlimited, restart the terminal, rerun with `--refresh`.

## Layout

- `rsi_fvg/signals.py` — `Signal` / `Direction` shared by all strategies.
- `rsi_fvg/strategies/` — one module per strategy; each exposes `run_strategy(bars, params) -> list[Signal]` and never looks at positions.
- `rsi_fvg/backtest/engine.py` — fills at next open (+spread/slippage), SL before TP, hedge or single concurrency, risk-% sizing.
- `rsi_fvg/backtest/metrics.py`, `optimize.py`, `export.py` — stats, grid/IS-OOS/robustness/recommendation, xlsx + html.
- `rsi_fvg/data/` — MT5 loader (parquet cache + spec sidecar), CSV fallback.
- `config/default.yaml` — symbol, timeframes, costs, sizing.

## Tests

    python -m pytest -q

MT5 integration tests skip automatically when the terminal is not running.

## Known limits

- Fixed spread model (`costs.spread_points`); the per-bar spread stored in the parquet is not used yet.
- No session filter, trailing stop or partial TP (by design, see specs).
- Live bot, MQL5 EA and cross-platform parity checks are a later phase.
- Pine ↔ Python parity is a manual spot-check (TradingView uses a different feed than Exness).

## RSI2 Swing Pullback — optimisation & report

Strategy: `rsi_fvg/strategies/rsi2_swing.py` (port of `pine/rsi2_swing_strategy.pine`).

    python scripts/run_rsi2_swing.py                     # 225 combos x M5/M15/H1, risk 5%, hedge
    python scripts/run_rsi2_swing.py --concurrency single
    python scripts/run_rsi2_swing.py --tf M15 --tp 2 3 --atr-mult 1 1.5 --rsi14 75/25 --rsi2 90/10
    python scripts/run_rsi2_swing.py --offline           # html with plotly.js embedded

Output `results/rsi2_swing/<timestamp>/`:
- `report_<symbol>.xlsx` — Summary (recommendation + run config), Grid (all combos, IS/OOS, robustness, flags),
  Trades_<TF>, Monthly_<TF>, Equity_<TF> for recommended combos, Params.
- `report_<symbol>.html` — equity/drawdown, R distribution, OOS heatmaps (TP x ATR per RSI set), IS-vs-OOS scatter, top-10, warnings.
- `grid.csv`, `trades_<TF>.csv`.

How the recommendation is chosen (spec §4): IS = first 70% of bars, OOS = last 30%. A combo qualifies when
IS n >= 30, IS avg R > 0, OOS avg R > 0 and <= 10% of its trades hit the min-lot floor. Score =
0.5·z(OOS avg R) + 0.3·z(robustness) + 0.2·z(IS avg R); robustness = median IS avg R of the grid neighbours
(±1 step in TP and ATR mult). Sharp peaks lose to plateaus on purpose. No qualifier → "no reliable parameter set".
