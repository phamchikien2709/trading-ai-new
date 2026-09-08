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

**Timeframe trimming.** MT5 serves a prefix of coarser bars ahead of the genuine intraday history — for XAUUSDc, ~924 daily bars (2014-01 → 2017-01, `tick_volume == 1`, `spread == 0`, 00:00 stamps) and then a stretch of H1 bars. Feeding those to an intraday strategy silently corrupts every indicator, so the loader cuts them: `trim_to_timeframe()` runs on both a fresh fetch and a cached read, rewrites the cleaned parquet, and logs the dropped count plus the usable range. Usable history after trimming: M5 and M15 from 2017-04-27, H1 from 2017-02-27. The number the scripts print as "usable" is the trimmed range, not what the terminal holds.

**Timestamps.** `time` is what MT5 reports for the broker's own server clock, and the loader labels it UTC without converting. For Exness that clock runs UTC+2/+3 (EET with DST), so a bar stamped 00:00 is really 22:00 or 21:00 the previous UTC day. Nothing in the backtest depends on wall-clock time — there is no session filter — so the labelling is harmless, but do not read the timestamps as true UTC when lining a trade up against a news event or a TradingView chart.

## Layout

- `rsi_fvg/signals.py` — `Signal` / `Direction` shared by all strategies.
- `rsi_fvg/strategies/` — one module per strategy; each exposes `run_strategy(bars, params) -> list[Signal]` and never looks at positions.
- `rsi_fvg/backtest/engine.py` — fills at next open (+spread/slippage), open-then-intrabar exits (SL before TP), hedge or single concurrency, risk-% sizing, 10% ruin floor.
- `rsi_fvg/backtest/metrics.py`, `optimize.py`, `export.py` — stats, grid/IS-OOS/robustness/recommendation, xlsx + html.
- `rsi_fvg/data/` — MT5 loader (parquet cache + spec sidecar), CSV fallback.
- `config/default.yaml` — symbol, timeframes, costs, sizing.

## Tests

    python -m pytest -q

MT5 integration tests skip automatically when the terminal is not running.

## Known limits

- Fixed spread model (`costs.spread_points`); the per-bar spread stored in the parquet is not used yet.
- **TP exits take no slippage.** A TP is modelled as a limit fill at its exact price, while SL exits and entries pay `costs.slippage_points`. This is deliberate — a stop is a market order into a moving book, a limit order fills at its price or not at all — but it makes results very slightly optimistic: a TP that reality would have missed by a tick is booked here as a win.
- Exits resolve the bar's open first, then its range. A bar that gaps past TP books TP even if its range also reaches SL; only when the open sits between the levels does SL win the tie (one bar's OHLC cannot say which level was touched first).
- In `single` concurrency, two signals on the same bar are resolved SELL before BUY — signals are sorted by `(signal_bar, int(direction))` and `SELL == -1`, so the sell takes the slot and the buy is logged as `blocked`. This is an arbitrary tie-break, not a modelled preference; `hedge` (the default) takes both.
- No session filter, trailing stop or partial TP (by design, see specs).
- Live bot, MQL5 EA and cross-platform parity checks are a later phase.
- Pine ↔ Python parity is a manual spot-check (TradingView uses a different feed than Exness).

## RSI2 Swing Pullback — optimisation & report

Strategy: `rsi_fvg/strategies/rsi2_swing.py` (port of `pine/rsi2_swing_strategy.pine`).

    python scripts/run_rsi2_swing.py                     # 225 combos x M5/M15/H1, risk 5%, hedge
    python scripts/run_rsi2_swing.py --concurrency single
    python scripts/run_rsi2_swing.py --tf M15 --tp 2 3 --atr-mult 1 1.5 --rsi14 75/25 --rsi2 90/10
    python scripts/run_rsi2_swing.py --offline           # html with plotly.js embedded

Three optional variants, all off by default (so the numbers above reproduce unchanged):

    python scripts/run_rsi2_swing.py --rsi-fast 2 5      # scan the structure-RSI length too (grid x2)
    python scripts/run_rsi2_swing.py --min-sl-mult 3     # skip a trade whose SL sits inside 3 spreads
    python scripts/run_rsi2_swing.py --htf 3600          # H1 RSI14 trend gate: BUY > 50, SELL < 50

`--rsi-fast` is a real grid axis (a second length doubles the combo count) and appears in the Grid sheet,
the heatmap titles and the recommendation. `--min-sl-mult` refuses fills whose stop is closer than N
spreads to the entry — the RSI(2) swing puts it a median $1.7 away on M1, inside the noise the spread
itself makes — and logs them as `rejected_min_sl` in `skipped_<TF>.csv`. `--htf` (seconds; 3600 = H1)
takes a signal only when the last **completed** higher-timeframe RSI agrees with its direction; a gated-out
trigger still consumes its flag, so one RSI14 cross is still at most one trade. Both switches are recorded
on every grid row (`min_sl_mult`, `n_rejected_min_sl`, `htf_seconds`) and in the Params sheet.

Output `results/rsi2_swing/<timestamp>/`:
- `report_<symbol>.xlsx` — Summary (recommendation + run config), Grid (all combos, IS/OOS, robustness, flags),
  Trades_<TF>, Monthly_<TF>, Equity_<TF> for recommended combos, Params.
- `report_<symbol>.html` — equity/drawdown, R distribution, OOS heatmaps (TP x ATR per RSI set), IS-vs-OOS scatter, top-10, warnings.
- `grid.csv`, `trades_<TF>.csv`, plus `skipped_<TF>.csv` when signals were dropped (blocked by an open position,
  or rejected for an invalid SL).

How the recommendation is chosen (spec §4.3): IS = first 70% of bars, OOS = last 30%.

A combo has to be profitable **in cash**, not just in R. It qualifies when it did not blow the account
(`ruined`), IS n >= 30, IS avg R > 0, net P&L > 0, profit factor > 1.0, max drawdown <= 50%, at most 10% of its
trades hit the min-lot floor (`oversized`) and at most 50% were clamped by `max_lot` (`capped`). Without the cash
gates the filter endorsed losers: 107 of 675 combos in the first full run had avg R > 0 while losing money.

**OOS is a pass/fail gate only** — `OOS avg R > 0` and `OOS n >= 10`. It is not part of the score, because
scoring on the out-of-sample stretch *is* optimising on it, which spec §4.2 rules out. The ranking is
`0.6·z(IS avg R) + 0.4·z(robustness)`, where robustness = median IS avg R of the grid neighbours (±1 step in TP
and ATR mult, same four RSI levels). Sharp peaks lose to plateaus on purpose. No qualifier → "no reliable
parameter set", never a forced pick.

A pick sitting on the first or last value of the TP or ATR grid is marked `grid_edge` / "(grid edge)": the
optimum may lie outside the grid, so widen it before trusting the number.
